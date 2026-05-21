"""Tests – Fluent builder (CaddyConfigBuilder, ServerBuilder, RouteBuilder, SubrouteBuilder)."""
import pytest

from caddyconfig import (
    CaddyConfig, Apps, MatchCriteria,
    ReverseProxyHandler, StaticResponseHandler,
    SubrouteHandler, FileServerHandler, AuthenticationHandler,
)
from caddyconfig.builder import CaddyConfigBuilder, RouteBuilder


# ---------------------------------------------------------------------------
# RouteBuilder – standalone (no parent)
# ---------------------------------------------------------------------------

class TestRouteBuilderStandalone:
    def test_build_empty(self):
        assert RouteBuilder().build().to_dict() == {}

    def test_build_with_group_and_terminal(self):
        r = RouteBuilder().group("g1").terminal().build()
        assert r.group == "g1"
        assert r.terminal is True

    def test_match_host_and_path(self):
        r = RouteBuilder().match(host=["foo.com"], path=["/api"]).build()
        assert r.match[0].host == ["foo.com"]
        assert r.match[0].path == ["/api"]

    def test_multiple_match_blocks_or_logic(self):
        r = RouteBuilder().match(host=["foo.com"]).match(host=["bar.com"]).build()
        assert len(r.match) == 2

    def test_handle_reverse_proxy(self):
        r = RouteBuilder().handle_reverse_proxy("10.0.0.1:80").build()
        h = r.get_handler("reverse_proxy")
        assert isinstance(h, ReverseProxyHandler)
        assert h.upstreams[0].dial == "10.0.0.1:80"

    def test_handle_reverse_proxy_multiple_upstreams(self):
        r = RouteBuilder().handle_reverse_proxy("a:1", "b:2").build()
        assert len(r.get_handler("reverse_proxy").upstreams) == 2  # type: ignore[union-attr]

    def test_handle_static(self):
        r = RouteBuilder().handle_static(200, body="OK").build()
        h = r.get_handler("static_response")
        assert isinstance(h, StaticResponseHandler)
        assert h.status_code == 200
        assert h.body == "OK"

    def test_handle_file_server(self):
        r = RouteBuilder().handle_file_server(root="/srv", browse=True).build()
        h = r.get_handler("file_server")
        assert isinstance(h, FileServerHandler)
        assert h.root == "/srv"
        assert h.browse is True

    def test_handle_auth_basic(self):
        r = RouteBuilder().handle_auth_basic(("alice", "hash"), realm="Admin").build()
        h = r.get_handler("authentication")
        assert isinstance(h, AuthenticationHandler)
        assert h.realm == "Admin"
        assert h.credentials[0].username == "alice"

    def test_handle_raw_handler(self):
        rp = ReverseProxyHandler(upstreams=["a:1"])
        r = RouteBuilder().handle(rp).build()
        assert r.get_handler("reverse_proxy") is rp

    def test_done_without_parent_raises(self):
        with pytest.raises(RuntimeError, match="parent"):
            RouteBuilder().done()


# ---------------------------------------------------------------------------
# SubrouteBuilder
# ---------------------------------------------------------------------------

class TestSubrouteBuilder:
    def test_basic_subroute(self):
        r = (
            RouteBuilder()
            .match(host=["foo.com"])
            .handle_subroute()
                .route().match(path=["/api"]).handle_reverse_proxy("10.0.0.1:80").done()
            .done()
            .build()
        )
        sub = r.get_handler("subroute")
        assert isinstance(sub, SubrouteHandler)
        assert sub.routes[0].match[0].path == ["/api"]

    def test_subroute_multiple_routes(self):
        r = (
            RouteBuilder()
            .handle_subroute()
                .route().match(path=["/a"]).handle_static(200).done()
                .route().match(path=["/b"]).handle_static(201).done()
            .done()
            .build()
        )
        assert len(r.get_handler("subroute").routes) == 2  # type: ignore[union-attr]

    def test_subroute_build_standalone(self):
        from caddyconfig.builder import SubrouteBuilder, RouteBuilder as RB
        parent_rb = RB()
        sb = SubrouteBuilder(parent=parent_rb)
        sb.route().match(path=["/x"]).handle_static(200).done()
        handler = sb.build()
        assert isinstance(handler, SubrouteHandler)
        assert len(handler.routes) == 1


# ---------------------------------------------------------------------------
# ServerBuilder
# ---------------------------------------------------------------------------

class TestServerBuilder:
    def test_server_name_and_listen(self):
        from caddyconfig.builder import ServerBuilder
        s = ServerBuilder(name="main", listen=[":443"]).build()
        assert s.name == "main"
        assert ":443" in s.listen

    def test_listen_method(self):
        from caddyconfig.builder import ServerBuilder
        sb = ServerBuilder(name="main")
        sb.listen(":443", ":80")
        assert set(sb.build().listen) == {":443", ":80"}

    def test_listen_deduplicates(self):
        from caddyconfig.builder import ServerBuilder
        sb = ServerBuilder(name="main", listen=[":443"])
        sb.listen(":443")
        assert sb.build().listen.count(":443") == 1

    def test_metrics(self):
        from caddyconfig.builder import ServerBuilder
        sb = ServerBuilder(name="main")
        sb.metrics(per_host=True)
        assert sb.build().metrics.per_host is True  # type: ignore[union-attr]

    def test_route_attached(self):
        from caddyconfig.builder import ServerBuilder
        sb = ServerBuilder(name="main")
        sb.route().match(host=["foo.com"]).handle_static(200).done()
        assert len(sb.build().routes) == 1

    def test_error_route_attached(self):
        from caddyconfig.builder import ServerBuilder
        sb = ServerBuilder(name="main")
        sb.error_route().match(host=["foo.com"]).handle_static(500).done()
        s = sb.build()
        assert len(s.errors) == 1
        assert len(s.routes) == 0

    def test_done_without_parent_raises(self):
        from caddyconfig.builder import ServerBuilder
        with pytest.raises(RuntimeError):
            ServerBuilder(name="main").done()


# ---------------------------------------------------------------------------
# CaddyConfigBuilder
# ---------------------------------------------------------------------------

class TestCaddyConfigBuilder:
    def test_build_empty(self):
        config = CaddyConfigBuilder().build()
        assert isinstance(config, CaddyConfig)
        assert config.to_dict() == {}

    def test_admin(self):
        config = CaddyConfigBuilder().admin(listen="localhost:2019").build()
        assert config.admin.listen == "localhost:2019"  # type: ignore[union-attr]

    def test_admin_disabled(self):
        assert CaddyConfigBuilder().admin(disabled=True).build().admin.disabled is True  # type: ignore[union-attr]

    def test_admin_with_origins(self):
        config = CaddyConfigBuilder().admin(enforce_origins=True, origins=["http://a.com"]).build()
        assert config.admin.origins == ["http://a.com"]  # type: ignore[union-attr]

    def test_logging(self):
        config = CaddyConfigBuilder().logging(writer="stderr", level="warn").build()
        assert config.logging.sink.writer == "stderr"  # type: ignore[union-attr]
        assert config.logging.logs["default"].level == "warn"  # type: ignore[union-attr]

    def test_logging_stdout(self):
        assert CaddyConfigBuilder().logging(writer="stdout").build().logging.sink.writer == "stdout"  # type: ignore[union-attr]

    def test_logging_extra_logs(self):
        config = CaddyConfigBuilder().logging(
            level="info",
            extra_logs={"access": {"level": "debug", "writer": "stdout"}},
        ).build()
        assert config.logging.logs["access"].level == "debug"  # type: ignore[union-attr]

    def test_single_server(self):
        config = (
            CaddyConfigBuilder()
            .server("main", listen=[":443"])
                .route().match(host=["foo.com"]).handle_static(200).done()
            .done()
            .build()
        )
        assert config.apps is not None
        server = config.apps.http.get_server("main")  # type: ignore[union-attr]
        assert server is not None
        assert ":443" in server.listen
        assert len(server.routes) == 1

    def test_multiple_servers(self):
        config = (
            CaddyConfigBuilder()
            .server("web", listen=[":443"]).done()
            .server("admin", listen=[":2020"]).done()
            .build()
        )
        assert config.apps.http.get_server("web") is not None   # type: ignore[union-attr]
        assert config.apps.http.get_server("admin") is not None  # type: ignore[union-attr]

    def test_full_config_to_dict(self):
        config = (
            CaddyConfigBuilder()
            .admin(listen="localhost:2019")
            .logging(writer="stderr", level="info")
            .server("main", listen=[":443", ":80"])
                .route().match(host=["foo.com"]).handle_reverse_proxy("10.0.0.1:8080").done()
            .done()
            .build()
        )
        d = config.to_dict()
        assert "admin" in d
        assert "logging" in d
        assert "apps" in d
        routes = d["apps"]["http"]["servers"]["main"]["routes"]
        assert routes[0]["match"][0]["host"] == ["foo.com"]
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"

    def test_chaining_returns_self(self):
        """admin() and logging() must return the same CaddyConfigBuilder instance."""
        builder = CaddyConfigBuilder()
        assert builder.admin() is builder
        assert builder.logging() is builder

    def test_builder_equivalent_to_manual(self):
        """Builder output must be identical to manual model construction."""
        from caddyconfig import Route, Server, HttpApp, Admin, Logging, LogSink, LogEntry

        manual = CaddyConfig(
            admin=Admin(listen="localhost:2019"),
            logging=Logging(
                sink=LogSink(writer="stderr"),
                logs={"default": LogEntry(name="default", level="info")},
            ),
            apps=Apps(
                http=HttpApp(
                    servers={
                        "main": Server(
                            name="main",
                            listen=[":443", ":80"],
                            routes=[
                                Route(
                                    match=[MatchCriteria(host=["foo.com"])],
                                    handle=[ReverseProxyHandler(upstreams=["10.0.0.1:80"])],
                                )
                            ],
                        )
                    }
                )
            ),
        )

        via_builder = (
            CaddyConfigBuilder()
            .admin(listen="localhost:2019")
            .logging(writer="stderr", level="info")
            .server("main", listen=[":443", ":80"])
                .route().match(host=["foo.com"]).handle_reverse_proxy("10.0.0.1:80").done()
            .done()
            .build()
        )

        assert via_builder.to_dict() == manual.to_dict()
"""
Integration tests – use cases from the specification.

Case 1 : Route for host "acme.com" on :443/:80.
         Add a reverse proxy to 192.168.0.123:8042 on /test.
         If the match already exists, update it (upsert).

Case 2 : Remove that reverse proxy.

Case 3 : Recursive navigation host → subroute path.

Plus  : full JSON roundtrip, from_json, builder ↔ model equivalence.
"""
import json

from caddyconfig import (
    CaddyConfig, Apps, Admin, Logging, LogSink, LogEntry,
    HttpApp, Server, Route, MatchCriteria,
    ReverseProxyHandler, StaticResponseHandler, SubrouteHandler,
)
from caddyconfig.builder import CaddyConfigBuilder


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def make_base_config() -> CaddyConfig:
    """
    Starting configuration:
      - admin on localhost:2019
      - logging stderr info
      - server 'main' :443/:80 with a host route for acme.com → static 200
    """
    host_route = Route(
        match=[MatchCriteria(host=["acme.com"])],
        handle=[StaticResponseHandler(status_code=200, body="Welcome")],
    )
    return CaddyConfig(
        admin=Admin(listen="localhost:2019"),
        logging=Logging(
            sink=LogSink(writer="stderr"),
            logs={"default": LogEntry(name="default", level="INFO")},
        ),
        apps=Apps(
            http=HttpApp(
                servers={
                    "main": Server(
                        name="main",
                        listen=[":443", ":80"],
                        routes=[host_route],
                    )
                }
            )
        ),
    )


# ---------------------------------------------------------------------------
# Case 1 – Add + upsert
# ---------------------------------------------------------------------------

class TestUseCase1AddReverseProxy:
    def test_host_route_exists(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        assert server.find_route(MatchCriteria(host=["acme.com"])) is not None

    def test_add_reverse_proxy(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]

        path_crit = MatchCriteria(path=["/test"])
        new_route = Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])])
        replaced = server.upsert_route(path_crit, new_route)

        assert replaced is False                    # inserted, not replaced
        assert len(server.routes) == 2
        rp = server.find_route(path_crit).get_handler("reverse_proxy")  # type: ignore[union-attr]
        assert isinstance(rp, ReverseProxyHandler)
        assert rp.upstreams[0].dial == "192.168.0.123:8042"

    def test_upsert_replaces_existing(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        path_crit = MatchCriteria(path=["/test"])

        server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])]))
        replaced = server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.200:9000"])]))

        assert replaced is True
        assert len(server.routes) == 2   # still host + /test, no duplicate
        rp = server.find_route(path_crit).get_handler("reverse_proxy")  # type: ignore[union-attr]
        assert rp.upstreams[0].dial == "192.168.0.200:9000"  # type: ignore[union-attr]

    def test_json_output_correct_after_add(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        path_crit = MatchCriteria(path=["/test"])
        server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])]))

        raw = json.loads(config.to_json())
        routes = raw["apps"]["http"]["servers"]["main"]["routes"]
        proxy_route = next(
            (r for r in routes if r.get("match", [{}])[0].get("path") == ["/test"]), None
        )
        assert proxy_route is not None
        assert proxy_route["handle"][0]["handler"] == "reverse_proxy"
        assert proxy_route["handle"][0]["upstreams"][0]["dial"] == "192.168.0.123:8042"


# ---------------------------------------------------------------------------
# Case 2 – Remove
# ---------------------------------------------------------------------------

class TestUseCase2RemoveReverseProxy:
    def _config_with_proxy(self) -> CaddyConfig:
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        path_crit = MatchCriteria(path=["/test"])
        server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])]))
        return config

    def test_remove_proxy_route(self):
        config = self._config_with_proxy()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        assert len(server.routes) == 2

        assert server.remove_route(MatchCriteria(path=["/test"])) is True
        assert len(server.routes) == 1
        assert server.find_route(MatchCriteria(path=["/test"])) is None

    def test_host_route_untouched_after_remove(self):
        config = self._config_with_proxy()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        server.remove_route(MatchCriteria(path=["/test"]))
        assert server.find_route(MatchCriteria(host=["acme.com"])) is not None

    def test_remove_nonexistent_returns_false(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        assert server.remove_route(MatchCriteria(path=["/test"])) is False

    def test_json_after_remove_has_one_route(self):
        config = self._config_with_proxy()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        server.remove_route(MatchCriteria(path=["/test"]))

        raw = json.loads(config.to_json())
        routes = raw["apps"]["http"]["servers"]["main"]["routes"]
        assert len(routes) == 1
        assert routes[0]["match"][0]["host"] == ["acme.com"]


# ---------------------------------------------------------------------------
# Case 3 – Recursive navigation host → subroute path
# ---------------------------------------------------------------------------

class TestUseCase3RecursiveNavigation:
    def _config_with_subroute(self) -> tuple[CaddyConfig, Route]:
        inner = Route(
            match=[MatchCriteria(path=["/test"])],
            handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])],
        )
        outer = Route(
            match=[MatchCriteria(host=["acme.com"])],
            handle=[SubrouteHandler(routes=[inner])],
        )
        server = Server(name="main", listen=[":443", ":80"], routes=[outer])
        config = CaddyConfig(apps=Apps(http=HttpApp(servers={"main": server})))
        return config, inner

    def test_find_outer_by_host(self):
        config, _ = self._config_with_subroute()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        outer = server.find_route(MatchCriteria(host=["acme.com"]), recursive=False)
        assert outer is not None
        assert outer.match[0].host == ["acme.com"]

    def test_find_inner_from_outer(self):
        config, inner = self._config_with_subroute()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        outer = server.find_route(MatchCriteria(host=["acme.com"]), recursive=False)
        assert outer.find_in_subroutes(MatchCriteria(path=["/test"])) is inner  # type: ignore[union-attr]

    def test_recursive_find_reaches_inner_directly(self):
        """find_route with recursive=True descends and finds /test directly."""
        config, inner = self._config_with_subroute()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        assert server.find_route(MatchCriteria(path=["/test"]), recursive=True) is inner

    def test_combined_criteria_on_same_match(self):
        """When the nested route carries both host and path on its own matcher,
        it can be reached directly with both criteria."""
        inner = Route(
            match=[MatchCriteria(host=["acme.com"], path=["/test"])],
            handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])],
        )
        outer = Route(
            match=[MatchCriteria(host=["acme.com"])],
            handle=[SubrouteHandler(routes=[inner])],
        )
        server = Server(name="main", listen=[":443", ":80"], routes=[outer])
        found = server.find_route(MatchCriteria(host=["acme.com"], path=["/test"]), recursive=True)
        assert found is inner


# ---------------------------------------------------------------------------
# Full JSON roundtrip
# ---------------------------------------------------------------------------

class TestFullJsonRoundtrip:
    def test_config_roundtrip(self):
        config = make_base_config()
        server = config.apps.http.servers["main"]  # type: ignore[union-attr]
        path_crit = MatchCriteria(path=["/test"])
        server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["192.168.0.123:8042"])]))
        assert CaddyConfig.from_json(config.to_json()).to_dict() == config.to_dict()

    def test_from_json_parses_all_sections(self):
        raw = json.dumps({
            "admin": {"listen": "localhost:2019"},
            "logging": {
                "sink": {"writer": {"output": "stderr"}},
                "logs": {"default": {"level": "INFO"}},
            },
            "apps": {
                "http": {
                    "servers": {
                        "main": {
                            "listen": [":443"],
                            "routes": [{
                                "match": [{"host": ["foo.com"]}],
                                "handle": [{"handler": "static_response", "status_code": 200}],
                            }],
                        }
                    }
                }
            },
        })
        config = CaddyConfig.from_json(raw)
        assert config.admin.listen == "localhost:2019"       # type: ignore[union-attr]
        assert config.logging.sink.writer == "stderr"        # type: ignore[union-attr]
        server = config.apps.http.get_server("main")         # type: ignore[union-attr]
        assert server.find_route(MatchCriteria(host=["foo.com"])).get_handler("static_response") is not None  # type: ignore[union-attr]

    def test_unknown_handler_preserved_in_roundtrip(self):
        raw = json.dumps({
            "apps": {"http": {"servers": {"main": {"listen": [":443"],
                "routes": [{"handle": [{"handler": "custom_plugin", "option": 42}]}]}}}}
        })
        config = CaddyConfig.from_json(raw)
        assert CaddyConfig.from_json(config.to_json()).to_dict() == config.to_dict()


# ---------------------------------------------------------------------------
# Builder ↔ model
# ---------------------------------------------------------------------------

class TestBuilderIntegration:
    def test_builder_use_case_1(self):
        """Use case 1 built entirely via the builder."""
        config = (
            CaddyConfigBuilder()
            .admin(listen="localhost:2019")
            .logging(writer="stderr", level="INFO")
            .server("main", listen=[":443", ":80"])
                .route().match(host=["acme.com"]).handle_static(200, body="Welcome").done()
                .route().match(path=["/test"]).handle_reverse_proxy("192.168.0.123:8042").done()
            .done()
            .build()
        )
        server = config.apps.http.get_server("main")  # type: ignore[union-attr]
        assert len(server.routes) == 2  # type: ignore[union-attr]
        rp = server.find_route(MatchCriteria(path=["/test"])).get_handler("reverse_proxy")  # type: ignore[union-attr]
        assert isinstance(rp, ReverseProxyHandler)
        assert rp.upstreams[0].dial == "192.168.0.123:8042"

    def test_builder_produces_valid_json(self):
        config = (
            CaddyConfigBuilder()
            .admin(listen="localhost:2019")
            .logging(writer="stderr", level="INFO")
            .server("main", listen=[":443", ":80"])
                .route().match(host=["acme.com"]).handle_reverse_proxy("192.168.0.123:8042").done()
            .done()
            .build()
        )
        raw = json.loads(config.to_json())
        assert raw["apps"]["http"]["servers"]["main"]["listen"] == [":443", ":80"]

    def test_builder_then_mutate(self):
        """Build with the builder then mutate the result directly."""
        config = (
            CaddyConfigBuilder()
            .server("main", listen=[":443"])
                .route().match(host=["foo.com"]).handle_static(200).done()
            .done()
            .build()
        )
        server = config.apps.http.get_server("main")  # type: ignore[union-attr]
        path_crit = MatchCriteria(path=["/api"])
        server.upsert_route(path_crit, Route(match=[path_crit], handle=[ReverseProxyHandler(upstreams=["10.0.0.1:80"])]))  # type: ignore[union-attr]
        assert len(server.routes) == 2  # type: ignore[union-attr]

    def test_builder_with_subroute(self):
        """Builder with nested subroute."""
        config = (
            CaddyConfigBuilder()
            .server("main", listen=[":443"])
                .route()
                    .match(host=["foo.com"])
                    .handle_subroute()
                        .route().match(path=["/api"]).handle_reverse_proxy("10.0.0.1:80").done()
                        .route().match(path=["/static"]).handle_file_server(root="/srv/static").done()
                    .done()
                .done()
            .done()
            .build()
        )
        server = config.apps.http.get_server("main")  # type: ignore[union-attr]
        outer = server.find_route(MatchCriteria(host=["foo.com"]), recursive=False)  # type: ignore[union-attr]
        assert outer.find_in_subroutes(MatchCriteria(path=["/api"])).get_handler("reverse_proxy") is not None   # type: ignore[union-attr]
        assert outer.find_in_subroutes(MatchCriteria(path=["/static"])).get_handler("file_server") is not None  # type: ignore[union-attr]
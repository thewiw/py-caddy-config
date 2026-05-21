"""Tests – Route, Server, HttpApp, Metrics."""
import pytest
from pydantic import ValidationError

from caddyconfig import (
    Route, MatchCriteria, Server, Metrics, HttpApp,
    StaticResponseHandler, ReverseProxyHandler, SubrouteHandler,
)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class TestRoute:
    def test_empty_route(self):
        assert Route().to_dict() == {}

    def test_group(self):
        assert Route(group="auth").to_dict()["group"] == "auth"

    def test_terminal_true(self):
        assert Route(terminal=True).to_dict()["terminal"] is True

    def test_terminal_false_omitted(self):
        assert "terminal" not in Route().to_dict()

    def test_match_serialised(self):
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        assert r.to_dict()["match"] == [{"host": ["foo.com"]}]

    def test_handle_serialised(self):
        r = Route(handle=[StaticResponseHandler(status_code=200)])
        assert r.to_dict()["handle"][0]["handler"] == "static_response"

    # --- _match_fits ---

    def test_match_fits_empty_both(self):
        assert Route()._match_fits(MatchCriteria()) is True

    def test_match_fits_host(self):
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        assert r._match_fits(MatchCriteria(host=["foo.com"])) is True
        assert r._match_fits(MatchCriteria(host=["bar.com"])) is False

    def test_match_fits_or_logic(self):
        """OR logic between matchers in the match list."""
        r = Route(match=[MatchCriteria(host=["foo.com"]), MatchCriteria(host=["bar.com"])])
        assert r._match_fits(MatchCriteria(host=["bar.com"])) is True

    def test_match_fits_partial_criteria(self):
        """Host-only criteria matches a route with both host and path (path is ignored)."""
        r = Route(match=[MatchCriteria(host=["foo.com"], path=["/api"])])
        assert r._match_fits(MatchCriteria(host=["foo.com"])) is True

    # --- handler management ---

    def test_add_handler(self):
        r = Route()
        r.add_handler(StaticResponseHandler(status_code=200))
        assert len(r.handle) == 1

    def test_remove_handler_found(self):
        r = Route(handle=[StaticResponseHandler(status_code=200), ReverseProxyHandler(upstreams=["a:1"])])
        assert r.remove_handler("static_response") is True
        assert len(r.handle) == 1
        assert r.handle[0].handler == "reverse_proxy"

    def test_remove_handler_not_found(self):
        assert Route().remove_handler("file_server") is False

    def test_get_handler_found(self):
        h = StaticResponseHandler(status_code=204)
        r = Route(handle=[h])
        assert r.get_handler("static_response") is h

    def test_get_handler_not_found(self):
        assert Route().get_handler("reverse_proxy") is None

    def test_replace_handler_existing(self):
        r = Route(handle=[StaticResponseHandler(status_code=200)])
        r.replace_handler(StaticResponseHandler(status_code=404))
        assert r.handle[0].status_code == 404  # type: ignore[attr-defined]

    def test_replace_handler_appends_when_absent(self):
        r = Route()
        r.replace_handler(StaticResponseHandler(status_code=200))
        assert len(r.handle) == 1

    # --- subroutes ---

    def test_find_in_subroutes(self):
        inner = Route(match=[MatchCriteria(path=["/inner"])], handle=[StaticResponseHandler(status_code=200)])
        outer = Route(match=[MatchCriteria(host=["foo.com"])], handle=[SubrouteHandler(routes=[inner])])
        assert outer.find_in_subroutes(MatchCriteria(path=["/inner"])) is inner

    def test_find_in_subroutes_not_found(self):
        outer = Route(match=[MatchCriteria(host=["foo.com"])], handle=[SubrouteHandler(routes=[])])
        assert outer.find_in_subroutes(MatchCriteria(path=["/x"])) is None

    def test_find_in_subroutes_no_subroute(self):
        r = Route(handle=[StaticResponseHandler(status_code=200)])
        assert r.find_in_subroutes(MatchCriteria(path=["/x"])) is None

    # --- serialization ---

    def test_roundtrip(self):
        r = Route(
            group="g1",
            match=[MatchCriteria(host=["foo.com"], path=["/api"])],
            handle=[StaticResponseHandler(status_code=200, body="ok")],
            terminal=True,
        )
        assert Route.from_dict(r.to_dict()).to_dict() == r.to_dict()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_per_host_true(self):
        assert Metrics(per_host=True).to_dict() == {"per_host": True}

    def test_per_host_false_empty(self):
        assert Metrics(per_host=False).to_dict() == {}


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class TestServer:
    def _server(self) -> Server:
        return Server(name="main", listen=[":443", ":80"])

    def test_listen_in_dict(self):
        assert self._server().to_dict()["listen"] == [":443", ":80"]

    def test_add_listen_deduplicates(self):
        s = self._server()
        s.add_listen(":443")
        assert s.listen.count(":443") == 1

    def test_add_listen_new(self):
        s = self._server()
        s.add_listen(":8443")
        assert ":8443" in s.listen

    def test_remove_listen_found(self):
        s = self._server()
        assert s.remove_listen(":80") is True
        assert ":80" not in s.listen

    def test_remove_listen_not_found(self):
        assert self._server().remove_listen(":9999") is False

    def test_invalid_listen_raises(self):
        with pytest.raises(ValidationError):
            Server(name="main", listen=[""])

    def test_find_route_direct(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        s.routes.append(r)
        assert s.find_route(MatchCriteria(host=["foo.com"])) is r

    def test_find_route_not_found(self):
        assert self._server().find_route(MatchCriteria(host=["nobody.com"])) is None

    def test_find_route_recursive_into_subroute(self):
        inner = Route(match=[MatchCriteria(path=["/api"])], handle=[StaticResponseHandler(status_code=200)])
        outer = Route(match=[MatchCriteria(host=["foo.com"])], handle=[SubrouteHandler(routes=[inner])])
        s = self._server()
        s.routes.append(outer)
        assert s.find_route(MatchCriteria(path=["/api"]), recursive=True) is inner

    def test_find_route_non_recursive(self):
        """Without recursion, nested routes must not be returned."""
        inner = Route(match=[MatchCriteria(path=["/api"])], handle=[])
        outer = Route(match=[MatchCriteria(host=["foo.com"])], handle=[SubrouteHandler(routes=[inner])])
        s = self._server()
        s.routes.append(outer)
        assert s.find_route(MatchCriteria(path=["/api"]), recursive=False) is None

    def test_find_route_in_errors(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        s.errors.append(r)
        assert s.find_route(MatchCriteria(host=["foo.com"]), error=True) is r
        assert s.find_route(MatchCriteria(host=["foo.com"]), error=False) is None

    def test_upsert_inserts_when_absent(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])], handle=[StaticResponseHandler(status_code=200)])
        assert s.upsert_route(MatchCriteria(host=["foo.com"]), r) is False
        assert len(s.routes) == 1

    def test_upsert_replaces_when_present(self):
        s = self._server()
        r1 = Route(match=[MatchCriteria(host=["foo.com"])], handle=[StaticResponseHandler(status_code=200)])
        r2 = Route(match=[MatchCriteria(host=["foo.com"])], handle=[StaticResponseHandler(status_code=404)])
        s.routes.append(r1)
        assert s.upsert_route(MatchCriteria(host=["foo.com"]), r2) is True
        assert len(s.routes) == 1
        assert s.routes[0].handle[0].status_code == 404  # type: ignore[attr-defined]

    def test_upsert_no_duplicate(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])], handle=[StaticResponseHandler(status_code=200)])
        s.upsert_route(MatchCriteria(host=["foo.com"]), r)
        s.upsert_route(MatchCriteria(host=["foo.com"]), r)
        assert len(s.routes) == 1

    def test_remove_route_found(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        s.routes.append(r)
        assert s.remove_route(MatchCriteria(host=["foo.com"])) is True
        assert len(s.routes) == 0

    def test_remove_route_not_found(self):
        assert self._server().remove_route(MatchCriteria(host=["nobody.com"])) is False

    def test_remove_route_in_errors(self):
        s = self._server()
        r = Route(match=[MatchCriteria(host=["foo.com"])])
        s.errors.append(r)
        assert s.remove_route(MatchCriteria(host=["foo.com"]), error=True) is True

    def test_routes_in_group(self):
        s = self._server()
        s.routes.append(Route(group="auth", match=[MatchCriteria(host=["a.com"])]))
        s.routes.append(Route(group="auth", match=[MatchCriteria(path=["/login"])]))
        s.routes.append(Route(match=[MatchCriteria(path=["/public"])]))
        assert len(s.routes_in_group("auth")) == 2

    def test_remove_group(self):
        s = self._server()
        s.routes.append(Route(group="auth"))
        s.routes.append(Route(group="auth"))
        s.routes.append(Route(group="other"))
        assert s.remove_group("auth") == 2
        assert len(s.routes) == 1

    def test_metrics_in_dict(self):
        s = Server(name="main", metrics=Metrics(per_host=True))
        assert s.to_dict()["metrics"] == {"per_host": True}

    def test_metrics_false_omitted(self):
        assert "metrics" not in Server(name="main", metrics=Metrics(per_host=False)).to_dict()

    def test_metrics_none_omitted(self):
        assert "metrics" not in Server(name="main").to_dict()

    def test_name_excluded_from_dict(self):
        assert "name" not in Server(name="main").to_dict()

    def test_roundtrip(self):
        s = Server(
            name="main",
            listen=[":443"],
            routes=[Route(match=[MatchCriteria(host=["foo.com"])], handle=[StaticResponseHandler(status_code=200)])],
            metrics=Metrics(per_host=True),
        )
        assert Server.from_dict("main", s.to_dict()).to_dict() == s.to_dict()


# ---------------------------------------------------------------------------
# HttpApp
# ---------------------------------------------------------------------------

class TestHttpApp:
    def test_add_get_server(self):
        app = HttpApp()
        s = Server(name="main", listen=[":443"])
        app.add_server(s)
        assert app.get_server("main") is s

    def test_remove_server_found(self):
        app = HttpApp()
        app.add_server(Server(name="main"))
        assert app.remove_server("main") is True
        assert app.get_server("main") is None

    def test_remove_server_not_found(self):
        assert HttpApp().remove_server("ghost") is False

    def test_optional_ports(self):
        d = HttpApp(http_port=8080, https_port=8443).to_dict()
        assert d["http_port"] == 8080
        assert d["https_port"] == 8443

    def test_optional_ports_omitted_when_none(self):
        d = HttpApp().to_dict()
        assert "http_port" not in d
        assert "https_port" not in d

    def test_roundtrip(self):
        app = HttpApp(servers={"main": Server(name="main", listen=[":443"])}, http_port=80)
        assert HttpApp.from_dict(app.to_dict()).to_dict() == app.to_dict()
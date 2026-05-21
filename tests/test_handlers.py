"""Tests – Handlers (FileServer, ReverseProxy, StaticResponse, Authentication, Subroute)."""
import pytest
from pydantic import ValidationError

from caddyconfig import (
    FileServerHandler,
    ReverseProxyHandler,
    UpstreamAddress,
    StaticResponseHandler,
    AuthenticationHandler,
    HttpBasicCredential,
    SubrouteHandler,
    Route,
    MatchCriteria,
    RawHandler,
    handler_from_dict,
)


# ---------------------------------------------------------------------------
# FileServerHandler
# ---------------------------------------------------------------------------

class TestFileServerHandler:
    def test_minimal(self):
        assert FileServerHandler().to_dict() == {"handler": "file_server"}

    def test_root_included(self):
        assert FileServerHandler(root="/var/www").to_dict()["root"] == "/var/www"

    def test_browse_as_empty_dict(self):
        assert FileServerHandler(browse=True).to_dict()["browse"] == {}

    def test_browse_false_omitted(self):
        assert "browse" not in FileServerHandler(browse=False).to_dict()

    def test_pass_thru(self):
        assert FileServerHandler(pass_thru=True).to_dict()["pass_thru"] is True

    def test_pass_thru_false_omitted(self):
        assert "pass_thru" not in FileServerHandler().to_dict()

    def test_hide_and_index(self):
        h = FileServerHandler(hide=[".git"], index_names=["index.html"])
        d = h.to_dict()
        assert d["hide"] == [".git"]
        assert d["index_names"] == ["index.html"]

    def test_empty_hide_omitted(self):
        assert "hide" not in FileServerHandler().to_dict()

    def test_roundtrip(self):
        h = FileServerHandler(root="/srv", browse=True, hide=[".env"], pass_thru=True)
        assert FileServerHandler.from_dict(h.to_dict()).to_dict() == h.to_dict()

    def test_handler_from_dict_dispatch(self):
        h = handler_from_dict({"handler": "file_server", "root": "/srv"})
        assert isinstance(h, FileServerHandler)
        assert h.root == "/srv"


# ---------------------------------------------------------------------------
# UpstreamAddress
# ---------------------------------------------------------------------------

class TestUpstreamAddress:
    @pytest.mark.parametrize("dial", [
        "192.168.0.1:8080",
        "host.example.com:443",
        ":8080",
        "[::1]:9000",
        "unix///run/app.sock",
    ])
    def test_valid_dials(self, dial: str):
        assert UpstreamAddress(dial=dial).dial == dial

    @pytest.mark.parametrize("dial", [
        "no-port",
        "host:99999",
        "",
        "host:",
    ])
    def test_invalid_dials(self, dial: str):
        with pytest.raises(ValidationError, match="dial"):
            UpstreamAddress(dial=dial)


# ---------------------------------------------------------------------------
# ReverseProxyHandler
# ---------------------------------------------------------------------------

class TestReverseProxyHandler:
    def test_string_upstreams_coerced(self):
        h = ReverseProxyHandler(upstreams=["10.0.0.1:80"])
        assert h.upstreams[0].dial == "10.0.0.1:80"

    def test_to_dict_structure(self):
        h = ReverseProxyHandler(upstreams=["10.0.0.1:80"])
        d = h.to_dict()
        assert d["handler"] == "reverse_proxy"
        assert d["upstreams"] == [{"dial": "10.0.0.1:80"}]

    def test_optional_fields_omitted(self):
        d = ReverseProxyHandler(upstreams=["a:1"]).to_dict()
        assert "headers" not in d
        assert "transport" not in d

    def test_headers_included(self):
        h = ReverseProxyHandler(
            upstreams=["a:1"],
            headers={"request": {"set": {"X-Real-IP": ["{remote_host}"]}}},
        )
        assert "headers" in h.to_dict()

    def test_add_upstream_deduplicates(self):
        h = ReverseProxyHandler(upstreams=["a:1"])
        h.add_upstream("a:1")
        assert len(h.upstreams) == 1

    def test_add_upstream_new(self):
        h = ReverseProxyHandler()
        h.add_upstream("b:2")
        assert h.upstreams[0].dial == "b:2"

    def test_remove_upstream_found(self):
        h = ReverseProxyHandler(upstreams=["a:1", "b:2"])
        assert h.remove_upstream("a:1") is True
        assert len(h.upstreams) == 1
        assert h.upstreams[0].dial == "b:2"

    def test_remove_upstream_not_found(self):
        h = ReverseProxyHandler(upstreams=["a:1"])
        assert h.remove_upstream("x:9") is False

    def test_invalid_upstream_raises(self):
        with pytest.raises(ValidationError):
            ReverseProxyHandler(upstreams=["not-valid"])

    def test_roundtrip(self):
        h = ReverseProxyHandler(
            upstreams=["10.0.0.1:8080", "10.0.0.2:8080"],
            headers={"request": {"set": {"Host": ["{upstream_hostport}"]}}},
        )
        assert ReverseProxyHandler.from_dict(h.to_dict()).to_dict() == h.to_dict()

    def test_handler_from_dict_dispatch(self):
        h = handler_from_dict({"handler": "reverse_proxy", "upstreams": [{"dial": "a:1"}]})
        assert isinstance(h, ReverseProxyHandler)


# ---------------------------------------------------------------------------
# StaticResponseHandler
# ---------------------------------------------------------------------------

class TestStaticResponseHandler:
    def test_minimal(self):
        assert StaticResponseHandler().to_dict() == {"handler": "static_response"}

    def test_status_code(self):
        assert StaticResponseHandler(status_code=200).to_dict()["status_code"] == 200

    def test_status_code_boundary_valid(self):
        StaticResponseHandler(status_code=100)
        StaticResponseHandler(status_code=599)

    def test_status_code_out_of_range(self):
        with pytest.raises(ValidationError):
            StaticResponseHandler(status_code=99)
        with pytest.raises(ValidationError):
            StaticResponseHandler(status_code=600)

    def test_body_included(self):
        assert StaticResponseHandler(body="OK").to_dict()["body"] == "OK"

    def test_close_true(self):
        assert StaticResponseHandler(close=True).to_dict()["close"] is True

    def test_close_false_omitted(self):
        assert "close" not in StaticResponseHandler().to_dict()

    def test_headers(self):
        h = StaticResponseHandler(
            status_code=301,
            headers={"Location": ["https://new.example.com"]},
        )
        assert h.to_dict()["headers"]["Location"] == ["https://new.example.com"]

    def test_roundtrip(self):
        h = StaticResponseHandler(status_code=200, body="hello", close=True)
        assert StaticResponseHandler.from_dict(h.to_dict()).to_dict() == h.to_dict()

    def test_handler_from_dict_dispatch(self):
        h = handler_from_dict({"handler": "static_response", "status_code": 204})
        assert isinstance(h, StaticResponseHandler)
        assert h.status_code == 204


# ---------------------------------------------------------------------------
# HttpBasicCredential
# ---------------------------------------------------------------------------

class TestHttpBasicCredential:
    def test_valid(self):
        c = HttpBasicCredential(username="alice", password="$2a$hash")
        d = c.to_dict()
        assert d["username"] == "alice"
        assert d["algorithm"] == {"algorithm": "bcrypt"}

    def test_empty_username_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            HttpBasicCredential(username="", password="pw")

    def test_empty_password_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            HttpBasicCredential(username="u", password="")

    def test_blank_username_raises(self):
        with pytest.raises(ValidationError):
            HttpBasicCredential(username="   ", password="pw")

    def test_algorithm_scrypt(self):
        c = HttpBasicCredential(username="u", password="p", algorithm="scrypt")
        assert c.to_dict()["algorithm"] == {"algorithm": "scrypt"}

    def test_invalid_algorithm_raises(self):
        with pytest.raises(ValidationError):
            HttpBasicCredential(username="u", password="p", algorithm="md5")  # type: ignore

    def test_roundtrip(self):
        c = HttpBasicCredential(username="bob", password="hash", algorithm="bcrypt")
        c2 = HttpBasicCredential.from_dict(c.to_dict())
        assert c2.username == "bob"
        assert c2.algorithm == "bcrypt"


# ---------------------------------------------------------------------------
# AuthenticationHandler
# ---------------------------------------------------------------------------

class TestAuthenticationHandler:
    def test_structure(self):
        h = AuthenticationHandler(
            realm="Admin",
            credentials=[HttpBasicCredential(username="u", password="p")],
        )
        d = h.to_dict()
        assert d["handler"] == "authentication"
        assert d["providers"]["http_basic"]["realm"] == "Admin"
        assert d["providers"]["http_basic"]["accounts"][0]["username"] == "u"

    def test_no_realm_omitted(self):
        assert "realm" not in AuthenticationHandler().to_dict()["providers"]["http_basic"]

    def test_hash_cache_true(self):
        assert "hash_cache" in AuthenticationHandler(hash_cache=True).to_dict()["providers"]["http_basic"]

    def test_hash_cache_false_omitted(self):
        assert "hash_cache" not in AuthenticationHandler(hash_cache=False).to_dict()["providers"]["http_basic"]

    def test_add_credential_replaces_same_username(self):
        h = AuthenticationHandler()
        h.add_credential(HttpBasicCredential(username="alice", password="old"))
        h.add_credential(HttpBasicCredential(username="alice", password="new"))
        assert len(h.credentials) == 1
        assert h.credentials[0].password == "new"

    def test_remove_credential_found(self):
        h = AuthenticationHandler(
            credentials=[HttpBasicCredential(username="bob", password="pw")]
        )
        assert h.remove_credential("bob") is True
        assert h.credentials == []

    def test_remove_credential_not_found(self):
        assert AuthenticationHandler().remove_credential("nobody") is False

    def test_roundtrip(self):
        h = AuthenticationHandler(
            realm="Secure",
            credentials=[HttpBasicCredential(username="u", password="h")],
            hash_cache=True,
        )
        assert AuthenticationHandler.from_dict(h.to_dict()).to_dict() == h.to_dict()

    def test_handler_from_dict_dispatch(self):
        raw = {"handler": "authentication", "providers": {"http_basic": {"accounts": []}}}
        assert isinstance(handler_from_dict(raw), AuthenticationHandler)


# ---------------------------------------------------------------------------
# SubrouteHandler
# ---------------------------------------------------------------------------

class TestSubrouteHandler:
    def _route(self, path: str) -> Route:
        return Route(
            match=[MatchCriteria(path=[path])],
            handle=[StaticResponseHandler(status_code=200)],
        )

    def test_add_and_find(self):
        sub = SubrouteHandler()
        r = self._route("/api")
        sub.add_route(r)
        assert sub.find_route(MatchCriteria(path=["/api"])) is r

    def test_find_not_found(self):
        assert SubrouteHandler().find_route(MatchCriteria(path=["/x"])) is None

    def test_remove_route_found(self):
        sub = SubrouteHandler()
        sub.add_route(self._route("/api"))
        assert sub.remove_route(MatchCriteria(path=["/api"])) is True
        assert sub.find_route(MatchCriteria(path=["/api"])) is None

    def test_remove_route_not_found(self):
        assert SubrouteHandler().remove_route(MatchCriteria(path=["/x"])) is False

    def test_upsert_inserts_when_absent(self):
        sub = SubrouteHandler()
        r = self._route("/api")
        assert sub.upsert_route(MatchCriteria(path=["/api"]), r) is False
        assert len(sub.routes) == 1

    def test_upsert_replaces_when_present(self):
        sub = SubrouteHandler()
        sub.add_route(self._route("/api"))
        r2 = Route(
            match=[MatchCriteria(path=["/api"])],
            handle=[StaticResponseHandler(status_code=404)],
        )
        assert sub.upsert_route(MatchCriteria(path=["/api"]), r2) is True
        assert sub.routes[0].handle[0].status_code == 404  # type: ignore[attr-defined]

    def test_error_routes_separate(self):
        sub = SubrouteHandler()
        r = self._route("/err")
        sub.add_route(r, error=True)
        assert sub.find_route(MatchCriteria(path=["/err"])) is None
        assert sub.find_route(MatchCriteria(path=["/err"]), error=True) is r

    def test_to_dict_structure(self):
        d = SubrouteHandler(routes=[self._route("/x")]).to_dict()
        assert d["handler"] == "subroute"
        assert len(d["routes"]) == 1

    def test_roundtrip(self):
        sub = SubrouteHandler(routes=[self._route("/x"), self._route("/y")])
        assert SubrouteHandler.from_dict(sub.to_dict()).to_dict() == sub.to_dict()

    def test_handler_from_dict_dispatch(self):
        assert isinstance(handler_from_dict({"handler": "subroute", "routes": []}), SubrouteHandler)


# ---------------------------------------------------------------------------
# RawHandler (unknown types)
# ---------------------------------------------------------------------------

class TestRawHandler:
    def test_unknown_type_preserved(self):
        raw = {"handler": "custom_plugin", "option": 42, "nested": {"key": "val"}}
        h = handler_from_dict(raw)
        assert isinstance(h, RawHandler)
        assert h.to_dict()["option"] == 42
        assert h.to_dict()["nested"] == {"key": "val"}

    def test_handler_type_preserved(self):
        h = handler_from_dict({"handler": "unknown_type"})
        assert h.handler == "unknown_type"
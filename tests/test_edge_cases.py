"""
Edge-case tests for null handling, key-presence bugs, JSON shape,
empty nested object preservation, and RawHandler serialization.
"""
import pytest
from pydantic import ValidationError

from caddyconfig import (
    CaddyConfig,
    Admin,
    Logging,
    LogSink,
    LogEntry,
    Apps,
    HttpApp,
    Server,
    Metrics,
    Route,
    MatchCriteria,
)
from caddyconfig.handlers import RawHandler, handler_from_dict
from caddyconfig.handlers.file_server import FileServerHandler
from caddyconfig.handlers.authentication import (
    AuthenticationHandler,
    HttpBasicCredential,
)
from caddyconfig.handlers.subroute import SubrouteHandler
from caddyconfig.handlers.static_response import StaticResponseHandler


# ---------------------------------------------------------------------------
# Null handling in from_dict
# ---------------------------------------------------------------------------

class TestNullHandlingInFromDict:
    def test_caddyconfig_admin_null(self):
        """"admin": null should be treated as absent."""
        config = CaddyConfig.from_dict({"admin": None})
        assert config.admin is None

    def test_caddyconfig_logging_null(self):
        config = CaddyConfig.from_dict({"logging": None})
        assert config.logging is None

    def test_caddyconfig_apps_null(self):
        config = CaddyConfig.from_dict({"apps": None})
        assert config.apps is None

    def test_server_metrics_null(self):
        server = Server.from_dict("main", {"metrics": None})
        assert server.metrics is None

    def test_httpapp_servers_null(self):
        app = HttpApp.from_dict({"servers": None})
        assert app.servers == {}

    def test_route_match_null(self):
        route = Route.from_dict({"match": None})
        assert route.match == []

    def test_route_handle_null(self):
        route = Route.from_dict({"handle": None})
        assert route.handle == []

    def test_matchcriteria_not_null(self):
        mc = MatchCriteria.from_dict({"not": None})
        assert mc.not_ is None

    def test_logsink_writer_null(self):
        sink = LogSink.from_dict({"writer": None})
        assert sink.writer == "stderr"

    def test_logging_sink_null(self):
        logging = Logging.from_dict({"sink": None})
        assert logging.sink is None

    def test_logging_logs_null(self):
        logging = Logging.from_dict({"logs": None})
        assert logging.logs == {}

    def test_authentication_providers_null(self):
        auth = AuthenticationHandler.from_dict(
            {"handler": "authentication", "providers": None}
        )
        assert auth.credentials == []
        assert auth.hash_cache is False


# ---------------------------------------------------------------------------
# Key-presence bugs (browse, hash_cache)
# ---------------------------------------------------------------------------

class TestKeyPresenceBugs:
    def test_fileserver_browse_false(self):
        """"browse": false must deserialize as False, not True."""
        handler = FileServerHandler.from_dict(
            {"handler": "file_server", "browse": False}
        )
        assert handler.browse is False
        assert "browse" not in handler.to_dict()

    def test_fileserver_browse_empty_dict(self):
        """"browse": {} means browse is enabled."""
        handler = FileServerHandler.from_dict(
            {"handler": "file_server", "browse": {}}
        )
        assert handler.browse is True
        assert "browse" in handler.to_dict()

    def test_fileserver_browse_true(self):
        handler = FileServerHandler.from_dict(
            {"handler": "file_server", "browse": True}
        )
        assert handler.browse is True

    def test_auth_hash_cache_false(self):
        """"hash_cache": false must deserialize as False."""
        handler = AuthenticationHandler.from_dict({
            "handler": "authentication",
            "providers": {
                "http_basic": {
                    "accounts": [],
                    "hash_cache": False,
                }
            },
        })
        assert handler.hash_cache is False
        assert "hash_cache" not in handler.to_dict()["providers"]["http_basic"]

    def test_auth_hash_cache_empty_dict(self):
        """"hash_cache": {} means hash_cache is enabled."""
        handler = AuthenticationHandler.from_dict({
            "handler": "authentication",
            "providers": {
                "http_basic": {
                    "accounts": [],
                    "hash_cache": {},
                }
            },
        })
        assert handler.hash_cache is True
        assert "hash_cache" in handler.to_dict()["providers"]["http_basic"]


# ---------------------------------------------------------------------------
# HttpBasicCredential JSON shape
# ---------------------------------------------------------------------------

class TestHttpBasicCredentialJsonShape:
    def test_algorithm_plain_string(self):
        """algorithm must be a plain string in JSON, not a nested dict."""
        c = HttpBasicCredential(username="u", password="p", algorithm="bcrypt")
        d = c.to_dict()
        assert d["algorithm"] == "bcrypt"
        assert isinstance(d["algorithm"], str)

    def test_algorithm_roundtrip_from_real_caddy_json(self):
        """Real Caddy uses plain string for algorithm."""
        d = {"username": "u", "password": "p", "algorithm": "scrypt"}
        c = HttpBasicCredential.from_dict(d)
        assert c.algorithm == "scrypt"
        assert c.to_dict()["algorithm"] == "scrypt"


# ---------------------------------------------------------------------------
# RawHandler exclude_none
# ---------------------------------------------------------------------------

class TestRawHandlerSerialization:
    def test_extra_none_fields_omitted(self):
        """RawHandler should not emit None values in extra fields."""
        handler = handler_from_dict(
            {"handler": "unknown_type", "foo": "bar", "baz": None}
        )
        d = handler.to_dict()
        assert d["foo"] == "bar"
        assert "baz" not in d


# ---------------------------------------------------------------------------
# Empty nested object preservation
# ---------------------------------------------------------------------------

class TestEmptyNestedObjectPreservation:
    def test_caddyconfig_admin_preserved(self):
        config = CaddyConfig(admin=Admin())
        d = config.to_dict()
        assert "admin" in d
        assert d["admin"] == {}

    def test_caddyconfig_logging_preserved(self):
        config = CaddyConfig(logging=Logging())
        d = config.to_dict()
        assert "logging" in d
        assert d["logging"] == {}

    def test_caddyconfig_apps_preserved(self):
        config = CaddyConfig(apps=Apps())
        d = config.to_dict()
        assert "apps" in d
        assert d["apps"] == {}

    def test_apps_http_preserved(self):
        apps = Apps(http=HttpApp())
        d = apps.to_dict()
        assert "http" in d
        assert d["http"] == {}

    def test_server_metrics_preserved(self):
        server = Server(name="main", metrics=Metrics(per_host=False))
        d = server.to_dict()
        assert "metrics" in d
        assert d["metrics"] == {}


# ---------------------------------------------------------------------------
# MatchCriteria "not" alias
# ---------------------------------------------------------------------------

class TestMatchCriteriaNotAlias:
    def test_not_alias_from_dict(self):
        mc = MatchCriteria.from_dict({"not": [{"host": ["evil.com"]}]})
        assert mc.not_ is not None
        assert mc.not_[0].host == ["evil.com"]

    def test_not_alias_to_dict(self):
        mc = MatchCriteria(not_=[MatchCriteria(host=["evil.com"])])
        d = mc.to_dict()
        assert "not" in d
        assert "not_" not in d


# ---------------------------------------------------------------------------
# Full roundtrip with null values
# ---------------------------------------------------------------------------

class TestFullRoundtripWithNulls:
    def test_caddyconfig_roundtrip_with_nulls(self):
        original = CaddyConfig.from_dict({
            "admin": None,
            "logging": None,
            "apps": {
                "http": {
                    "servers": {
                        "main": {
                            "listen": [":443"],
                            "routes": [
                                {
                                    "match": None,
                                    "handle": [
                                        {"handler": "static_response", "status_code": 200}
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
        })
        d = original.to_dict()
        restored = CaddyConfig.from_dict(d)
        assert restored.admin is None
        assert restored.logging is None
        server = restored.apps.http.servers["main"]
        assert server.listen == [":443"]
        route = server.routes[0]
        assert route.match == []
        assert route.handle[0].handler == "static_response"

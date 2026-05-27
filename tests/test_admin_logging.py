"""Tests – Admin and Logging."""
import pytest
from pydantic import ValidationError

from caddyconfig import Admin, Logging, LogSink, LogEntry


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class TestAdmin:
    def test_default_serializes_empty(self):
        assert Admin().to_dict() == {}

    def test_listen_only(self):
        assert Admin(listen="localhost:2019").to_dict() == {"listen": "localhost:2019"}

    def test_disabled_true(self):
        assert Admin(disabled=True).to_dict()["disabled"] is True

    def test_disabled_false_omitted(self):
        assert "disabled" not in Admin(disabled=False).to_dict()

    def test_enforce_origins_true(self):
        d = Admin(enforce_origins=True).to_dict()
        assert d["enforce_origins"] is True

    def test_enforce_origins_false_omitted(self):
        assert "enforce_origins" not in Admin(enforce_origins=False).to_dict()

    def test_origins_present_when_non_empty(self):
        d = Admin(origins=["http://a.com"]).to_dict()
        assert d["origins"] == ["http://a.com"]

    def test_origins_omitted_when_empty(self):
        assert "origins" not in Admin().to_dict()

    def test_add_origin_deduplicates(self):
        a = Admin()
        a.add_origin("http://x.com")
        a.add_origin("http://x.com")
        assert a.origins == ["http://x.com"]

    def test_remove_origin_found(self):
        a = Admin(origins=["http://a.com", "http://b.com"])
        assert a.remove_origin("http://a.com") is True
        assert a.origins == ["http://b.com"]

    def test_remove_origin_not_found(self):
        assert Admin().remove_origin("http://missing.com") is False

    def test_roundtrip(self):
        a = Admin(disabled=True, listen=":2019", enforce_origins=True, origins=["http://x.com"])
        a2 = Admin.from_dict(a.to_dict())
        assert a2.to_dict() == a.to_dict()

    def test_full_roundtrip_via_json(self):
        a = Admin(listen="localhost:2019", origins=["http://a.com"])
        assert Admin.from_json(a.to_json()).to_dict() == a.to_dict()


# ---------------------------------------------------------------------------
# LogSink
# ---------------------------------------------------------------------------

class TestLogSink:
    def test_stderr_default(self):
        assert LogSink().to_dict() == {"writer": {"output": "stderr"}}

    def test_stdout(self):
        assert LogSink(writer="stdout").to_dict() == {"writer": {"output": "stdout"}}

    def test_invalid_writer_raises(self):
        with pytest.raises(ValidationError, match="stderr|stdout"):
            LogSink(writer="file")  # type: ignore[arg-type]

    def test_roundtrip(self):
        s = LogSink(writer="stdout")
        assert LogSink.from_dict(s.to_dict()).writer == "stdout"


# ---------------------------------------------------------------------------
# LogEntry
# ---------------------------------------------------------------------------

class TestLogEntry:
    def test_level_only(self):
        e = LogEntry(name="default", level="WARN")
        assert e.to_dict() == {"level": "WARN"}

    def test_writer_included(self):
        e = LogEntry(name="access", level="INFO", writer="stdout")
        assert e.to_dict()["writer"] == {"output": "stdout"}

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError):
            LogEntry(name="x", level="verbose")  # type: ignore[arg-type]

    def test_invalid_writer_raises(self):
        with pytest.raises(ValidationError):
            LogEntry(name="x", writer="file")  # type: ignore[arg-type]

    def test_name_excluded_from_dict(self):
        assert "name" not in LogEntry(name="default", level="INFO").to_dict()

    def test_roundtrip(self):
        e = LogEntry(name="access", level="DEBUG", writer="stderr")
        e2 = LogEntry.from_dict("access", e.to_dict())
        assert e2.level == "DEBUG"
        assert e2.writer == "stderr"
        assert e2.name == "access"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class TestLogging:
    def test_empty(self):
        assert Logging().to_dict() == {}

    def test_sink_included(self):
        lg = Logging(sink=LogSink(writer="stderr"))
        assert "sink" in lg.to_dict()

    def test_set_get_log(self):
        lg = Logging()
        e = LogEntry(name="app", level="INFO")
        lg.set_log(e)
        assert lg.get_log("app") is e

    def test_set_log_replaces(self):
        lg = Logging()
        lg.set_log(LogEntry(name="app", level="INFO"))
        lg.set_log(LogEntry(name="app", level="ERROR"))
        assert lg.logs["app"].level == "ERROR"

    def test_remove_log_found(self):
        lg = Logging()
        lg.set_log(LogEntry(name="app", level="INFO"))
        assert lg.remove_log("app") is True
        assert lg.get_log("app") is None

    def test_remove_log_not_found(self):
        assert Logging().remove_log("missing") is False

    def test_roundtrip(self):
        lg = Logging(
            sink=LogSink(writer="stderr"),
            logs={"default": LogEntry(name="default", level="WARN")},
        )
        lg2 = Logging.from_dict(lg.to_dict())
        assert lg2.to_dict() == lg.to_dict()
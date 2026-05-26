"""
Logging section – https://caddyserver.com/docs/json/logging/

Scope: stderr/stdout sink, log level per named logger.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import CaddyModel

WriterOutput = Literal["stderr", "stdout"]
LogLevel = Literal["debug", "info", "warn", "error", "panic", "fatal"]


class LogSink(CaddyModel):
    """
    ``logging > sink`` – shared output for all loggers.

    Attributes
    ----------
    writer : "stderr" | "stdout"
    """

    writer: WriterOutput = "stderr"

    def to_dict(self) -> dict[str, Any]:
        return {"writer": {"output": self.writer}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogSink":
        writer_data = data.get("writer")
        writer = writer_data.get("output", "stderr") if isinstance(writer_data, dict) else "stderr"
        return cls(writer=writer)


class LogEntry(CaddyModel):
    """
    Entry in ``logging > logs``.

    Attributes
    ----------
    name : str
        Logger key (e.g. ``"default"``).
    level : LogLevel | None
    writer : "stderr" | "stdout" | None
        If absent, inherits from the global sink.
    """

    # ``name`` is the dict key in Caddy JSON, not an inline field.
    name: str = Field(exclude=True)
    level: Optional[LogLevel] = None
    writer: Optional[WriterOutput] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.level is not None:
            d["level"] = self.level
        if self.writer is not None:
            d["writer"] = {"output": self.writer}
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "LogEntry":  # type: ignore[override]
        writer_block = data.get("writer")
        writer = writer_block.get("output") if isinstance(writer_block, dict) else None
        return cls(name=name, level=data.get("level"), writer=writer)


class Logging(CaddyModel):
    """
    ``logging`` block of the Caddy configuration.

    Attributes
    ----------
    sink : LogSink | None
    logs : dict[str, LogEntry]
    """

    sink: Optional[LogSink] = None
    logs: dict[str, LogEntry] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_log(self, entry: LogEntry) -> None:
        self.logs[entry.name] = entry

    def remove_log(self, name: str) -> bool:
        if name in self.logs:
            del self.logs[name]
            return True
        return False

    def get_log(self, name: str) -> Optional[LogEntry]:
        return self.logs.get(name)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.sink is not None:
            d["sink"] = self.sink.to_dict()
        if self.logs:
            d["logs"] = {name: entry.to_dict() for name, entry in self.logs.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Logging":  # type: ignore[override]
        sink_data = data.get("sink")
        sink = LogSink.from_dict(sink_data) if isinstance(sink_data, dict) else None
        logs_data = data.get("logs") or {}
        logs = {
            name: LogEntry.from_dict(name, entry)
            for name, entry in logs_data.items()
        }
        return cls(sink=sink, logs=logs)

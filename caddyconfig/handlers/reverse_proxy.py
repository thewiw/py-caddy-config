"""
Handler ``reverse_proxy`` – https://caddyserver.com/docs/json/apps/http/servers/routes/handle/reverse_proxy/
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import Field, field_validator

from . import HandlerBase, register_handler
from ..base import CaddyModel

# Validates host:port, [ipv6]:port, :port, unix//path
# Port: 1-65535 (max 5 digits, but range is validated by the validator)
_DIAL_RE = re.compile(
    r"^("
    r"unix//.+"                                      # unix socket
    r"|:([1-9]\d{0,4})"                              # port only
    r"|\[.+\]:([1-9]\d{0,4})"                        # [IPv6]:port
    r"|[a-zA-Z0-9._\-]+:([1-9]\d{0,4})"             # host:port
    r")$"
)


class UpstreamAddress(CaddyModel):
    """Address of an upstream (``dial``)."""

    dial: str

    @field_validator("dial")
    @classmethod
    def dial_format(cls, v: str) -> str:
        if not _DIAL_RE.match(v):
            raise ValueError(
                f"Invalid dial format: {v!r}. "
                "Expected: host:port, [ipv6]:port, :port or unix//path"
            )
        # Numeric port verification (1-65535)
        if not v.startswith("unix//"):
            port_str = v.rsplit(":", 1)[-1]
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError(
                    f"Port out of range (1-65535): {port}"
                )
        return v

    def to_dict(self) -> dict[str, Any]:
        return {"dial": self.dial}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpstreamAddress":
        return cls(dial=data["dial"])


@register_handler("reverse_proxy")
class ReverseProxyHandler(HandlerBase):
    """
    Forwards requests to one or more upstreams.

    Attributes
    ----------
    upstreams : list[UpstreamAddress]
        Destinations (format ``host:port``).
    headers : dict | None
        Header manipulation.
    transport : dict | None
        HTTP transport configuration.
    health_checks : dict | None
    load_balancing : dict | None
    """

    handler: str = "reverse_proxy"
    upstreams: list[UpstreamAddress] = Field(default_factory=list)
    headers: Optional[dict[str, Any]] = None
    transport: Optional[dict[str, Any]] = None
    health_checks: Optional[dict[str, Any]] = None
    load_balancing: Optional[dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Convenience constructor: accepts str or UpstreamAddress
    # ------------------------------------------------------------------

    @field_validator("upstreams", mode="before")
    @classmethod
    def coerce_upstreams(cls, v: Any) -> Any:
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"dial": item})
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_upstream(self, dial: str) -> None:
        """Adds an upstream (ignored if already present)."""
        if not any(u.dial == dial for u in self.upstreams):
            self.upstreams.append(UpstreamAddress(dial=dial))

    def remove_upstream(self, dial: str) -> bool:
        before = len(self.upstreams)
        self.upstreams = [u for u in self.upstreams if u.dial != dial]
        return len(self.upstreams) < before

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "handler": self.handler,
            "upstreams": [u.to_dict() for u in self.upstreams],
        }
        if self.headers:
            d["headers"] = self.headers
        if self.transport:
            d["transport"] = self.transport
        if self.health_checks:
            d["health_checks"] = self.health_checks
        if self.load_balancing:
            d["load_balancing"] = self.load_balancing
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReverseProxyHandler":
        return cls(
            upstreams=[UpstreamAddress.from_dict(u) for u in data.get("upstreams", [])],
            headers=data.get("headers"),
            transport=data.get("transport"),
            health_checks=data.get("health_checks"),
            load_balancing=data.get("load_balancing"),
        )

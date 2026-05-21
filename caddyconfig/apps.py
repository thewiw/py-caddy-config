"""
Apps container – https://caddyserver.com/docs/json/apps/

``Apps`` maps directly to the ``apps`` key in the Caddy JSON, making the
Python object hierarchy mirror the JSON structure exactly:

    config.apps.http.get_server("main")
    ↕
    { "apps": { "http": { "servers": { "main": { ... } } } } }

Adding support for other Caddy apps (tls, pki, layer4 …) only requires
extending ``Apps`` without touching ``CaddyConfig``.
"""
from __future__ import annotations

from typing import Any, Optional

from .base import CaddyModel
from .server import HttpApp


class Apps(CaddyModel):
    """
    ``apps`` block of the Caddy configuration.

    Attributes
    ----------
    http : HttpApp | None
        HTTP application (``apps.http``).
    """

    http: Optional[HttpApp] = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.http is not None:
            http_d = self.http.to_dict()
            if http_d:
                d["http"] = http_d
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Apps":  # type: ignore[override]
        http_data = data.get("http")
        return cls(
            http=HttpApp.from_dict(http_data) if http_data is not None else None,
        )

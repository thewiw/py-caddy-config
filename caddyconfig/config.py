"""
Root Caddy configuration object – https://caddyserver.com/docs/json/
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .base import CaddyModel
from .admin import Admin
from .logging import Logging
from .apps import Apps


class CaddyConfig(CaddyModel):
    """
    Complete Caddy configuration – main entry point of the library.

    The object hierarchy mirrors the Caddy JSON structure exactly::

        config.apps.http.get_server("main")
        ↕
        { "apps": { "http": { "servers": { "main": { ... } } } } }

    Attributes
    ----------
    admin : Admin | None
    logging : Logging | None
    apps : Apps | None
        Container for all Caddy applications (http, tls, pki …).
    """

    admin: Optional[Admin] = None
    logging: Optional[Logging] = None
    apps: Optional[Apps] = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.admin is not None:
            d["admin"] = self.admin.to_dict()
        if self.logging is not None:
            d["logging"] = self.logging.to_dict()
        if self.apps is not None:
            d["apps"] = self.apps.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaddyConfig":  # type: ignore[override]
        admin_data = data.get("admin")
        admin = Admin.from_dict(admin_data) if isinstance(admin_data, dict) else None
        logging_data = data.get("logging")
        logging = Logging.from_dict(logging_data) if isinstance(logging_data, dict) else None
        apps_data = data.get("apps")
        apps = Apps.from_dict(apps_data) if isinstance(apps_data, dict) else None
        return cls(admin=admin, logging=logging, apps=apps)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "CaddyConfig":
        return cls.from_dict(json.loads(text))

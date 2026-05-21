"""
Server and HttpApp – https://caddyserver.com/docs/json/apps/http/servers/
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .base import CaddyModel
from .route import Route
from .match import MatchCriteria


class Metrics(CaddyModel):
    """Prometheus metrics for a server."""

    per_host: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"per_host": True} if self.per_host else {}


class Server(CaddyModel):
    """
    HTTP server in the Caddy configuration.

    Attributes
    ----------
    name : str
        Key in ``apps.http.servers``.
    listen : list[str]
        Listen addresses (e.g. ``[":443", ":80"]``).
    routes : list[Route]
    errors : list[Route]
    metrics : Metrics | None
    """

    name: str = Field(exclude=True)  # dict key, not an inline JSON field
    listen: list[str] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    errors: list[Route] = Field(default_factory=list)
    metrics: Optional[Metrics] = None

    @field_validator("listen", mode="before")
    @classmethod
    def listen_format(cls, v: Any) -> Any:
        for addr in v:
            if not isinstance(addr, str) or not addr.strip():
                raise ValueError(f"Invalid listen address: {addr!r}")
        return v

    # ------------------------------------------------------------------
    # Listen address management
    # ------------------------------------------------------------------

    def add_listen(self, address: str) -> None:
        if address not in self.listen:
            self.listen.append(address)

    def remove_listen(self, address: str) -> bool:
        try:
            self.listen.remove(address)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Route lookup
    # ------------------------------------------------------------------

    def find_route(
        self,
        criteria: MatchCriteria,
        *,
        error: bool = False,
        recursive: bool = True,
    ) -> Optional[Route]:
        """
        Returns the first route satisfying the criteria.

        Parameters
        ----------
        criteria : MatchCriteria
            Only non-None fields are compared.
        error : bool
            Search in ``errors`` if True.
        recursive : bool
            Descend into SubrouteHandlers if True.
        """
        target = self.errors if error else self.routes
        for route in target:
            if route._match_fits(criteria):
                return route
        if recursive:
            for route in target:
                result = route.find_in_subroutes(criteria, error=error)
                if result is not None:
                    return result
        return None

    # ------------------------------------------------------------------
    # Upsert / removal
    # ------------------------------------------------------------------

    def upsert_route(
        self,
        criteria: MatchCriteria,
        route: Route,
        *,
        error: bool = False,
    ) -> bool:
        """Inserts or replaces. Returns True if replaced."""
        target = self.errors if error else self.routes
        for i, existing in enumerate(target):
            if existing._match_fits(criteria):
                target[i] = route
                return True
        target.append(route)
        return False

    def remove_route(
        self,
        criteria: MatchCriteria,
        *,
        error: bool = False,
    ) -> bool:
        """Removes the first matching route. Returns True if found."""
        target = self.errors if error else self.routes
        for i, route in enumerate(target):
            if route._match_fits(criteria):
                del target[i]
                return True
        return False

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def routes_in_group(self, group: str) -> list[Route]:
        return [r for r in self.routes if r.group == group]

    def remove_group(self, group: str) -> int:
        before = len(self.routes)
        self.routes = [r for r in self.routes if r.group != group]
        return before - len(self.routes)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.listen:
            d["listen"] = list(self.listen)
        if self.routes:
            d["routes"] = [r.to_dict() for r in self.routes]
        if self.errors:
            d["errors"] = [r.to_dict() for r in self.errors]
        if self.metrics is not None:
            metrics_d = self.metrics.to_dict()
            if metrics_d:
                d["metrics"] = metrics_d
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "Server":  # type: ignore[override]
        metrics = Metrics.from_dict(data["metrics"]) if "metrics" in data else None
        return cls(
            name=name,
            listen=list(data.get("listen", [])),
            routes=[Route.from_dict(r) for r in data.get("routes", [])],
            errors=[Route.from_dict(r) for r in data.get("errors", [])],
            metrics=metrics,
        )


class HttpApp(CaddyModel):
    """
    ``apps.http`` block.

    Attributes
    ----------
    servers : dict[str, Server]
    http_port : int | None
    https_port : int | None
    grace_period : str | None
    """

    servers: dict[str, Server] = Field(default_factory=dict)
    http_port: Optional[int] = None
    https_port: Optional[int] = None
    grace_period: Optional[str] = None

    def add_server(self, server: Server) -> None:
        self.servers[server.name] = server

    def remove_server(self, name: str) -> bool:
        if name in self.servers:
            del self.servers[name]
            return True
        return False

    def get_server(self, name: str) -> Optional[Server]:
        return self.servers.get(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.http_port is not None:
            d["http_port"] = self.http_port
        if self.https_port is not None:
            d["https_port"] = self.https_port
        if self.grace_period is not None:
            d["grace_period"] = self.grace_period
        if self.servers:
            d["servers"] = {name: srv.to_dict() for name, srv in self.servers.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HttpApp":  # type: ignore[override]
        servers = {
            name: Server.from_dict(name, srv)
            for name, srv in data.get("servers", {}).items()
        }
        return cls(
            servers=servers,
            http_port=data.get("http_port"),
            https_port=data.get("https_port"),
            grace_period=data.get("grace_period"),
        )

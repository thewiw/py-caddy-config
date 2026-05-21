"""
Handler ``subroute`` – https://caddyserver.com/docs/json/apps/http/servers/routes/handle/subroute/
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

from . import HandlerBase, register_handler

if TYPE_CHECKING:
    from ..route import Route
    from ..match import MatchCriteria


@register_handler("subroute")
class SubrouteHandler(HandlerBase):
    """
    Handler containing its own nested routes.

    Attributes
    ----------
    routes : list[Route]
    errors : list[Route]
    """

    handler: str = "subroute"
    routes: list[Any] = Field(default_factory=list)   # list[Route] – Any avoids circular import
    errors: list[Any] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_route(self, route: "Route", *, error: bool = False) -> None:
        target = self.errors if error else self.routes
        target.append(route)

    def remove_route(self, criteria: "MatchCriteria", *, error: bool = False) -> bool:
        target = self.errors if error else self.routes
        for i, route in enumerate(target):
            if route._match_fits(criteria):
                del target[i]
                return True
        return False

    def find_route(
        self,
        criteria: "MatchCriteria",
        *,
        error: bool = False,
        recursive: bool = True,
    ) -> Optional["Route"]:
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

    def upsert_route(self, criteria: "MatchCriteria", route: "Route") -> bool:
        for i, existing in enumerate(self.routes):
            if existing._match_fits(criteria):
                self.routes[i] = route
                return True
        self.routes.append(route)
        return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"handler": self.handler}
        if self.routes:
            d["routes"] = [r.to_dict() for r in self.routes]
        if self.errors:
            d["errors"] = [r.to_dict() for r in self.errors]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubrouteHandler":
        from ..route import Route
        return cls(
            routes=[Route.from_dict(r) for r in data.get("routes", [])],
            errors=[Route.from_dict(r) for r in data.get("errors", [])],
        )

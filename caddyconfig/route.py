"""
Caddy Route – https://caddyserver.com/docs/json/apps/http/servers/routes/
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import CaddyModel
from .match import MatchCriteria
from .handlers import HandlerBase, handler_from_dict


class Route(CaddyModel):
    """
    Represents a route in a Caddy server.

    Attributes
    ----------
    group : str | None
    match : list[MatchCriteria]
        Matchers (OR logic).
    handle : list[HandlerBase]
        Handlers executed in order.
    terminal : bool
    """

    group: Optional[str] = None
    match: list[MatchCriteria] = Field(default_factory=list)
    handle: list[Any] = Field(default_factory=list)   # list[HandlerBase]
    terminal: bool = False

    # ------------------------------------------------------------------
    # Matcher matching
    # ------------------------------------------------------------------

    def _match_fits(self, criteria: MatchCriteria) -> bool:
        """
        True if at least one matcher of the route matches the criteria.
        If match is empty and criteria too → True.
        """
        if not self.match and not criteria.to_dict():
            return True
        return any(m.matches_exactly(criteria) for m in self.match)

    # ------------------------------------------------------------------
    # Recursive search in subroutes
    # ------------------------------------------------------------------

    def find_in_subroutes(
        self,
        criteria: MatchCriteria,
        *,
        error: bool = False,
    ) -> Optional["Route"]:
        from .handlers.subroute import SubrouteHandler
        for handler in self.handle:
            if isinstance(handler, SubrouteHandler):
                result = handler.find_route(criteria, error=error, recursive=True)
                if result is not None:
                    return result
        return None

    # ------------------------------------------------------------------
    # Handler management
    # ------------------------------------------------------------------

    def add_handler(self, handler: HandlerBase) -> None:
        self.handle.append(handler)

    def remove_handler(self, handler_type: str) -> bool:
        for i, h in enumerate(self.handle):
            if h.handler == handler_type:
                del self.handle[i]
                return True
        return False

    def get_handler(self, handler_type: str) -> Optional[HandlerBase]:
        for h in self.handle:
            if h.handler == handler_type:
                return h
        return None

    def replace_handler(self, handler: HandlerBase) -> bool:
        for i, h in enumerate(self.handle):
            if h.handler == handler.handler:
                self.handle[i] = handler
                return True
        self.handle.append(handler)
        return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.group is not None:
            d["group"] = self.group
        if self.match:
            d["match"] = [m.to_dict() for m in self.match]
        if self.handle:
            d["handle"] = [h.to_dict() for h in self.handle]
        if self.terminal:
            d["terminal"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Route":
        return cls(
            group=data.get("group"),
            match=[MatchCriteria.from_dict(m) for m in data.get("match", [])],
            handle=[handler_from_dict(h) for h in data.get("handle", [])],
            terminal=data.get("terminal", False),
        )

"""
Admin section – https://caddyserver.com/docs/json/admin/
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from .base import CaddyModel


class Admin(CaddyModel):
    """
    ``admin`` block of the Caddy configuration.

    Attributes
    ----------
    disabled : bool
        Disables the admin API if True.
    listen : str | None
        Listen address (e.g. ``"localhost:2019"``).
    enforce_origins : bool | None
        Enables origin verification.
    origins : list[str]
        Allowed origins.
    """

    disabled: bool = False
    listen: Optional[str] = None
    enforce_origins: Optional[bool] = None
    origins: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_origin(self, origin: str) -> None:
        if origin not in self.origins:
            self.origins.append(origin)

    def remove_origin(self, origin: str) -> bool:
        try:
            self.origins.remove(origin)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Serialization: only emit disabled / enforce_origins if True
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = super().to_dict()
        if not self.disabled:
            d.pop("disabled", None)
        if not self.enforce_origins:
            d.pop("enforce_origins", None)
        if not self.origins:
            d.pop("origins", None)
        return d

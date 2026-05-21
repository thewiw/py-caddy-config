"""
Base Pydantic class for all Caddy objects.

Common rules:
  - None fields are excluded from serialization (exclude_none=True).
  - Python → JSON aliases are declared with Field(serialization_alias=...).
  - model_config forbids unknown fields (extra="forbid") on strict models,
    but "unknown" handlers (RawHandler) use extra="allow".
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class CaddyModel(BaseModel):
    """Base model: Caddy JSON serialization without None fields."""

    model_config = ConfigDict(
        populate_by_name=True,   # accepte le nom Python ET l'alias
        extra="forbid",
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict ready for Caddy (no None keys, with aliases)."""
        return self.model_dump(
            mode="json",
            exclude_none=True,
            by_alias=True,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaddyModel":
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "CaddyModel":
        return cls.from_dict(json.loads(text))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"

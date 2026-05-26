"""
Handler base and polymorphic deserialization registry.
"""
from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from ..base import CaddyModel

# Registry: handler_type → Pydantic class
_HANDLER_REGISTRY: dict[str, type["HandlerBase"]] = {}


def register_handler(handler_type: str):
    """Decorator: registers a class in the registry."""
    def decorator(cls: type) -> type:
        _HANDLER_REGISTRY[handler_type] = cls
        return cls
    return decorator


class HandlerBase(CaddyModel):
    """Base class for all Caddy handlers."""

    handler: str  # polymorphic discriminant


class RawHandler(HandlerBase):
    """Generic handler for types not explicitly covered."""

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawHandler":
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


def handler_from_dict(data: dict[str, Any]) -> HandlerBase:
    """
    Deserializes a handler using the registry.
    Returns a ``RawHandler`` if the type is unknown.
    """
    handler_type = data.get("handler", "")
    klass = _HANDLER_REGISTRY.get(handler_type)
    if klass is not None:
        return klass.from_dict(data)
    return RawHandler.from_dict(data)

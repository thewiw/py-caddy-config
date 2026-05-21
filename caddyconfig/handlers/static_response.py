"""
Handler ``static_response`` – https://caddyserver.com/docs/json/apps/http/servers/routes/handle/static_response/
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import field_validator

from . import HandlerBase, register_handler


@register_handler("static_response")
class StaticResponseHandler(HandlerBase):
    """
    Returns a static HTTP response.

    Attributes
    ----------
    status_code : int | None
        HTTP code (100-599).
    headers : dict[str, list[str]] | None
    body : str | None
    close : bool
    """

    handler: str = "static_response"
    status_code: Optional[int] = None
    headers: Optional[dict[str, list[str]]] = None
    body: Optional[str] = None
    close: bool = False

    @field_validator("status_code")
    @classmethod
    def valid_status(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (100 <= v <= 599):
            raise ValueError(f"status_code must be between 100 and 599, got: {v}")
        return v

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"handler": self.handler}
        if self.status_code is not None:
            d["status_code"] = self.status_code
        if self.headers:
            d["headers"] = {k: list(v) for k, v in self.headers.items()}
        if self.body is not None:
            d["body"] = self.body
        if self.close:
            d["close"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StaticResponseHandler":
        return cls(
            status_code=data.get("status_code"),
            headers=data.get("headers"),
            body=data.get("body"),
            close=data.get("close", False),
        )

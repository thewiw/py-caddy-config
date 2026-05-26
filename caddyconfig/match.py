"""
Matchers – https://caddyserver.com/docs/json/apps/http/servers/routes/match/

Pydantic validation:
  - host   : list of non-empty str
  - path   : must start with /
  - header : non-empty keys and values
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .base import CaddyModel


class MatchCriteria(CaddyModel):
    """
    ``match`` block of a Caddy route.

    All fields are optional; only set fields are included in serialization.

    Attributes
    ----------
    host : list[str] | None
    path : list[str] | None
    path_regexp : dict | None
        E.g. ``{"name": "re1", "pattern": "^/v[0-9]+"}``
    header : dict[str, list[str]] | None
    header_regexp : dict | None
        E.g. ``{"name": "re1", "field": "X-Foo", "pattern": "^Bearer"}``
    not_ : list[MatchCriteria] | None
        Inverted matchers (JSON key : ``"not"``).
    """

    host: Optional[list[str]] = None
    path: Optional[list[str]] = None
    path_regexp: Optional[dict[str, Any]] = None
    header: Optional[dict[str, list[str]]] = None
    header_regexp: Optional[dict[str, Any]] = None
    not_: Optional[list["MatchCriteria"]] = Field(None, alias="not", serialization_alias="not") # JSON alias: "not" is a Python reserved word

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("host", mode="before")
    @classmethod
    def host_non_empty(cls, v: Any) -> Any:
        if v is not None:
            for h in v:
                if not isinstance(h, str) or not h.strip():
                    raise ValueError(f"Each host entry must be a non-empty string, got: {h!r}")
        return v

    @field_validator("path", mode="before")
    @classmethod
    def path_starts_with_slash(cls, v: Any) -> Any:
        if v is not None:
            for p in v:
                if not isinstance(p, str) or not p.startswith("/"):
                    raise ValueError(f"Each path must start with '/', got: {p!r}")
        return v

    @field_validator("header", mode="before")
    @classmethod
    def header_non_empty_keys(cls, v: Any) -> Any:
        if v is not None:
            for k in v:
                if not k.strip():
                    raise ValueError("Header keys cannot be empty")
        return v

    # ------------------------------------------------------------------
    # Exact matching (for find / upsert / remove)
    # ------------------------------------------------------------------

    def matches_exactly(self, criteria: "MatchCriteria") -> bool:
        """
        Returns True if this matcher satisfies all provided criteria.

        None fields in ``criteria`` are ignored (= "don't care").
        Lists are compared regardless of order.
        """
        if criteria.host is not None:
            if sorted(self.host or []) != sorted(criteria.host):
                return False
        if criteria.path is not None:
            if sorted(self.path or []) != sorted(criteria.path):
                return False
        if criteria.path_regexp is not None:
            if self.path_regexp != criteria.path_regexp:
                return False
        if criteria.header is not None:
            if self.header != criteria.header:
                return False
        if criteria.header_regexp is not None:
            if self.header_regexp != criteria.header_regexp:
                return False
        if criteria.not_ is not None:
            self_not = self.not_ or []
            if len(self_not) != len(criteria.not_):
                return False
            for s, c in zip(self_not, criteria.not_):
                if not s.matches_exactly(c):
                    return False
        return True

    # ------------------------------------------------------------------
    # Serialization: exclude None fields + "not" alias
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.host is not None:
            d["host"] = list(self.host)
        if self.path is not None:
            d["path"] = list(self.path)
        if self.path_regexp is not None:
            d["path_regexp"] = dict(self.path_regexp)
        if self.header is not None:
            d["header"] = {k: list(v) for k, v in self.header.items()}
        if self.header_regexp is not None:
            d["header_regexp"] = dict(self.header_regexp)
        if self.not_:
            # Use the serialization_alias from the Field definition
            alias = self.__class__.model_fields["not_"].serialization_alias or "not"
            d[alias] = [m.to_dict() for m in self.not_]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchCriteria":
        # Remap "not" → "not_" for Pydantic
        payload = dict(data)
        not_data = payload.pop("not", None)
        if not_data is not None:
            payload["not_"] = [cls.from_dict(m) for m in not_data]
        return cls.model_validate(payload)

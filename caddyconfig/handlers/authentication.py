"""
Handler ``authentication`` (http_basic provider only).
https://caddyserver.com/docs/json/apps/http/servers/routes/handle/authentication/
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from . import HandlerBase, register_handler
from ..base import CaddyModel

HashAlgorithm = Literal["bcrypt", "scrypt"]


class HttpBasicCredential(CaddyModel):
    """
    Username / hashed password pair for http_basic.

    Attributes
    ----------
    username : str       Non-empty.
    password : str       Non-empty.
    algorithm : str      ``"bcrypt"`` (default) or ``"scrypt"``.
    """

    username: str
    password: str
    algorithm: HashAlgorithm = "bcrypt"

    @field_validator("username", "password")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("username and password cannot be empty")
        return v

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HttpBasicCredential":
        algo = data.get("algorithm", "bcrypt")
        algorithm = algo if isinstance(algo, str) else "bcrypt"
        return cls(
            username=data["username"],
            password=data["password"],
            algorithm=algorithm,
        )


@register_handler("authentication")
class AuthenticationHandler(HandlerBase):
    """
    HTTP Basic authentication.

    Attributes
    ----------
    realm : str
    credentials : list[HttpBasicCredential]
    hash_cache : bool
        Enables Caddy hash caching (recommended with bcrypt).
    """

    handler: str = "authentication"
    realm: str = ""
    credentials: list[HttpBasicCredential] = Field(default_factory=list)
    hash_cache: bool = False

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_credential(self, credential: HttpBasicCredential) -> None:
        """Adds or replaces (same username)."""
        self.remove_credential(credential.username)
        self.credentials.append(credential)

    def remove_credential(self, username: str) -> bool:
        before = len(self.credentials)
        self.credentials = [c for c in self.credentials if c.username != username]
        return len(self.credentials) < before

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        provider: dict[str, Any] = {
            "accounts": [c.to_dict() for c in self.credentials],
        }
        if self.realm:
            provider["realm"] = self.realm
        if self.hash_cache:
            provider["hash_cache"] = {}
        return {
            "handler": self.handler,
            "providers": {"http_basic": provider},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthenticationHandler":
        providers = data.get("providers")
        http_basic = providers.get("http_basic") if isinstance(providers, dict) else {}
        http_basic = http_basic or {}
        hash_cache_val = http_basic.get("hash_cache")
        if isinstance(hash_cache_val, dict):
            hash_cache = True
        else:
            hash_cache = bool(hash_cache_val) if hash_cache_val is not None else False
        return cls(
            realm=http_basic.get("realm", ""),
            credentials=[
                HttpBasicCredential.from_dict(c)
                for c in http_basic.get("accounts", [])
            ],
            hash_cache=hash_cache,
        )

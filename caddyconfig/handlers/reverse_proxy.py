"""
Handler ``reverse_proxy`` – https://caddyserver.com/docs/json/apps/http/servers/routes/handle/reverse_proxy/
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, field_validator

from . import HandlerBase, register_handler
from ..base import CaddyModel

if TYPE_CHECKING:
    from ..route import Route

# Validates host:port, [ipv6]:port, :port, unix//path
# Port: 1-65535 (max 5 digits, but range is validated by the validator)
_DIAL_RE = re.compile(
    r"^("
    r"unix//.+"                                      # unix socket
    r"|:([1-9]\d{0,4})"                              # port only
    r"|\[.+\]:([1-9]\d{0,4})"                        # [IPv6]:port
    r"|[a-zA-Z0-9._\-]+:([1-9]\d{0,4})"             # host:port
    r")$"
)


# ---------------------------------------------------------------------------
# UpstreamAddress
# ---------------------------------------------------------------------------

class UpstreamAddress(CaddyModel):
    """Address of an upstream (``dial``)."""

    dial: str
    max_requests: Optional[int] = None

    @field_validator("dial")
    @classmethod
    def dial_format(cls, v: str) -> str:
        if not _DIAL_RE.match(v):
            raise ValueError(
                f"Invalid dial format: {v!r}. "
                "Expected: host:port, [ipv6]:port, :port or unix//path"
            )
        # Numeric port verification (1-65535)
        if not v.startswith("unix//"):
            port_str = v.rsplit(":", 1)[-1]
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError(
                    f"Port out of range (1-65535): {port}"
                )
        return v

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"dial": self.dial}
        if self.max_requests is not None:
            d["max_requests"] = self.max_requests
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpstreamAddress":
        return cls(dial=data["dial"], max_requests=data.get("max_requests"))


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

class HeaderReplacement(CaddyModel):
    """In-situ substring/regex replacement for a header value."""

    search: Optional[str] = None
    search_regexp: Optional[str] = None
    replace: Optional[str] = None


class HeaderOps(CaddyModel):
    """Manipulations for HTTP request/response headers."""

    add: Optional[dict[str, list[str]]] = None
    set: Optional[dict[str, list[str]]] = None
    delete: Optional[list[str]] = None
    replace: Optional[dict[str, list[HeaderReplacement]]] = None


class HeaderRequire(CaddyModel):
    """Criteria a response must satisfy for deferred header ops to apply."""

    status_code: Optional[list[int]] = None
    headers: Optional[dict[str, list[str]]] = None


class RespHeaderOps(CaddyModel):
    """Response header manipulations, with optional deferred application."""

    add: Optional[dict[str, list[str]]] = None
    set: Optional[dict[str, list[str]]] = None
    delete: Optional[list[str]] = None
    replace: Optional[dict[str, list[HeaderReplacement]]] = None
    require: Optional[HeaderRequire] = None
    deferred: Optional[bool] = None


class HeaderConfig(CaddyModel):
    """Top-level ``headers`` block on reverse_proxy."""

    request: Optional[HeaderOps] = None
    response: Optional[RespHeaderOps] = None


# ---------------------------------------------------------------------------
# Rewrite
# ---------------------------------------------------------------------------

class UriSubstring(CaddyModel):
    """Substring replacement on the URI."""

    find: Optional[str] = None
    replace: Optional[str] = None
    limit: Optional[int] = None


class PathRegexp(CaddyModel):
    """Regex replacement on the URI path."""

    find: Optional[str] = None
    replace: Optional[str] = None


class QueryRename(CaddyModel):
    """Rename a query key."""

    key: Optional[str] = None
    val: Optional[str] = None


class QuerySet(CaddyModel):
    """Set a query key/value."""

    key: Optional[str] = None
    val: Optional[str] = None


class QueryReplace(CaddyModel):
    """In-situ replacement of a query parameter value."""

    key: Optional[str] = None
    search: Optional[str] = None
    search_regexp: Optional[str] = None
    replace: Optional[str] = None


class QueryRewrite(CaddyModel):
    """Operations to perform on the URI query string."""

    rename: Optional[list[QueryRename]] = None
    set: Optional[list[QuerySet]] = None
    add: Optional[list[QuerySet]] = None
    replace: Optional[list[QueryReplace]] = None
    delete: Optional[list[str]] = None


class RewriteConfig(CaddyModel):
    """Rewrite applied to the upstream request copy."""

    method: Optional[str] = None
    uri: Optional[str] = None
    strip_path_prefix: Optional[str] = None
    strip_path_suffix: Optional[str] = None
    uri_substring: Optional[list[UriSubstring]] = None
    path_regexp: Optional[list[PathRegexp]] = None
    query: Optional[QueryRewrite] = None


# ---------------------------------------------------------------------------
# Health Checks
# ---------------------------------------------------------------------------

class ActiveHealthCheck(CaddyModel):
    """Active (proactive) health check configuration."""

    path: Optional[str] = None
    uri: Optional[str] = None
    upstream: Optional[str] = None
    port: Optional[int] = None
    headers: Optional[dict[str, list[str]]] = None
    method: Optional[str] = None
    body: Optional[str] = None
    follow_redirects: Optional[bool] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    passes: Optional[int] = None
    fails: Optional[int] = None
    max_size: Optional[int] = None
    expect_status: Optional[int] = None
    expect_body: Optional[str] = None


class PassiveHealthCheck(CaddyModel):
    """Passive (reactive) health check configuration."""

    fail_duration: Optional[int] = None
    max_fails: Optional[int] = None
    unhealthy_request_count: Optional[int] = None
    unhealthy_status: Optional[list[int]] = None
    unhealthy_latency: Optional[int] = None


class HealthChecks(CaddyModel):
    """Health check settings (active + passive)."""

    active: Optional[ActiveHealthCheck] = None
    passive: Optional[PassiveHealthCheck] = None


# ---------------------------------------------------------------------------
# Load Balancing
# ---------------------------------------------------------------------------

class LoadBalancing(CaddyModel):
    """Load balancing and retry configuration."""

    selection_policy: Optional[dict[str, Any]] = None
    retries: Optional[int] = None
    try_duration: Optional[int] = None
    try_interval: Optional[int] = None
    retry_match: Optional[list[Any]] = None


# ---------------------------------------------------------------------------
# Handle Response
# ---------------------------------------------------------------------------

class HandleResponseMatch(CaddyModel):
    """Criteria for matching a response in handle_response."""

    status_code: Optional[list[int]] = None
    headers: Optional[dict[str, list[str]]] = None


class HandleResponse(CaddyModel):
    """Response interception and replacement within reverse_proxy."""

    match: Optional[HandleResponseMatch] = None
    status_code: Optional[str] = None
    routes: list[Any] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.match is not None:
            match_dict = self.match.to_dict()
            if match_dict:
                d["match"] = match_dict
        if self.status_code is not None:
            d["status_code"] = self.status_code
        if self.routes:
            d["routes"] = [r.to_dict() for r in self.routes]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandleResponse":
        from ..route import Route
        match_data = data.get("match")
        match = HandleResponseMatch.from_dict(match_data) if match_data else None
        routes_data = data.get("routes", [])
        routes = [Route.from_dict(r) for r in routes_data]
        return cls(
            match=match,
            status_code=data.get("status_code"),
            routes=routes,
        )


# ---------------------------------------------------------------------------
# ReverseProxyHandler
# ---------------------------------------------------------------------------

@register_handler("reverse_proxy")
class ReverseProxyHandler(HandlerBase):
    """
    Forwards requests to one or more upstreams.

    Attributes
    ----------
    upstreams : list[UpstreamAddress]
        Destinations (format ``host:port``).
    headers : HeaderConfig | None
        Header manipulation.
    transport : dict | None
        HTTP transport configuration.
    circuit_breaker : dict | None
    health_checks : HealthChecks | None
    load_balancing : LoadBalancing | None
    rewrite : RewriteConfig | None
    handle_response : list[HandleResponse] | None
    flush_interval : int | None
    trusted_proxies : list[str] | None
    request_buffers : int | None
    response_buffers : int | None
    stream_timeout : int | None
    stream_close_delay : int | None
    dynamic_upstreams : dict | None
    verbose_logs : bool
    """

    handler: str = "reverse_proxy"
    upstreams: list[UpstreamAddress] = Field(default_factory=list)
    headers: Optional[HeaderConfig] = None
    transport: Optional[dict[str, Any]] = None
    circuit_breaker: Optional[dict[str, Any]] = None
    health_checks: Optional[HealthChecks] = None
    load_balancing: Optional[LoadBalancing] = None
    rewrite: Optional[RewriteConfig] = None
    handle_response: Optional[list[HandleResponse]] = None
    flush_interval: Optional[int] = None
    trusted_proxies: Optional[list[str]] = None
    request_buffers: Optional[int] = None
    response_buffers: Optional[int] = None
    stream_timeout: Optional[int] = None
    stream_close_delay: Optional[int] = None
    dynamic_upstreams: Optional[dict[str, Any]] = None
    verbose_logs: bool = False

    # ------------------------------------------------------------------
    # Convenience constructor: accepts str or UpstreamAddress
    # ------------------------------------------------------------------

    @field_validator("upstreams", mode="before")
    @classmethod
    def coerce_upstreams(cls, v: Any) -> Any:
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"dial": item})
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_upstream(self, dial: str) -> None:
        """Adds an upstream (ignored if already present)."""
        if not any(u.dial == dial for u in self.upstreams):
            self.upstreams.append(UpstreamAddress(dial=dial))

    def remove_upstream(self, dial: str) -> bool:
        before = len(self.upstreams)
        self.upstreams = [u for u in self.upstreams if u.dial != dial]
        return len(self.upstreams) < before

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "handler": self.handler,
            "upstreams": [u.to_dict() for u in self.upstreams],
        }
        if self.headers is not None:
            headers_dict = self.headers.to_dict()
            if headers_dict:
                d["headers"] = headers_dict
        if self.transport:
            d["transport"] = self.transport
        if self.circuit_breaker:
            d["circuit_breaker"] = self.circuit_breaker
        if self.health_checks is not None:
            hc_dict = self.health_checks.to_dict()
            if hc_dict:
                d["health_checks"] = hc_dict
        if self.load_balancing is not None:
            lb_dict = self.load_balancing.to_dict()
            if lb_dict:
                d["load_balancing"] = lb_dict
        if self.rewrite is not None:
            rw_dict = self.rewrite.to_dict()
            if rw_dict:
                d["rewrite"] = rw_dict
        if self.handle_response:
            d["handle_response"] = [hr.to_dict() for hr in self.handle_response]
        if self.flush_interval is not None:
            d["flush_interval"] = self.flush_interval
        if self.trusted_proxies:
            d["trusted_proxies"] = list(self.trusted_proxies)
        if self.request_buffers is not None:
            d["request_buffers"] = self.request_buffers
        if self.response_buffers is not None:
            d["response_buffers"] = self.response_buffers
        if self.stream_timeout is not None:
            d["stream_timeout"] = self.stream_timeout
        if self.stream_close_delay is not None:
            d["stream_close_delay"] = self.stream_close_delay
        if self.dynamic_upstreams:
            d["dynamic_upstreams"] = self.dynamic_upstreams
        if self.verbose_logs:
            d["verbose_logs"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReverseProxyHandler":
        headers_data = data.get("headers")
        headers = HeaderConfig.model_validate(headers_data) if headers_data else None

        health_checks_data = data.get("health_checks")
        health_checks = HealthChecks.model_validate(health_checks_data) if health_checks_data else None

        load_balancing_data = data.get("load_balancing")
        load_balancing = LoadBalancing.model_validate(load_balancing_data) if load_balancing_data else None

        rewrite_data = data.get("rewrite")
        rewrite = RewriteConfig.model_validate(rewrite_data) if rewrite_data else None

        handle_response_data = data.get("handle_response")
        handle_response = [HandleResponse.from_dict(hr) for hr in handle_response_data] if handle_response_data else None

        return cls(
            upstreams=[UpstreamAddress.from_dict(u) for u in data.get("upstreams", [])],
            headers=headers,
            transport=data.get("transport"),
            circuit_breaker=data.get("circuit_breaker"),
            health_checks=health_checks,
            load_balancing=load_balancing,
            rewrite=rewrite,
            handle_response=handle_response,
            flush_interval=data.get("flush_interval"),
            trusted_proxies=list(data.get("trusted_proxies", [])),
            request_buffers=data.get("request_buffers"),
            response_buffers=data.get("response_buffers"),
            stream_timeout=data.get("stream_timeout"),
            stream_close_delay=data.get("stream_close_delay"),
            dynamic_upstreams=data.get("dynamic_upstreams"),
            verbose_logs=data.get("verbose_logs", False),
        )

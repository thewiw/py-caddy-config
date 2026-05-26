"""
caddyconfig – Caddy JSON configuration manipulation via Pydantic v2.

Public API
----------
Models:
    CaddyConfig, Apps, Admin, Logging, LogSink, LogEntry,
    HttpApp, Server, Metrics, Route, MatchCriteria

Handlers:
    FileServerHandler, ReverseProxyHandler, UpstreamAddress,
    StaticResponseHandler, AuthenticationHandler, HttpBasicCredential,
    SubrouteHandler, RawHandler, handler_from_dict

Builder:
    CaddyConfigBuilder, ServerBuilder, RouteBuilder, SubrouteBuilder
"""

# Core models
from .config import CaddyConfig
from .apps import Apps
from .admin import Admin
from .logging import Logging, LogSink, LogEntry
from .server import HttpApp, Server, Metrics
from .route import Route
from .match import MatchCriteria

# Handlers
from .handlers import HandlerBase, RawHandler, handler_from_dict
from .handlers.file_server import FileServerHandler
from .handlers.reverse_proxy import (
    ReverseProxyHandler,
    UpstreamAddress,
    HeaderConfig,
    HeaderOps,
    RespHeaderOps,
    HeaderReplacement,
    HeaderRequire,
    RewriteConfig,
    QueryRewrite,
    UriSubstring,
    PathRegexp,
    QueryRename,
    QuerySet,
    QueryReplace,
    HealthChecks,
    ActiveHealthCheck,
    PassiveHealthCheck,
    LoadBalancing,
    HandleResponse,
    HandleResponseMatch,
)
from .handlers.static_response import StaticResponseHandler
from .handlers.authentication import AuthenticationHandler, HttpBasicCredential
from .handlers.subroute import SubrouteHandler

# Fluent builder
from .builder import CaddyConfigBuilder, ServerBuilder, RouteBuilder, SubrouteBuilder

__all__ = [
    # Config
    "CaddyConfig", "Apps",
    # Admin
    "Admin",
    # Logging
    "Logging", "LogSink", "LogEntry",
    # HTTP
    "HttpApp", "Server", "Metrics",
    # Routes
    "Route", "MatchCriteria",
    # Handlers
    "HandlerBase", "RawHandler", "handler_from_dict",
    "FileServerHandler",
    "ReverseProxyHandler", "UpstreamAddress",
    "HeaderConfig", "HeaderOps", "RespHeaderOps",
    "HeaderReplacement", "HeaderRequire",
    "RewriteConfig", "QueryRewrite",
    "UriSubstring", "PathRegexp",
    "QueryRename", "QuerySet", "QueryReplace",
    "HealthChecks", "ActiveHealthCheck", "PassiveHealthCheck",
    "LoadBalancing",
    "HandleResponse", "HandleResponseMatch",
    "StaticResponseHandler",
    "AuthenticationHandler", "HttpBasicCredential",
    "SubrouteHandler",
    # Builder
    "CaddyConfigBuilder", "ServerBuilder", "RouteBuilder", "SubrouteBuilder",
]

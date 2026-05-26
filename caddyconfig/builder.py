"""
Fluent builder layer for constructing Caddy configurations.

Each builder accumulates its parameters through chained method calls and
exposes a ``build()`` method that returns the corresponding model object.
Nested builders return to their parent via ``.done()``.

Full example
------------
::

    from caddyconfig.builder import CaddyConfigBuilder

    config = (
        CaddyConfigBuilder()
        .admin(listen="localhost:2019")
        .logging(writer="stderr", level="info")
        .server("main", listen=[":443", ":80"])
            .route()
                .match(host=["acme.com"])
                .handle_static(200, body="Welcome")
            .done()
            .route()
                .match(host=["acme.com"], path=["/test"])
                .handle_reverse_proxy("192.168.0.123:8042")
            .done()
        .done()
        .build()
    )
"""
from __future__ import annotations

from typing import Any, Optional

from .admin import Admin
from .apps import Apps
from .config import CaddyConfig
from .handlers.authentication import AuthenticationHandler, HttpBasicCredential
from .handlers.file_server import FileServerHandler
from .handlers.reverse_proxy import ReverseProxyHandler
from .handlers.static_response import StaticResponseHandler
from .handlers.subroute import SubrouteHandler
from .logging import LogEntry, LogSink, Logging
from .match import MatchCriteria
from .route import Route
from .server import HttpApp, Metrics, Server


# ---------------------------------------------------------------------------
# RouteBuilder
# ---------------------------------------------------------------------------

class RouteBuilder:
    """
    Builder for a ``Route``.

    Standalone usage::

        route = RouteBuilder().match(host=["foo.com"]).handle_reverse_proxy("10.0.0.1:80").build()

    Embedded in a ServerBuilder::

        server_builder.route().match(...).handle_reverse_proxy(...).done()
    """

    def __init__(self, parent: Optional["ServerBuilder | SubrouteBuilder"] = None) -> None:
        self._parent = parent
        self._group: Optional[str] = None
        self._matchers: list[MatchCriteria] = []
        self._handlers: list[Any] = []
        self._terminal: bool = False
        self._error: bool = False  # True → route belongs to the errors block

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def group(self, name: str) -> "RouteBuilder":
        """Assign this route to a group."""
        self._group = name
        return self

    def terminal(self, value: bool = True) -> "RouteBuilder":
        """Mark this route as terminal."""
        self._terminal = value
        return self

    def as_error(self) -> "RouteBuilder":
        """Route goes into the ``errors`` block instead of ``routes``."""
        self._error = True
        return self

    # ------------------------------------------------------------------
    # Matchers
    # ------------------------------------------------------------------

    def match(
        self,
        host: Optional[list[str]] = None,
        path: Optional[list[str]] = None,
        path_regexp: Optional[dict[str, Any]] = None,
        header: Optional[dict[str, list[str]]] = None,
        header_regexp: Optional[dict[str, Any]] = None,
        not_: Optional[list[MatchCriteria]] = None,
    ) -> "RouteBuilder":
        """
        Add a matcher block. Multiple calls produce OR logic.

        Parameters
        ----------
        host : list[str] | None
        path : list[str] | None
        path_regexp : dict | None
        header : dict[str, list[str]] | None
        header_regexp : dict | None
        not_ : list[MatchCriteria] | None
        """
        self._matchers.append(
            MatchCriteria(
                host=host,
                path=path,
                path_regexp=path_regexp,
                header=header,
                header_regexp=header_regexp,
                not_=not_,
            )
        )
        return self

    # ------------------------------------------------------------------
    # Convenience handler methods
    # ------------------------------------------------------------------

    def handle_reverse_proxy(
        self,
        *upstreams: str,
        headers: Optional[dict[str, Any]] = None,
        transport: Optional[dict[str, Any]] = None,
        circuit_breaker: Optional[dict[str, Any]] = None,
        health_checks: Optional[dict[str, Any]] = None,
        load_balancing: Optional[dict[str, Any]] = None,
        rewrite: Optional[dict[str, Any]] = None,
        handle_response: Optional[list[dict[str, Any]]] = None,
        flush_interval: Optional[int] = None,
        trusted_proxies: Optional[list[str]] = None,
        request_buffers: Optional[int] = None,
        response_buffers: Optional[int] = None,
        stream_timeout: Optional[int] = None,
        stream_close_delay: Optional[int] = None,
        dynamic_upstreams: Optional[dict[str, Any]] = None,
        verbose_logs: bool = False,
    ) -> "RouteBuilder":
        """
        Add a ``reverse_proxy`` handler.

        Parameters
        ----------
        *upstreams : str
            One or more ``host:port`` upstream addresses.
        """
        self._handlers.append(
            ReverseProxyHandler(
                upstreams=list(upstreams),
                headers=headers,
                transport=transport,
                circuit_breaker=circuit_breaker,
                health_checks=health_checks,
                load_balancing=load_balancing,
                rewrite=rewrite,
                handle_response=handle_response,
                flush_interval=flush_interval,
                trusted_proxies=trusted_proxies,
                request_buffers=request_buffers,
                response_buffers=response_buffers,
                stream_timeout=stream_timeout,
                stream_close_delay=stream_close_delay,
                dynamic_upstreams=dynamic_upstreams,
                verbose_logs=verbose_logs,
            )
        )
        return self

    def handle_static(
        self,
        status_code: Optional[int] = None,
        *,
        body: Optional[str] = None,
        headers: Optional[dict[str, list[str]]] = None,
        close: bool = False,
    ) -> "RouteBuilder":
        """Add a ``static_response`` handler."""
        self._handlers.append(
            StaticResponseHandler(
                status_code=status_code,
                body=body,
                headers=headers,
                close=close,
            )
        )
        return self

    def handle_file_server(
        self,
        root: Optional[str] = None,
        *,
        browse: bool = False,
        hide: Optional[list[str]] = None,
        index_names: Optional[list[str]] = None,
        pass_thru: bool = False,
    ) -> "RouteBuilder":
        """Add a ``file_server`` handler."""
        self._handlers.append(
            FileServerHandler(
                root=root,
                browse=browse,
                hide=hide or [],
                index_names=index_names or [],
                pass_thru=pass_thru,
            )
        )
        return self

    def handle_auth_basic(
        self,
        *credentials: tuple[str, str],
        realm: str = "",
        hash_cache: bool = False,
    ) -> "RouteBuilder":
        """
        Add an ``authentication`` handler (http_basic provider).

        Parameters
        ----------
        *credentials : tuple[str, str]
            ``(username, hashed_password)`` pairs.
        realm : str
        hash_cache : bool
        """
        creds = [HttpBasicCredential(username=u, password=p) for u, p in credentials]
        self._handlers.append(
            AuthenticationHandler(realm=realm, credentials=creds, hash_cache=hash_cache)
        )
        return self

    def handle_subroute(self) -> "SubrouteBuilder":
        """
        Open a nested subroute builder.

        Usage::

            route_builder.handle_subroute()
                .route().match(path=["/api"]).handle_reverse_proxy("10.0.0.1:80").done()
            .done()  # closes SubrouteBuilder → returns to RouteBuilder
        """
        return SubrouteBuilder(parent=self)

    def handle(self, handler: Any) -> "RouteBuilder":
        """Attach any pre-built handler instance."""
        self._handlers.append(handler)
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Route:
        """Build and return the ``Route``."""
        return Route(
            group=self._group,
            match=list(self._matchers),
            handle=list(self._handlers),
            terminal=self._terminal,
        )

    def done(self) -> "ServerBuilder | SubrouteBuilder":
        """
        Finalize the route and return the parent builder.
        Raises RuntimeError if this builder has no parent.
        """
        if self._parent is None:
            raise RuntimeError(
                "done() called on a RouteBuilder with no parent. "
                "Use build() to obtain the Route directly."
            )
        route = self.build()
        self._parent._add_route(route, error=self._error)
        return self._parent


# ---------------------------------------------------------------------------
# SubrouteBuilder
# ---------------------------------------------------------------------------

class SubrouteBuilder:
    """
    Builder for a ``SubrouteHandler``.

    Returned by ``RouteBuilder.handle_subroute()``.
    """

    def __init__(self, parent: "RouteBuilder") -> None:
        self._parent = parent
        self._routes: list[Route] = []
        self._errors: list[Route] = []

    def _add_route(self, route: Route, *, error: bool = False) -> None:
        if error:
            self._errors.append(route)
        else:
            self._routes.append(route)

    def route(self) -> RouteBuilder:
        """Open a child route builder."""
        return RouteBuilder(parent=self)

    def build(self) -> SubrouteHandler:
        """Build and return the ``SubrouteHandler``."""
        return SubrouteHandler(routes=list(self._routes), errors=list(self._errors))

    def done(self) -> RouteBuilder:
        """Finalize the SubrouteHandler and attach it to the parent RouteBuilder."""
        self._parent._handlers.append(self.build())
        return self._parent


# ---------------------------------------------------------------------------
# ServerBuilder
# ---------------------------------------------------------------------------

class ServerBuilder:
    """
    Builder for a ``Server``.

    Returned by ``CaddyConfigBuilder.server()``.
    """

    def __init__(
        self,
        name: str,
        listen: Optional[list[str]] = None,
        parent: Optional["CaddyConfigBuilder"] = None,
    ) -> None:
        self._name = name
        self._listen: list[str] = list(listen or [])
        self._parent = parent
        self._routes: list[Route] = []
        self._errors: list[Route] = []
        self._metrics: Optional[Metrics] = None

    # ------------------------------------------------------------------
    # Server configuration
    # ------------------------------------------------------------------

    def listen(self, *addresses: str) -> "ServerBuilder":
        """Add listen addresses (duplicates are ignored)."""
        for addr in addresses:
            if addr not in self._listen:
                self._listen.append(addr)
        return self

    def metrics(self, per_host: bool = False) -> "ServerBuilder":
        """Enable Prometheus metrics."""
        self._metrics = Metrics(per_host=per_host)
        return self

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def _add_route(self, route: Route, *, error: bool = False) -> None:
        if error:
            self._errors.append(route)
        else:
            self._routes.append(route)

    def route(self) -> RouteBuilder:
        """Open a route builder."""
        return RouteBuilder(parent=self)

    def error_route(self) -> RouteBuilder:
        """Open a route builder targeting the ``errors`` block."""
        rb = RouteBuilder(parent=self)
        rb._error = True
        return rb

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Server:
        """Build and return the ``Server``."""
        return Server(
            name=self._name,
            listen=list(self._listen),
            routes=list(self._routes),
            errors=list(self._errors),
            metrics=self._metrics,
        )

    def done(self) -> "CaddyConfigBuilder":
        """Finalize the server and return the parent builder."""
        if self._parent is None:
            raise RuntimeError("done() called with no parent CaddyConfigBuilder.")
        self._parent._add_server(self.build())
        return self._parent


# ---------------------------------------------------------------------------
# CaddyConfigBuilder
# ---------------------------------------------------------------------------

class CaddyConfigBuilder:
    """
    Root builder for a ``CaddyConfig``.

    Minimal example
    ---------------
    ::

        config = (
            CaddyConfigBuilder()
            .admin(listen="localhost:2019")
            .logging(writer="stderr", level="info")
            .server("main", listen=[":443", ":80"])
                .route()
                    .match(host=["foo.com"])
                    .handle_reverse_proxy("10.0.0.1:8080")
                .done()
            .done()
            .build()
        )
    """

    def __init__(self) -> None:
        self._admin: Optional[Admin] = None
        self._logging: Optional[Logging] = None
        self._servers: list[Server] = []

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def admin(
        self,
        *,
        listen: Optional[str] = None,
        disabled: bool = False,
        enforce_origins: bool = False,
        origins: Optional[list[str]] = None,
    ) -> "CaddyConfigBuilder":
        """Configure the admin block."""
        self._admin = Admin(
            disabled=disabled,
            listen=listen,
            enforce_origins=enforce_origins or None,
            origins=origins or [],
        )
        return self

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def logging(
        self,
        writer: str = "stderr",
        level: str = "info",
        *,
        logger_name: str = "default",
        extra_logs: Optional[dict[str, dict[str, str]]] = None,
    ) -> "CaddyConfigBuilder":
        """
        Configure the logging block.

        Parameters
        ----------
        writer : "stderr" | "stdout"
            Global sink output.
        level : str
            Log level for ``logger_name``.
        logger_name : str
            Name of the primary logger (default: ``"default"``).
        extra_logs : dict | None
            Additional loggers as ``{name: {level, writer}}``.
        """
        sink = LogSink(writer=writer)  # type: ignore[arg-type]
        logs: dict[str, LogEntry] = {
            logger_name: LogEntry(name=logger_name, level=level)  # type: ignore[arg-type]
        }
        for name, opts in (extra_logs or {}).items():
            logs[name] = LogEntry(
                name=name,
                level=opts.get("level"),  # type: ignore[arg-type]
                writer=opts.get("writer"),  # type: ignore[arg-type]
            )
        self._logging = Logging(sink=sink, logs=logs)
        return self

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------

    def _add_server(self, server: Server) -> None:
        self._servers.append(server)

    def server(
        self,
        name: str,
        listen: Optional[list[str]] = None,
    ) -> ServerBuilder:
        """
        Open a server builder.

        Parameters
        ----------
        name : str
            Server name (key in ``apps.http.servers``).
        listen : list[str] | None
            Initial listen addresses.
        """
        return ServerBuilder(name=name, listen=listen, parent=self)

    # ------------------------------------------------------------------
    # Final build
    # ------------------------------------------------------------------

    def build(self) -> CaddyConfig:
        """Build and return the final ``CaddyConfig``."""
        apps: Optional[Apps] = None
        if self._servers:
            servers = {s.name: s for s in self._servers}
            apps = Apps(http=HttpApp(servers=servers))
        return CaddyConfig(
            admin=self._admin,
            logging=self._logging,
            apps=apps,
        )

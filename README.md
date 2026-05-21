# caddyconfig

Caddy JSON configuration manipulation for Python, built on Pydantic v2.

Provides typed models, validation, a fluent builder API, and bidirectional
serialization to/from Caddy's native JSON format.

## Installation

```bash
pip install caddyconfig
```

Requires Python 3.10+.

## Quick Start

### Fluent Builder API

```python
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
            .match(path=["/api"])
            .handle_reverse_proxy("10.0.0.1:8080")
        .done()
    .done()
    .build()
)

print(config.to_json(indent=2))
```

### Direct Model API

```python
from caddyconfig import (
    CaddyConfig, Admin, Logging, LogSink, LogEntry,
    Apps, HttpApp, Server, Route, MatchCriteria,
    StaticResponseHandler, ReverseProxyHandler,
)

config = CaddyConfig(
    admin=Admin(listen="localhost:2019"),
    logging=Logging(
        sink=LogSink(writer="stderr"),
        logs={"default": LogEntry(name="default", level="info")},
    ),
    apps=Apps(
        http=HttpApp(
            servers={
                "main": Server(
                    name="main",
                    listen=[":443", ":80"],
                    routes=[
                        Route(
                            match=[MatchCriteria(host=["acme.com"])],
                            handle=[StaticResponseHandler(status_code=200, body="Welcome")],
                        ),
                        Route(
                            match=[MatchCriteria(path=["/api"])],
                            handle=[ReverseProxyHandler(upstreams=["10.0.0.1:8080"])],
                        ),
                    ],
                )
            }
        ),
    )
)
```

## JSON Roundtrip

```python
json_str = config.to_json()
config2 = CaddyConfig.from_json(json_str)
assert config2.to_dict() == config.to_dict()
```

## Route Lookup and Mutation

```python
server = config.apps.http.get_server("main")

# Find a route by matcher criteria (partial match supported)
route = server.find_route(MatchCriteria(path=["/api"]))

# Upsert: replace if exists, insert otherwise
server.upsert_route(MatchCriteria(path=["/api"]), new_route)

# Remove a route
server.remove_route(MatchCriteria(path=["/api"]))

# Search recursively through subroutes
route = server.find_route(MatchCriteria(path=["/api"]), recursive=True)
```

## Supported Handlers

| Handler | Model | Builder Method |
|---------|-------|----------------|
| `static_response` | `StaticResponseHandler` | `.handle_static(status, body=...)` |
| `reverse_proxy` | `ReverseProxyHandler` | `.handle_reverse_proxy("host:port")` |
| `file_server` | `FileServerHandler` | `.handle_file_server(root=...)` |
| `authentication` | `AuthenticationHandler` | `.handle_auth_basic(("u", "pw"))` |
| `subroute` | `SubrouteHandler` | `.handle_subroute()` |
| unknown types | `RawHandler` | `.handle(raw_handler)` |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_builder.py

# With coverage
uv run pytest --cov=caddyconfig
```

## License

Apache License 2.0

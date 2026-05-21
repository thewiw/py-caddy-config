# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`caddyconfig` is a Python library for building and manipulating Caddy web server configurations in JSON format. It provides Pydantic v2 models with validation, a fluent builder API, and bidirectional serialization (Python objects <-> Caddy JSON).

- Python: 3.10+ (project currently uses 3.13)
- Package manager: `uv`
- Dependencies: `pydantic>=2.0`
- Dev dependencies: `pytest>=8`, `pytest-cov>=7.1.0`

## Commands

| Task | Command |
|------|---------|
| Install dependencies | `uv sync` |
| Run all tests | `uv run pytest` |
| Run tests verbose | `uv run pytest -v` |
| Run single test file | `uv run pytest tests/test_builder.py` |
| Run single test | `uv run pytest tests/test_builder.py::TestRouteBuilderStandalone::test_build_empty` |
| Run with coverage | `uv run pytest --cov=caddyconfig` |

## Architecture

### Two APIs: Model + Builder

The library exposes two equivalent ways to construct configs:

1. **Direct models** (imperative):
   ```python
   from caddyconfig import CaddyConfig, Server, Route, MatchCriteria, StaticResponseHandler
   config = CaddyConfig(
       http=HttpApp(servers={
           "main": Server(name="main", listen=[":443"], routes=[
               Route(match=[MatchCriteria(host=["foo.com"])],
                     handle=[StaticResponseHandler(status_code=200)])
           ])
       })
   )
   ```

2. **Fluent builder** (chained):
   ```python
   from caddyconfig.builder import CaddyConfigBuilder
   config = (
       CaddyConfigBuilder()
       .server("main", listen=[":443"])
           .route().match(host=["foo.com"]).handle_static(200).done()
       .done()
       .build()
   )
   ```

Builders use `.done()` to return to the parent builder. Calling `.done()` on a builder without a parent raises `RuntimeError`.

### Custom Serialization is the Norm

Most model classes override `to_dict()` and `from_dict()` instead of relying on Pydantic's `model_dump`/`model_validate` alone. This is because Caddy's JSON format requires fine-grained control over what fields are emitted:

- **None values are excluded** (Caddy omits optional fields)
- **False booleans and empty collections are often excluded** (e.g. `Admin.disabled=False`, `Server.listen=[]`)
- **Special nested structures** (e.g. `Logging.sink` → `{"writer": {"output": "stderr"}}`)
- **Dict keys stored as attributes** use `Field(exclude=True)` — e.g. `Server.name` is the dict key in `apps.http.servers`, not an inline JSON field; same for `LogEntry.name`

When adding new models or fields, follow this pattern: inherit from `CaddyModel`, override `to_dict()` to conditionally include fields, and override `from_dict()` to handle Caddy's JSON shape.

### Handler Polymorphism via Registry

Handlers (reverse_proxy, file_server, static_response, authentication, subroute) are deserialized polymorphically using a class registry in `caddyconfig/handlers/__init__.py`:

- `@register_handler("handler_name")` decorator registers a class
- `handler_from_dict(data)` looks up the registry by `data["handler"]` and falls back to `RawHandler` for unknown types
- `RawHandler` uses `extra="allow"` to accept arbitrary fields
- All handlers inherit from `HandlerBase` which requires a `handler: str` discriminant field

When adding a new handler type: create the class in `caddyconfig/handlers/`, decorate it with `@register_handler("name")`, import it in `caddyconfig/__init__.py`, and add builder convenience methods in `builder.py`.

### MatchCriteria and Route Lookup

`MatchCriteria` supports host, path, header, regexp matchers, and nested `not` matchers (field `not_` with JSON alias `"not"`).

Route lookup/upsert/removal uses `MatchCriteria.matches_exactly()` which compares only non-None fields. This means you can find a route by partial criteria (e.g. just `host=["foo.com"]`) even if the route has additional matchers. The comparison is order-independent for lists.

`Server.find_route()` and `Server.upsert_route()` operate on either `routes` or `errors` depending on the `error=` flag. Subroutes are searched recursively by default.

### Key Files

| File | Purpose |
|------|---------|
| `caddyconfig/base.py` | `CaddyModel` — base class with serialization helpers |
| `caddyconfig/config.py` | `CaddyConfig` — root object, serializes to `apps.http` nesting |
| `caddyconfig/server.py` | `HttpApp`, `Server`, `Metrics` — server definitions and route CRUD |
| `caddyconfig/route.py` | `Route` — matchers + handlers, handler management |
| `caddyconfig/match.py` | `MatchCriteria` — request matchers with validation |
| `caddyconfig/builder.py` | Fluent builders: `CaddyConfigBuilder`, `ServerBuilder`, `RouteBuilder`, `SubrouteBuilder` |
| `caddyconfig/handlers/__init__.py` | `HandlerBase`, `RawHandler`, `@register_handler`, `handler_from_dict` |
| `caddyconfig/handlers/reverse_proxy.py` | `ReverseProxyHandler`, `UpstreamAddress` — validates dial format |
| `caddyconfig/handlers/subroute.py` | `SubrouteHandler` — nested routes with recursive find/upsert/remove |
| `caddyconfig/admin.py` | `Admin` — admin API config |
| `caddyconfig/logging.py` | `Logging`, `LogSink`, `LogEntry` |

### Testing Conventions

- Tests use pytest with classes grouped by component (e.g. `TestRouteBuilderStandalone`)
- Integration tests in `test_integration.py` cover end-to-end scenarios: build config, find routes, upsert, remove, JSON roundtrip
- Validation tests use `pydantic.ValidationError` assertions

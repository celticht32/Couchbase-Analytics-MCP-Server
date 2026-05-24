# Architecture

A short tour of how the pieces fit together.

## Process layout

One Python process, one event loop, two HTTP servers running concurrently:

```
asyncio loop
├── mcp.run_streamable_http_async()      ← bound to MCP_PORT (default 8000)
└── uvicorn(gui_app)                     ← bound to GUI_PORT (default 8080)
```

Both share:

- A single `ClientPool` (one `AnalyticsClient` per cluster, optional Capella)
- A single `AuditLog` (one writer thread, one file)
- A single `Metrics` registry (Prometheus exposition on `9100`)

Lifespan is owned by FastMCP; the GUI piggybacks on it.

## Layered design

```
┌─────────────────────────────────────────────────────────────┐
│  Claude (MCP)              Browser (GUI)                    │
└──────────┬────────────────────────┬─────────────────────────┘
           │                        │
           ▼                        ▼
   FastMCP (auth + tool       FastAPI (session +
   dispatch + lifespan)        Jinja2 + HTMX)
           │                        │
           ▼                        ▼
   ┌───────────────────────────────────────────┐
   │              tools/*  (55 tools)          │
   │  Each tool: _impl()  ← business logic     │
   │             register() ← wraps with       │
   │                          observability    │
   └───────────────┬───────────────────────────┘
                   ▼
           ┌──────────────┐
           │ ClientPool   │ ← keyed by cluster name
           └──────┬───────┘
                  ▼
        ┌──────────────────┐    ┌──────────────────┐
        │ AnalyticsClient  │    │ CapellaClient    │
        └────────┬─────────┘    └────────┬─────────┘
                 ▼                       ▼
        ┌────────────────┐      ┌────────────────────┐
        │ Couchbase REST │      │ Capella Cloud API  │
        └────────────────┘      └────────────────────┘
```

## Tool pattern

Each tool module exports an `_impl()` async function that takes the pool
and the tool's typed arguments. `register(mcp, pool, audit, metrics)` wraps
that impl with `call_tool_observed()`, which:

1. Starts a timer.
2. Calls the impl.
3. Catches `AnalyticsError` (typed) and any other exception, converting
   both to `{"ok": False, ...}` results — the conversation never crashes.
4. Records a Prometheus invocation + duration.
5. Writes one audit-log record with the redacted args and a small
   `result_summary` derived from the data.

This separation makes `_impl` directly unit-testable with a mocked pool
(see `tests/unit/mcp/test_tool_impls.py` — 67 tests).

## HTTP client

The internal Couchbase client lives in `couchbase/`. It is intentionally
small:

- `http_client.py`: an httpx wrapper with:
  - Basic auth
  - tenacity-driven exponential backoff for `ConnectError`, `ReadTimeout`,
    `RemoteProtocolError`, and 5xx
  - A hand-rolled async-native circuit breaker
    (`_AsyncCircuitBreaker`) — pybreaker's `call_async` is hard-coded for
    Tornado and not usable here
  - Status-code → typed-exception mapping
- `analytics_api.py`, `cluster_api.py`: one class per REST group. Each
  method takes typed Pydantic models in and out.
- `client.py`: the `AnalyticsClient` facade tying the per-group APIs to
  one shared `HttpClient`. The dataclass `AnalyticsClientConfig` lives at
  `client.cfg`; the service-config API lives at `client.config`.

## Configuration

`config.py` reads env vars (and optionally a JSON cluster file) into a
single dataclass tree:

```
AppConfig
├── ClusterConfig[]      (one per cluster)
├── capella_api_key?     (SecretStr)
├── GuiConfig
└── ObservabilityConfig
```

`load_config()` is the only public entrypoint; `validate_config()` checks
for missing required values and default GUI password / session secret.
`config_summary()` returns a redacted dict suitable for logging.

## Observability

| concern | module | output |
|---|---|---|
| Structured logs | `observability/logging.py` | stdout + optional file, JSON or console |
| Audit trail | `observability/audit.py` | dedicated JSON file, one line per tool call |
| Metrics | `observability/metrics.py` | Prometheus HTTP endpoint on `:9100` |
| Traces | `observability/tracing.py` | OTLP HTTP, opt-in |
| Redaction | `observability/redact.py` | shared by logs and audit |

The redactor is a structlog processor, so every log line that the JSON
renderer ever sees has already been through it.

## GUI

`gui/app.py` builds a FastAPI app that attaches the same `ClientPool`,
`AuditLog`, and `Metrics` to `app.state`. Routes:

- `routes/auth.py` — `/login`, `/logout`, `require_session()` dependency.
- `routes/dashboard.py` — `/`, the cluster overview.
- `routes/query.py` — `/query` (form) + `/query/run` (HTMX result fragment).
- `routes/admin.py` — `/admin`, audit log + config summary.
- `routes/logs.py` — `/logs` + `/logs/tail` (HTMX poll).

Templates are server-rendered Jinja2; the only client-side library is
HTMX, which keeps things crawlable and simple.

## Testing

- 411 unit tests, all using either `respx` (HTTP mocking) or `FakePool` /
  `FakeClient` (in-memory mocks of the client surface). No tests touch a
  real Couchbase cluster.
- The 52 tool impls are tested at the `_impl()` level — no FastMCP machinery
  in the test path.
- The GUI is tested via FastAPI's `TestClient` against the same mocked pool.

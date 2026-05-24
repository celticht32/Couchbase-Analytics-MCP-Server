# Changelog

All notable changes to cb-analytics are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] — 2026-05-24

### Added
- **Capella Analytics client** (`CapellaAnalyticsClient`) targeting
  `cloudapi.cloud.couchbase.com/v4/` with Bearer token auth
- **Analytics Library API** (`client.libraries`) — list, upload, delete UDF libraries.
  Upload restricted to local-origin; remote 403 raises `AnalyticsLibraryError` with
  clear explanation rather than generic auth error
- **`/eventsStreaming` SSE endpoint** — `client.cluster.stream_events()` async
  generator with `max_events` and `timeout_seconds` parameters
- **`GET/POST /settings/rebalance`** — `get_rebalance_settings()` / `configure_rebalance_settings()`
- **`GET/POST /pools/default/settings/memcached/global`** — `get_cluster_connections()` / `configure_cluster_connections()`
- **Manual async circuit breaker** — replaces `pybreaker` (incompatible with Python 3.12
  without Tornado). Opens after `circuit_fail_max` failures, auto-resets after
  `circuit_reset_timeout` seconds
- **`asyncio.timeout` outer guard** on every HTTP request to catch servers that accept
  connections but never send response bodies
- **Prometheus metrics** via `MetricsRegistry` — requests_total, request_duration,
  errors_total, circuit_state, active_requests
- **Proper `structlog` configuration** (`logging_setup.py`) with secret scrubbing,
  JSON and colored dev output modes
- **`CB_ANALYTICS_DEBUG`** environment variable — logs request method+path (never passwords)
- **SQL++ injection warning** — `UserWarning` emitted when a statement contains patterns
  that suggest string interpolation instead of parameterized queries
- **Auto-refresh timer in MonitorPanel** — configurable 15s/30s/60s or manual-only
  via dropdown; uses `call_from_thread()` for all widget updates
- **5 Claude skill files** in `skills/` directory for each major workflow area
- **`Makefile`** — `make test`, `lint`, `typecheck`, `security`, `coverage`, `docs`
- **`.pre-commit-config.yaml`** — ruff, pyflakes, mypy, bandit on every commit
- **`.github/dependabot.yml`** — weekly dependency update PRs
- `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`

### Fixed
- **CRITICAL: `pyproject.toml` invalid `copyright` field** broke `pip install` — removed
- **`password` was plain `str` in `AnalyticsClientConfig`** — now `SecretStr`; never
  appears in `repr()`, logs, or tracebacks
- **All credential fields in link models** (`secretAccessKey`, `accountKey`, `bindPass`)
  now `SecretStr`; unwrapped only via `to_api_dict()` at HTTP boundary
- **`model_dump(if v is not None)` silently stripped `0` and `False`** — replaced with
  `to_api_dict()` / `model_dump(exclude_unset=True)` throughout
- **`IngestionStatus` model shape** — now parses both list and dict API response formats
  via `IngestionStatus.from_raw()`
- **`params or None` inconsistency** — `get_completed_requests()` and `get_all_links()`
  now use `params if params else None`
- **GUI `MonitorPanel` widget updates from `@work` tasks** — all updates now use
  `call_from_thread()` to post to the main event loop
- **GUI `SchemaTab` NameError** — removed leftover React-style `callTool` / `onToolCall`
  calls; dataset click now properly awaits in `@work` context
- **5 unused imports in `gui/app.py`** — `asyncio`, `reactive`, `Vertical`, `Log`, `Markdown`
- **`asyncio` imported but unused in `http_client.py`**
- **`typing.Any` unused in `server_groups.py`**
- **6 unused imports across test files**
- **`structlog` imported but never configured** — now initialized by `configure_logging()`
- **`prometheus-client` declared as dependency but unused** — now fully wired up
- **README CI badge and clone URLs** pointed to wrong repo (`cahrendt`) — fixed to
  `celticht32/Couchbase-Analytics-MCP-Server`
- **`.github/workflows/ci.yml`** was not committed to the repo — now tracked
- **Test fixtures** passed `SecretStr` directly to `HttpClient` — fixed to call
  `.get_secret_value()`

### Changed
- Version bumped to `1.1.0`
- Coverage target raised to 95%
- `pybreaker` dependency removed; replaced with native `_AsyncCircuitBreaker`
- `circuit_fail_max` and `circuit_reset_timeout` exposed in `AnalyticsClientConfig`

---

## [1.0.0] — 2026-05-20

### Added
- Initial release with complete REST API coverage for Enterprise Analytics 2.1
- 8 API group classes, 60+ Pydantic v2 models
- Textual TUI with 6 panels
- Typer CLI
- 142 unit tests (respx mocks)
- Architecture SVG diagrams and GUI screenshots
- Word document with implementation guide (`docs/cb-analytics-documentation.docx`)

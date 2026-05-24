# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Configurable soft cap on full-result queries.** `execute_query` and
  `execute_query_readonly` now truncate to `MAX_QUERY_ROWS` (default 1000)
  and return `truncated: true` plus `full_row_count` so the caller knows to
  re-issue as paginated. `MAX_QUERY_ROWS=0` disables the cap entirely.
- **Per-tool rate limiting.** Token-bucket per API key per category:
  10 queries/sec, 60 reads/sec, 1 write/sec by default. Configurable via
  `RATE_LIMIT_QUERY_PER_SEC`, `RATE_LIMIT_READ_PER_SEC`,
  `RATE_LIMIT_WRITE_PER_SEC`. Setting a limit to 0 disables that bucket.
- **Audit log rotation.** Uses `RotatingFileHandler`; rotates at
  `AUDIT_ROTATE_BYTES` (default 10 MB) keeping `AUDIT_ROTATE_KEEP`
  generations (default 5). `AUDIT_ROTATE_BYTES=0` falls back to a plain
  unrotated file.
- **Dashboard Test Connection button** on every cluster row.
  Posts to `/cluster/{name}/test` and returns an inline result fragment
  with reachability + elapsed time, swapped into the row via HTMX.
- **Audit log search/filter in the GUI** — date range, tool dropdown
  (populated with every known tool, not just those seen in the log so
  far), and a failures-only checkbox. HTMX-driven: the form updates the
  table in place without a full page reload.
- **CLI for invoking tools** without going through Claude:
  - `cb-analytics-mcp tools list [--category {query,read,write}]`
  - `cb-analytics-mcp tools call NAME --arg KEY=VALUE [...] [--offline | --remote URL]`

  Offline mode instantiates the client pool in-process; remote mode sends
  an MCP JSON-RPC call to a running server using `MCP_API_KEY` as bearer.
- **Paginated query tool** (`execute_query_paginated`) — returns the first
  page plus a handle; `fetch_next_page(handle)` retrieves subsequent pages.
  Strips any trailing LIMIT/OFFSET on the user's statement so pagination
  applies cleanly.
- **Query plan tool** (`explain_query`) — prepends EXPLAIN to a SQL++
  statement and returns the plan. Useful for "why is this slow"
  investigations.
- **Result caching** for `execute_query_readonly` — TTL 60 seconds keyed by
  cluster, statement, and scan_consistency. Response includes a `cached`
  boolean.
- **WebSocket live log streaming** at `/logs/ws` on the GUI — replaces the
  5-second HTMX poll with a true push stream. Falls back to HTMX polling
  automatically when WebSockets aren't available.

### Changed
- Total MCP tool count: 52 → 55 (added the 3 query tools above).
- Total tests: 411 → 519. Coverage: 95.66 % → 94.04 %.

## [1.0.0] — 2026-05-24

Initial release.

### Added
- **55 MCP tools** across 10 groups: meta, schema, query, admin, config, links,
  libraries, security, cluster, and Capella.
- **Bundled FastAPI + HTMX GUI** with login, dashboard, SQL++ query editor,
  audit-log viewer, config explorer, and live log tail.
- **Multi-cluster support** via env vars or a JSON cluster file.
- **Capella Cloud Management API** integration (opt-in with
  `CB_CAPELLA_API_KEY_SECRET`).
- **Observability stack**: structured JSON logging (structlog), append-only
  audit log with redaction, Prometheus metrics, optional OpenTelemetry
  tracing.
- **Internal HTTP client** with exponential-backoff retry, an async-native
  circuit breaker, and consistent typed-exception mapping.
- **Hardened authentication**: bearer-token MCP auth and session-cookie GUI
  auth, both using `hmac.compare_digest`.
- **Health endpoints**: `/healthz` (liveness) and `/readyz` (cluster ping).
- **Docker image** (multi-stage, non-root) and `docker-compose.yml` with
  nginx TLS termination.
- **8 Claude Code skills** for setup, querying, schema, admin, links,
  security, cluster, and Capella workflows.
- **Documentation**: installation, configuration, connection, GUI guide,
  tool reference, observability, security, deployment, architecture.
- **286 unit tests** with mocked I/O (respx for HTTP, FakePool for the
  Couchbase client); 81 % line + branch coverage.
- **CI-ready scanners**: pyflakes, ruff, mypy (strict), bandit, all clean.

[Unreleased]: https://github.com/celticht32/cb-analytics-mcp/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/celticht32/cb-analytics-mcp/releases/tag/v1.0.0

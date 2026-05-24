# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-05-24

Initial release.

### Added
- **52 MCP tools** across 10 groups: meta, schema, query, admin, config, links,
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

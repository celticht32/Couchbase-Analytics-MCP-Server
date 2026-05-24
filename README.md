# cb-analytics-mcp

[![CI](https://github.com/celticht32/cb-analytics-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/celticht32/cb-analytics-mcp/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-94.04%25-brightgreen.svg)](https://github.com/celticht32/cb-analytics-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)

A standalone **MCP (Model Context Protocol) server** plus admin GUI for
**Couchbase Enterprise Analytics** and **Couchbase Capella Analytics**.
Connects to Claude (claude.ai, Claude Desktop, Claude Code) and exposes the
full Analytics REST surface as 55 well-typed, audited tools.

> © 2026 Chris Ahrendt — MIT licensed

---

## What you get

- **55 MCP tools** spanning query execution, schema introspection, ingestion
  control, link management, UDF libraries, RBAC, cluster admin, and Capella
  cloud management.
- **Paginated queries** for large result sets, with TTL caching for repeated
  reads, an `explain_query` tool for plan investigation, and a configurable
  soft cap on full-result queries (default 1000 rows; truncated responses
  include `truncated: true` and `full_row_count`).
- **Rate limiting** per API key, per tool category (10 query/sec, 60 read/sec,
  1 write/sec by default) so a runaway client can't melt your cluster.
- **Multi-cluster support** out of the box (one process, many Couchbase
  clusters).
- **Bundled web GUI** at `:8080` with login, SQL++ editor, paginated audit-log
  viewer with date / tool / failure filters, per-cluster Test Connection
  buttons, config explorer, and live log tail (WebSocket-streamed, with
  HTMX polling fallback).
- **CLI** for testing tools without a running server (`cb-analytics-mcp tools
  call <name> --offline`) or against a remote one (`--remote URL`).
- **Structured logging + audit trail + Prometheus metrics + OpenTelemetry**
  tracing — all opt-in but on by default for the basics. Audit log rotates
  at 10 MB by default and keeps 5 generations.
- **Hardened HTTP client** with retry, exponential backoff, async-native
  circuit breaker, and consistent error mapping.
- **Strict scans** — every release passes pyflakes, ruff, mypy strict, bandit,
  and pytest with 94 %+ coverage.

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/celticht32/cb-analytics-mcp
cd cb-analytics-mcp
make dev

# 2. Configure
cp .env.example .env
$EDITOR .env          # set MCP_API_KEY, CB_ANALYTICS_HOST, etc.

# 3. Run
make run              # starts MCP server on :8000 + GUI on :8080
```

Then open `http://localhost:8080` in a browser, or point Claude at
`http://localhost:8000/mcp` with the bearer token you set as `MCP_API_KEY`.

For reproducible builds in CI / Docker, install from the locked
`requirements.txt` instead of `pyproject.toml`:

```bash
pip install -r requirements.txt
pip install --no-deps -e .
```

Contributors can opt in to pre-commit hooks (ruff, mypy, bandit run on
every commit):

```bash
pip install pre-commit && pre-commit install
```

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Connecting Claude.ai / Desktop / Code](docs/connecting-claude-ai.md)
- [GUI walkthrough](docs/gui-guide.md)
- [Tool reference (all 55 tools)](docs/tool-reference.md)
- [Observability — logs, metrics, traces, audit](docs/observability.md)
- [Security model](docs/security.md)
- [Deployment (Docker, Compose, TLS)](docs/deployment.md)
- [Architecture](docs/architecture.md)

## Project layout

```
cb-analytics-mcp/
├── src/cb_analytics_mcp/
│   ├── auth.py              # bearer-token verifier
│   ├── config.py            # env-driven config loader
│   ├── pool.py              # connection pool (clusters + Capella)
│   ├── server.py            # FastMCP wire-up
│   ├── __main__.py          # entrypoint (server / GUI / --check)
│   ├── couchbase/           # internal HTTP client (no SDK dep)
│   ├── observability/       # logging, audit, metrics, tracing
│   ├── tools/               # 10 modules × 55 MCP tools
│   └── gui/                 # FastAPI + HTMX admin GUI
├── tests/unit/              # 411 unit tests, mocked I/O
├── docs/                    # MkDocs-ready Markdown
├── .claude/skills/          # 8 Claude Code skills
├── scripts/                 # deep_scan.sh, make_screenshots.py
└── pyproject.toml
```

## Make targets

| target | description |
|---|---|
| `make dev` | Install with dev extras (pytest, ruff, mypy, bandit, playwright) |
| `make run` | Run MCP server + GUI |
| `make gui` | Run just the GUI |
| `make test` | Run unit tests |
| `make coverage` | Tests with HTML coverage report, 95.66 % currently |
| `make scan` | pyflakes + ruff + mypy + bandit + tests |
| `make screenshots` | Generate documentation screenshots via Playwright |
| `make docker` | Build the Docker image |

## Quality bar

Every release must pass `make scan`. Current numbers:

| metric | value |
|---|---|
| Unit tests | 519 ✓ |
| Coverage | 94.04 % |
| pyflakes / ruff / mypy strict / bandit / pip-audit | ✓ clean |
| Python | 3.11, 3.12, 3.13 |

## Future possibilities

Things that aren't built yet but would be obvious next steps. Issues and
PRs welcome on any of these:

- **Query history in the GUI.** The query editor loses your statement on
  page reload. A small dropdown of recent queries (in-memory only, scoped
  to the current GUI session) would be ergonomic. The audit log already
  has every executed statement; this is just surfacing it in the editor.
- **DDL helper tools.** `create_dataverse`, `create_dataset`, `drop_dataset`,
  `create_index`, `drop_index` as typed tools instead of relying on Claude
  to compose raw SQL++. Safer, less ambiguous.
- **Bucket / scope / collection awareness.** Today's schema tools work at
  dataverse level, but real Couchbase deployments use buckets → scopes →
  collections. `list_buckets`, `list_scopes(bucket)`, `list_collections(...)`
  would help Claude navigate clusters it hasn't seen before.
- **Integration tests against a real Couchbase.** The 519 unit tests use
  mocks; a small `tests/integration/` suite that spins up
  `couchbase/server:enterprise-7.6` in a Docker container would catch
  things mocks can't (real timeouts, real auth flows, edge cases in the
  Analytics REST surface).
- **Per-team / per-project API keys.** Today the MCP server accepts a single
  bearer token. Larger deployments would want per-team tokens with their
  own audit attribution and RBAC scope.
- **Tracing across the Couchbase REST boundary.** OpenTelemetry currently
  stops at the MCP boundary. Instrumenting the outgoing `httpx` requests
  would give full traces from Claude → MCP → Couchbase.
- **Distributed rate limits / pagination state.** The current implementations
  are in-process. Scaling out horizontally would need a shared store
  (Redis or similar).

## Acknowledgements

This project speaks to Couchbase through its public REST API. It is **not**
an official Couchbase product. "Couchbase" and "Couchbase Capella" are
trademarks of Couchbase, Inc.

## License

MIT — see [LICENSE](LICENSE).

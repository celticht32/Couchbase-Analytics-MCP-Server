# cb-analytics-mcp

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)

A standalone **MCP (Model Context Protocol) server** plus admin GUI for
**Couchbase Enterprise Analytics** and **Couchbase Capella Analytics**.
Connects to Claude (claude.ai, Claude Desktop, Claude Code) and exposes the
full Analytics REST surface as 52 well-typed, audited tools.

> © 2026 Chris Ahrendt — MIT licensed

---

## What you get

- **52 MCP tools** spanning query execution, schema introspection, ingestion
  control, link management, UDF libraries, RBAC, cluster admin, and Capella
  cloud management.
- **Multi-cluster support** out of the box (one process, many Couchbase
  clusters).
- **Bundled web GUI** at `:8080` with login, SQL++ editor, audit-log viewer,
  config explorer, and live log tail.
- **Structured logging + audit trail + Prometheus metrics + OpenTelemetry**
  tracing — all opt-in but on by default for the basics.
- **Hardened HTTP client** with retry, exponential backoff, async-native
  circuit breaker, and consistent error mapping.
- **Strict scans** — every release passes pyflakes, ruff, mypy strict, bandit,
  and pytest with ≥80 % coverage.

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

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Connecting Claude.ai / Desktop / Code](docs/connecting-claude-ai.md)
- [GUI walkthrough](docs/gui-guide.md)
- [Tool reference (all 52 tools)](docs/tool-reference.md)
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
│   ├── tools/               # 10 modules × 52 MCP tools
│   └── gui/                 # FastAPI + HTMX admin GUI
├── tests/unit/              # 286 unit tests, mocked I/O
├── docs/                    # MkDocs-ready Markdown
├── skills/                  # 8 Claude Code skills
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
| `make coverage` | Tests with HTML coverage report, ≥80 % required |
| `make scan` | pyflakes + ruff + mypy + bandit + tests |
| `make screenshots` | Generate documentation screenshots via Playwright |
| `make docker` | Build the Docker image |

## Quality bar

Every release must pass `make scan`. Current numbers:

| metric | value |
|---|---|
| Unit tests | 286 ✓ |
| Coverage | 81.7 % |
| pyflakes / ruff / mypy strict / bandit | ✓ clean |
| Python | 3.11, 3.12, 3.13 |

## Acknowledgements

This project speaks to Couchbase through its public REST API. It is **not**
an official Couchbase product. "Couchbase" and "Couchbase Capella" are
trademarks of Couchbase, Inc.

## License

MIT — see [LICENSE](LICENSE).

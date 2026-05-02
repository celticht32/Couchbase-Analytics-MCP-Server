# cb-analytics

> **Python SDK, CLI, and Terminal UI for the Couchbase Enterprise Analytics REST API**

Copyright © 2026 [Chris Ahrendt](https://github.com/cahrendt) · [MIT License](LICENSE)

[![CI](https://github.com/cahrendt/cb-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/cahrendt/cb-analytics/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-111%20passing-brightgreen)](tests/)

A **complete, production-ready** Python implementation of every documented endpoint in the [Couchbase Enterprise Analytics REST API](https://docs.couchbase.com/enterprise-analytics/current/reference/rest-intro.html). Fully typed with Pydantic v2, async-first with httpx, and exposed through a keyboard-driven Textual TUI, a Typer CLI, and a clean Python SDK.

---

## Screenshots

### Connection Screen
![Connection Screen](docs/screenshots/01-connection-screen.svg)

### SQL++ Query Editor
![Query Tab](docs/screenshots/02-query-tab.svg)

### Service Monitor
![Monitor Tab](docs/screenshots/03-monitor-tab.svg)

### RBAC User & Group Management
![RBAC Tab](docs/screenshots/04-rbac-tab.svg)

### Analytics Links
![Links Tab](docs/screenshots/05-links-tab.svg)

### Cluster Overview
![Cluster Tab](docs/screenshots/06-cluster-tab.svg)

### CLI Output
![CLI](docs/screenshots/07-cli-output.svg)

---

## Architecture Diagrams

### System Architecture
![System Architecture](docs/diagrams/01-system-architecture.svg)

### Request Lifecycle
![Request Lifecycle](docs/diagrams/02-request-lifecycle.svg)

### API Groups & Endpoint Coverage
![API Groups](docs/diagrams/03-api-groups.svg)

### Exception Hierarchy
![Exceptions](docs/diagrams/04-exception-hierarchy.svg)

### Configuration Flow
![Configuration](docs/diagrams/05-configuration-flow.svg)

---

## Feature Overview

| Feature | Details |
|---|---|
| **Complete API coverage** | Every endpoint from the official REST API reference |
| **8 API group classes** | Cluster, AnalyticsService, AnalyticsAdmin, AnalyticsConfig, AnalyticsSettings, AnalyticsLinks, Security, ServerGroups |
| **60+ Pydantic v2 models** | Full request/response type safety with validation |
| **Async-first** | Built on `httpx.AsyncClient` throughout |
| **Auto-retry** | Tenacity exponential backoff for transient errors |
| **Textual TUI** | 6-panel keyboard-driven terminal interface |
| **Typer CLI** | Full command coverage: query, admin, config, links, security, cluster |
| **pydantic-settings** | `CB_ANALYTICS_*` environment variable configuration |
| **111 unit tests** | All mocked with `respx` — no real cluster required |
| **24 integration tests** | Auto-skip without `CB_ANALYTICS_HOST` |
| **GitHub Actions CI** | Lint → type-check → unit → integration → build |
| **MIT License** | Copyright © 2026 Chris Ahrendt |

---

## Quick Start

```bash
pip install cb-analytics

# Execute a SQL++ query
CB_ANALYTICS_HOST=localhost \
CB_ANALYTICS_USERNAME=Administrator \
CB_ANALYTICS_PASSWORD=password \
  cb-analytics query execute "SELECT 1 AS ping"

# Launch the TUI
cb-analytics-gui

# Check cluster health
cb-analytics cluster ping && cb-analytics admin status
```

---

## Installation

```bash
pip install cb-analytics                  # production
pip install "cb-analytics[dev]"           # + testing & linting tools

# from source
git clone https://github.com/cahrendt/cb-analytics.git
cd cb-analytics && pip install -e ".[dev]"
```

**Requires:** Python 3.11+, Couchbase Enterprise Analytics 2.0+

---

## Configuration

All settings read from `CB_ANALYTICS_*` env vars, a `.env` file, or constructor kwargs.

| Variable | Default | Description |
|---|---|---|
| `CB_ANALYTICS_HOST` | `localhost` | Cluster hostname |
| `CB_ANALYTICS_MGMT_PORT` | `8091` | Management port (18091 for TLS) |
| `CB_ANALYTICS_ANALYTICS_PORT` | `8095` | Analytics port (18095 for TLS) |
| `CB_ANALYTICS_USERNAME` | `Administrator` | RBAC username |
| `CB_ANALYTICS_PASSWORD` | `password` | RBAC password |
| `CB_ANALYTICS_TLS` | `false` | Enable HTTPS |
| `CB_ANALYTICS_VERIFY_SSL` | `true` | Verify TLS certs |
| `CB_ANALYTICS_TIMEOUT_SECONDS` | `60.0` | Per-request timeout |
| `CB_ANALYTICS_MAX_RETRIES` | `3` | Retry count for transient errors |

---

## Python SDK

```python
import asyncio
from cb_analytics import AnalyticsClient, AnalyticsClientConfig
from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency, UserUpsertRequest, RbacDomain

async def main():
    async with AnalyticsClient(AnalyticsClientConfig(host="localhost")) as client:

        # SQL++ with request-plus consistency
        result = await client.analytics.execute(
            AnalyticsQueryRequest(
                statement="SELECT a.airlinename, COUNT(*) AS routes FROM `Default`.airline a LIMIT 5",
                scan_consistency=ScanConsistency.REQUEST_PLUS,
                timeout="30s",
            )
        )
        print(result.results, result.metrics.elapsedTime)

        # Cancel a running query
        await client.admin.cancel_request("ctx-id-123")

        # Update config
        from cb_analytics.models import ServiceConfig
        await client.config.update_service_config(ServiceConfig(resultTtl=7200))

        # Create RBAC user
        await client.security.upsert_user(
            RbacDomain.LOCAL, "alice",
            UserUpsertRequest(password="Pass123!", roles="analytics_reader[*]")
        )

        # List Analytics links
        links = await client.links.get_all_links(link_type="s3")

asyncio.run(main())
```

### Error handling

```python
from cb_analytics.exceptions import AnalyticsQueryError, AnalyticsAuthError, AnalyticsError

try:
    result = await client.analytics.execute(AnalyticsQueryRequest(statement="BAD SQL"))
except AnalyticsQueryError as e:
    print(f"Query error [{e.code}] line {e.line}: {e}")
except AnalyticsAuthError:
    print("Check credentials and RBAC roles")
except AnalyticsError as e:
    print(f"SDK error: {e}")
```

---

## CLI Reference

```bash
cb-analytics query execute "SELECT 1 AS n"
cb-analytics query execute "SELECT * FROM airline" --consistency request_plus --timeout 60s
cb-analytics query explain "SELECT COUNT(*) FROM airline"

cb-analytics admin status
cb-analytics admin active-requests
cb-analytics admin ingestion

cb-analytics config get-service
cb-analytics config set resultTtl 7200

cb-analytics links list
cb-analytics links list --type s3 --dataverse Default

cb-analytics security users
cb-analytics security roles

cb-analytics cluster info
cb-analytics cluster tasks
cb-analytics cluster ping

cb-analytics-gui          # launch TUI
```

---

## TUI Key Bindings

| Key | Action |
|-----|--------|
| `F1` | Query — SQL++ editor with results table |
| `F2` | Monitor — active queries, service status |
| `F3` | Config — service/node configuration viewer |
| `F4` | RBAC — users and groups management |
| `F5` | Links — analytics link overview |
| `F6` | Cluster — nodes, server groups, tasks |
| `Ctrl+R` | Refresh current panel |
| `Ctrl+Q` | Quit |

---

## Running Tests

```bash
# Unit tests — no Couchbase required (111 tests, ~0.7s)
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=cb_analytics --cov-report=html

# Integration tests — requires running Couchbase
docker-compose up -d
CB_ANALYTICS_HOST=localhost pytest tests/integration/ -v

# All tests
pytest
```

---

## Project Structure

```
cb-analytics/
├── LICENSE                             MIT © 2026 Chris Ahrendt
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── src/cb_analytics/
│   ├── client.py                       AnalyticsClient — unified facade
│   ├── config.py                       pydantic-settings config
│   ├── http_client.py                  httpx + tenacity retry
│   ├── exceptions.py                   Typed exception hierarchy
│   ├── cli.py                          Typer CLI
│   ├── models/__init__.py              60+ Pydantic v2 models
│   ├── api/analytics.py                Service / Admin / Config / Settings / Links
│   ├── api/cluster.py                  40+ cluster endpoints
│   ├── api/security.py                 35+ security/RBAC endpoints
│   ├── api/server_groups.py            Server Group Awareness
│   └── gui/app.py                      Textual TUI (6 panels)
├── tests/
│   ├── unit/                           111 mocked unit tests
│   └── integration/                    24 live integration tests
└── docs/
    ├── diagrams/                       Architecture SVGs
    ├── screenshots/                    GUI/CLI screenshot SVGs
    ├── architecture/ARCHITECTURE.md
    └── INTEGRATION_GUIDE.md
```

---

## License

MIT License — Copyright © 2026 Chris Ahrendt. See [LICENSE](LICENSE) for full text.

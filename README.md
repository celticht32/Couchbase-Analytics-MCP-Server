# cb-analytics

> **Python SDK, CLI, and Terminal UI for Couchbase Enterprise Analytics and Capella Analytics**

Copyright © 2026 [Chris Ahrendt](https://github.com/cahrendt) · [MIT License](LICENSE)

[![CI](https://github.com/celticht32/Couchbase-Analytics-MCP-Server/actions/workflows/ci.yml/badge.svg)](https://github.com/celticht32/Couchbase-Analytics-MCP-Server/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-154%20passing-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A595%25-brightgreen)](tests/)
[![Version](https://img.shields.io/badge/version-1.1.0-blue)](CHANGELOG.md)

Complete Python implementation of every documented endpoint in the [Couchbase Enterprise Analytics REST API](https://docs.couchbase.com/enterprise-analytics/current/reference/rest-intro.html) plus the [Capella Analytics Management API v4](https://docs.couchbase.com/analytics/management-api-guide/management-api-intro.html). Fully typed with Pydantic v2, async-first with `httpx`, protected by an async-native circuit breaker, instrumented with Prometheus metrics, and delivered with a 6-panel keyboard-driven Textual TUI and a Typer CLI.

---

## Contents

- [Screenshots](#screenshots)
- [Architecture Diagrams](#architecture-diagrams)
- [Feature Overview](#feature-overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Python SDK](#python-sdk)
- [Capella Analytics Client](#capella-analytics-client)
- [CLI Reference](#cli-reference)
- [TUI Key Bindings](#tui-key-bindings)
- [Claude Skills](#claude-skills)
- [Running Tests](#running-tests)
- [Documentation](#documentation)
- [License](#license)

---

## Screenshots

### Connection Screen
![Connection Screen](docs/screenshots/01-connection-screen.svg)

### SQL++ Query Editor
![Query Tab](docs/screenshots/02-query-tab.svg)

### Service Monitor — with configurable auto-refresh (15s / 30s / 60s / manual)
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

### Request Lifecycle — including circuit breaker and asyncio.timeout guard
![Request Lifecycle](docs/diagrams/02-request-lifecycle.svg)

### API Groups & Endpoint Coverage
![API Groups](docs/diagrams/03-api-groups.svg)

### Exception Hierarchy
![Exceptions](docs/diagrams/04-exception-hierarchy.svg)

### Configuration Flow
![Configuration](docs/diagrams/05-configuration-flow.svg)

---

## Feature Overview

| Feature | Detail |
|---|---|
| **Complete API coverage** | Every endpoint from the Couchbase Enterprise Analytics 2.x REST API |
| **Capella Analytics client** | `CapellaAnalyticsClient` — Bearer token auth, `cloudapi.cloud.couchbase.com/v4/` |
| **9 API group classes** | `cluster` · `analytics` · `admin` · `config` · `settings` · `links` · `libraries` · `security` · `server_groups` |
| **Analytics Library API** | UDF library management: list, upload¹, delete |
| **SSE event stream** | `client.cluster.stream_events()` — async generator over `/eventsStreaming` |
| **60+ Pydantic v2 models** | Full request/response type safety; all credentials use `SecretStr` |
| **Async-first** | `httpx.AsyncClient` throughout; every method is `async` |
| **Async circuit breaker** | Native `asyncio` — no Tornado dependency; Python 3.11 and 3.12 compatible |
| **Auto-retry** | Tenacity exponential backoff — retries connection errors and 5xx, never auth errors |
| **`asyncio.timeout` guard** | Outer timeout on every request — catches servers that accept but never respond |
| **Prometheus metrics** | `requests_total`, `request_duration_seconds`, `errors_total`, `circuit_state`, `active_requests` |
| **Structured logging** | `structlog` with secret scrubbing — passwords never appear in logs |
| **SQL++ injection warning** | `UserWarning` emitted when a statement looks string-interpolated |
| **Textual TUI** | 6-panel keyboard-driven interface; MonitorPanel has configurable auto-refresh |
| **Typer CLI** | `cb-analytics` command with subgroups: `query`, `admin`, `config`, `links`, `security`, `cluster` |
| **`CB_ANALYTICS_*` config** | All settings readable from environment variables or a `.env` file |
| **154 unit tests** | All mocked with `respx` — zero real-cluster calls required |
| **95% coverage target** | Enforced by `--cov-fail-under=95` in CI |
| **GitHub Actions CI** | lint → typecheck → security → unit (Py 3.11 + 3.12) → integration → build |
| **Dependabot** | Weekly dependency update PRs |
| **5 Claude skill files** | Teach Claude.ai how to use this SDK — query, schema discovery, admin, links, security |

¹ UDF library **upload** requires the request to originate locally from an Analytics node. Remote upload returns HTTP 403 and the SDK raises `AnalyticsLibraryError` with a clear message rather than a generic auth error. List and delete work remotely without restriction.

---

## Quick Start

```bash
pip install cb-analytics

# Run a SQL++ query
CB_ANALYTICS_HOST=localhost \
CB_ANALYTICS_USERNAME=Administrator \
CB_ANALYTICS_PASSWORD=password \
  cb-analytics query execute "SELECT 1 AS ping"

# Launch the interactive TUI
cb-analytics-gui

# Health check (exit 0 = connected)
cb-analytics cluster ping
```

---

## Installation

```bash
# From PyPI
pip install cb-analytics

# With development tools (pytest, ruff, mypy, bandit, pre-commit)
pip install "cb-analytics[dev]"

# From source
git clone https://github.com/celticht32/Couchbase-Analytics-MCP-Server.git
cd Couchbase-Analytics-MCP-Server
pip install -e ".[dev]"
pre-commit install
```

**Requires:** Python 3.11 or 3.12 · Couchbase Enterprise Analytics 2.x

---

## Configuration

All settings are read from `CB_ANALYTICS_*` environment variables, a `.env` file in the working directory, or passed directly as constructor keyword arguments (highest priority).

| Variable | Default | Description |
|---|---|---|
| `CB_ANALYTICS_HOST` | `localhost` | Cluster hostname or IP |
| `CB_ANALYTICS_MGMT_PORT` | `8091` | Management port — auto-selects `18091` when `TLS=true` |
| `CB_ANALYTICS_ANALYTICS_PORT` | `8095` | Analytics port — auto-selects `18095` when `TLS=true` |
| `CB_ANALYTICS_USERNAME` | `Administrator` | RBAC username |
| `CB_ANALYTICS_PASSWORD` | _(none)_ | RBAC password — stored as `SecretStr`; never appears in logs or `repr()` |
| `CB_ANALYTICS_TLS` | `false` | Enable HTTPS |
| `CB_ANALYTICS_VERIFY_SSL` | `true` | Verify TLS certificates; set `false` for self-signed dev clusters |
| `CB_ANALYTICS_TIMEOUT_SECONDS` | `60.0` | Per-request `httpx` timeout in seconds |
| `CB_ANALYTICS_MAX_RETRIES` | `3` | Tenacity retry attempts for connection errors and 5xx |
| `CB_ANALYTICS_DEBUG` | `false` | Log request method + path to stdout — **never logs passwords** |
| `CB_ANALYTICS_CIRCUIT_FAIL_MAX` | `5` | Consecutive failures before circuit breaker opens |
| `CB_ANALYTICS_CIRCUIT_RESET_TIMEOUT` | `30` | Seconds before an open circuit allows one probe request |

---

## Python SDK

### Basic connection

```python
import asyncio
from cb_analytics import AnalyticsClient, AnalyticsClientConfig

async def main():
    # Reads CB_ANALYTICS_* env vars automatically when called with no args
    async with AnalyticsClient() as client:
        print(await client.ping())   # True if cluster responds

asyncio.run(main())
```

### SQL++ query execution

Always use `args=` or `named_args=` instead of f-strings. The SDK emits a `UserWarning` if it detects string interpolation in a statement.

```python
from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency

# Positional parameters
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT * FROM `Default`.airline WHERE id = $1",
        args=[42],
        scan_consistency=ScanConsistency.REQUEST_PLUS,
        timeout="30s",
    )
)
print(result.results)              # list[Any]
print(result.metrics.elapsedTime)  # e.g. "142ms"
print(result.metrics.resultCount)  # int

# Named parameters
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT * FROM `Default`.airline WHERE callsign = $callsign",
        named_args={"callsign": "UAL"},
    )
)
```

### Streaming events (SSE)

```python
# Async generator — yields SystemEvent Pydantic objects
async for event in client.cluster.stream_events(max_events=50, timeout_seconds=60.0):
    print(event.timestamp, event.severity, event.description)
```

### Admin and monitoring

```python
# Service health
status = await client.admin.get_service_status()
print(status.state)           # "ACTIVE" | "INACTIVE" | "BOOTSTRAP"
print(status.ccRevLag)        # revision lag — high means cluster sync delay

# Ingestion freshness
ingestion = await client.admin.get_ingestion_status()
for link in ingestion.links:
    print(link.name, link.state)   # "CONNECTED" | "DISCONNECTED"

# Running queries
active = await client.admin.get_active_requests()
for req in active:
    print(req.clientContextID, req.elapsedTime, req.state)

# Cancel a query
await client.admin.cancel_request("ctx-abc-123")
```

### Analytics links

```python
from cb_analytics.models import S3LinkConfig, CouchbaseLinkConfig, EncryptionLevel

# Create an S3 link — credentials stored as SecretStr internally
await client.links.create_link(
    name="myS3Link",
    dataverse="Default",
    config=S3LinkConfig(
        region="us-east-1",
        accessKeyId="AKIAIOSFODNN7EXAMPLE",
        secretAccessKey="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    ),
)

links = await client.links.get_all_links()
await client.links.delete_link("myS3Link")
```

### UDF library management

```python
# List all UDF libraries
libs = await client.libraries.list_libraries()

# Delete a library (works remotely)
await client.libraries.delete_library(scope="Default", library_name="mylib")

# Upload — MUST be called from an Analytics node (remote calls raise AnalyticsLibraryError)
await client.libraries.upload_library("Default", "mylib", "python", open("mylib.pyz","rb").read())
```

### RBAC

```python
from cb_analytics.models import RbacDomain, UserUpsertRequest

await client.security.upsert_user(
    domain=RbacDomain.LOCAL,
    username="alice",
    request=UserUpsertRequest(
        password="SecurePass123!",    # SecretStr — never logged
        roles="analytics_reader[*]",
        name="Alice Smith",
    ),
)
users = await client.security.list_users()
```

### Error handling

```python
from cb_analytics.exceptions import (
    AnalyticsQueryError,       # SQL++ error — carries code, line, column
    AnalyticsAuthError,        # 401 / 403
    AnalyticsNotFoundError,    # 404
    AnalyticsRequestError,     # 400 / 409
    AnalyticsServerError,      # 5xx — retried automatically
    AnalyticsConnectionError,  # network / timeout — retried automatically
    AnalyticsCircuitOpenError, # circuit breaker open — wait reset_timeout seconds
    AnalyticsLibraryError,     # UDF library error (e.g. remote upload blocked)
    AnalyticsError,            # base class — catches all of the above
)

try:
    result = await client.analytics.execute(
        AnalyticsQueryRequest(statement="SELECT * FROM nonexistent")
    )
except AnalyticsQueryError as e:
    print(f"SQL error [{e.code}] at line {e.line}, col {e.column}: {e}")
except AnalyticsCircuitOpenError:
    print("Cluster unreachable — circuit open, retrying later")
except AnalyticsError as e:
    print(f"SDK error: {e}")
```

---

## Capella Analytics Client

Targets `https://cloudapi.cloud.couchbase.com/v4/` with Bearer token authentication. This is a separate product from self-managed Enterprise Analytics — it manages cluster lifecycle rather than executing queries.

```python
from cb_analytics.capella import CapellaAnalyticsClient, CapellaConfig

# CB_CAPELLA_API_KEY_SECRET env var is read automatically
config = CapellaConfig(api_key_secret="my-api-key-secret")

async with CapellaAnalyticsClient(config) as capella:
    # Organizations
    orgs = await capella.list_organizations()

    # Clusters
    clusters = await capella.list_clusters(org_id="org-id", project_id="proj-id")
    cluster  = await capella.get_cluster("org-id", "proj-id", "cluster-id")
    await capella.create_cluster("org-id", "proj-id", {"name": "my-cluster", ...})
    await capella.delete_cluster("org-id", "proj-id", "cluster-id")

    # Backups
    backups = await capella.list_backups("org-id", "proj-id", "cluster-id")
    await capella.create_backup("org-id", "proj-id", "cluster-id")
    await capella.restore_backup("org-id", "proj-id", "cluster-id", "backup-id")

    # API keys
    keys = await capella.list_api_keys("org-id")
    await capella.create_api_key("org-id", {"name": "my-key", "roles": [...]})
    await capella.delete_api_key("org-id", "key-id")
```

---

## CLI Reference

```
cb-analytics query execute "SQL"               Execute SQL++ — prints results as table
cb-analytics query execute "SQL" \
  --consistency request_plus                   With scan consistency
cb-analytics query explain "SQL"               Print query execution plan

cb-analytics admin status                      Analytics service state + nodes
cb-analytics admin active-requests             List running queries
cb-analytics admin ingestion                   Per-link ingestion status

cb-analytics config get-service                Service-level configuration
cb-analytics config set <param> <value>        Update a configuration parameter

cb-analytics links list                        All Analytics links
cb-analytics links list --type s3              Filter by link type

cb-analytics security users                    RBAC users and their roles
cb-analytics security roles                    All available roles

cb-analytics cluster info                      Nodes, memory quotas, cluster name
cb-analytics cluster tasks                     Active cluster tasks (rebalance, etc.)
cb-analytics cluster ping                      Connectivity check — exit 0 = success
```

Global options available on every command: `--host`, `--port`, `--username`, `--password`.

---

## TUI Key Bindings

| Key | Tab / Action |
|---|---|
| `F1` | **Query** — SQL++ editor, scan consistency selector, results table, metrics |
| `F2` | **Monitor** — service status, circuit breaker state, ingestion, active/completed requests, auto-refresh |
| `F3` | **Config** — live service and node configuration viewer |
| `F4` | **RBAC** — users, domains, roles, and group management |
| `F5` | **Links** — Analytics link overview with type and active dataset count |
| `F6` | **Cluster** — nodes, server groups, active cluster tasks |
| `Ctrl+R` | Refresh the current panel |
| `Ctrl+Q` | Quit |
| `Escape` | Quit (connection screen) |

---

## Claude Skills

Five skill files in `skills/` teach Claude.ai how to use this SDK correctly. Load them when deploying this server in a Claude environment.

| File | Teaches Claude |
|---|---|
| [`cb-analytics-query.md`](skills/cb-analytics-query.md) | SQL++ syntax, backtick quoting, parameterized queries, scan consistency, response shape, common error codes |
| [`cb-analytics-schema.md`](skills/cb-analytics-schema.md) | **Mandatory discovery workflow** — always query `Metadata` before writing SELECT statements to avoid hallucinated dataset names |
| [`cb-analytics-admin.md`](skills/cb-analytics-admin.md) | Health check sequence, cancelling queries, config tuning, when to restart node vs service |
| [`cb-analytics-links.md`](skills/cb-analytics-links.md) | Link types and auth models, credential SecretStr handling, disconnect-before-delete requirement |
| [`cb-analytics-security.md`](skills/cb-analytics-security.md) | Minimum RBAC roles per operation, `check_permissions()` workflow, SecretStr password handling |

---

## Running Tests

```bash
make test          # 154 unit tests, no Couchbase required (~0.8s)
make coverage      # unit tests + HTML coverage report (target: ≥95%)
make lint          # ruff + pyflakes
make typecheck     # mypy strict
make security      # bandit
make integration   # requires CB_ANALYTICS_HOST — spins up against a live cluster
make all           # lint + typecheck + security + coverage
```

**Test files and what they cover:**

| File | Tests | Covers |
|---|---|---|
| `test_analytics_api.py` | 24 | SQL++ execute, admin, config, settings, links, library API |
| `test_cluster_api.py` | 35 | All ClusterAPI methods and error mapping |
| `test_security_api.py` | 28 | RBAC, certs, LDAP, SAML, audit, secrets |
| `test_server_groups_and_models.py` | 24 | ServerGroups, Pydantic models, exceptions, config |
| `test_http_client_and_edge_cases.py` | 28 | HTTP status mapping, SecretStr, circuit breaker, retry, injection warning |
| `test_capella_client.py` | 11 | Capella Management API — auth, CRUD, error handling |
| `test_observability.py` | 5 | Prometheus MetricsRegistry |
| `test_integration.py` | 24 | Live cluster end-to-end (auto-skipped without `CB_ANALYTICS_HOST`) |

---

## Documentation

| File | Contents |
|---|---|
| [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) | Deep-dive architecture, component responsibilities, design decisions |
| [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md) | Step-by-step integration patterns, security hardening, deployment |
| [`docs/cb-analytics-documentation.docx`](docs/cb-analytics-documentation.docx) | Word document — cover page, all diagrams, full implementation guide, API reference |
| [`CHANGELOG.md`](CHANGELOG.md) | Detailed change log — what changed and why in each release |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Dev setup, test standards, PR process, coding conventions |
| [`SECURITY.md`](SECURITY.md) | How to report vulnerabilities; credential and TLS security guidance |

> **Future improvement:** the `.docx` is committed for convenience but can be regenerated at any time with `node docs/build_doc.js`. Moving it to a GitHub Release asset and building it in CI on each tag is a clean alternative that removes binary files from clone history.

---

## License

MIT License — Copyright © 2026 Chris Ahrendt. See [LICENSE](LICENSE) for full text.

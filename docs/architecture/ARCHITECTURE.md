# Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                         │
│                                                                     │
│   ┌──────────────────┐      ┌──────────────────────────────────┐   │
│   │  Textual TUI      │      │   Typer CLI (cb-analytics)       │   │
│   │  (cb-analytics-   │      │   ┌──────────┐ ┌─────────────┐  │   │
│   │   gui)            │      │   │ query    │ │ admin       │  │   │
│   │  ConnectionScreen │      │   │ config   │ │ links       │  │   │
│   │  MainScreen       │      │   │ security │ │ cluster     │  │   │
│   │  QueryPanel       │      │   └──────────┘ └─────────────┘  │   │
│   │  MonitorPanel     │      └──────────────────────────────────┘   │
│   │  ConfigPanel      │                                             │
│   │  RbacPanel        │                                             │
│   │  LinksPanel       │                                             │
│   │  ClusterPanel     │                                             │
│   └──────────┬────────┘                                            │
└──────────────┼──────────────────────────────────────────────────────┘
               │ uses
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SDK Core Layer                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    AnalyticsClient                           │  │
│  │                                                              │  │
│  │  .cluster    → ClusterAPI          (management port 8091)   │  │
│  │  .analytics  → AnalyticsServiceAPI (analytics port 8095)    │  │
│  │  .admin      → AnalyticsAdminAPI   (analytics port 8095)    │  │
│  │  .config     → AnalyticsConfigAPI  (analytics port 8095)    │  │
│  │  .settings   → AnalyticsSettingsAPI(management port 8091)   │  │
│  │  .links      → AnalyticsLinksAPI   (analytics port 8095)    │  │
│  │  .security   → SecurityAPI         (management port 8091)   │  │
│  │  .server_groups → ServerGroupsAPI  (management port 8091)   │  │
│  └──────────────────────────────┬───────────────────────────────┘  │
│                                 │ delegates to                     │
│  ┌──────────────────────────────▼───────────────────────────────┐  │
│  │                      HttpClient                              │  │
│  │                                                              │  │
│  │  mgmt_client  → httpx.AsyncClient(base=:8091)               │  │
│  │  analytics_client → httpx.AsyncClient(base=:8095)           │  │
│  │                                                              │  │
│  │  Retry: tenacity exponential backoff                         │  │
│  │  Auth:  HTTP Basic (username:password)                       │  │
│  │  Error: maps HTTP status → domain exceptions                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────┐  ┌───────────────────┐                     │
│  │  Pydantic Models   │  │   Exceptions      │                     │
│  │  (request/response │  │  AnalyticsError   │                     │
│  │   validation)      │  │  ├ AuthError      │                     │
│  └────────────────────┘  │  ├ QueryError     │                     │
│                           │  ├ NotFoundError  │                     │
│                           │  ├ ConnectionError│                     │
│                           │  └ ServerError    │                     │
│                           └───────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
               │ HTTP/HTTPS
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Couchbase Enterprise Analytics Cluster                │
│                                                                     │
│   ┌──────────────────────────────┐   ┌──────────────────────────┐  │
│   │  Management Service :8091    │   │  Analytics Service :8095  │  │
│   │  (or :18091 TLS)             │   │  (or :18095 TLS)          │  │
│   │                              │   │                           │  │
│   │  /clusterInit                │   │  /api/v1/request          │  │
│   │  /pools/*                    │   │  /api/v1/active_requests  │  │
│   │  /settings/rbac/*            │   │  /api/v1/completed_...    │  │
│   │  /settings/ldap              │   │  /api/v1/status/service   │  │
│   │  /settings/audit             │   │  /api/v1/status/ingestion │  │
│   │  /settings/analytics         │   │  /api/v1/config/service   │  │
│   │  /controller/*               │   │  /api/v1/config/node      │  │
│   │  /node/controller/*          │   │  /api/v1/link/*           │  │
│   │  /nodes/self/*               │   │  /api/v1/service/restart  │  │
│   └──────────────────────────────┘   │  /api/v1/node/restart     │  │
│                                      └──────────────────────────┘  │
│                      Apache AsterixDB Engine                        │
│                      SQL++ query execution                          │
│                      KV DCP replication (links)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

```
User calls: await client.analytics.execute(request)
     │
     ▼
AnalyticsServiceAPI.execute()
  ├─ Build payload dict from AnalyticsQueryRequest
  ├─ Call HttpClient.analytics_post("/api/v1/request", json=payload)
  │    │
  │    ▼
  │  HttpClient._request()
  │    ├─ AsyncRetrying (max_retries=3, exponential backoff)
  │    │    └─ httpx_client.request(method, path, json=payload)
  │    │         ├─ On ConnectError/TimeoutException → AnalyticsConnectionError (retried)
  │    │         └─ On response → HttpClient._handle_response(response)
  │    │              ├─ 200/201/202 → return parsed body
  │    │              ├─ 401/403     → raise AnalyticsAuthError
  │    │              ├─ 404         → raise AnalyticsNotFoundError
  │    │              ├─ 400/409     → raise AnalyticsRequestError
  │    │              └─ 5xx         → raise AnalyticsServerError (retried)
  │    └─ Return parsed JSON body
  │
  ├─ Validate response → AnalyticsQueryResponse
  └─ If response.errors: raise AnalyticsQueryError(first_error)
       └─ Else: return AnalyticsQueryResponse to caller
```

---

## Retry Strategy

Transient errors are retried automatically using `tenacity`:

```
Retried:  AnalyticsConnectionError (network failure, timeout)
          AnalyticsServerError (5xx responses)

NOT retried:
          AnalyticsAuthError    (401/403 — fix credentials)
          AnalyticsNotFoundError (404 — fix the URL)
          AnalyticsRequestError  (400/409 — fix the request)
          AnalyticsQueryError    (query-level error — fix the SQL++)

Default:  max_retries=3
Backoff:  exponential, 0.5s base, 10s ceiling
          attempt 1 → immediate
          attempt 2 → ~0.5s wait
          attempt 3 → ~1.0s wait
```

---

## Authentication

All requests use HTTP Basic Authentication:

```
Authorization: Basic base64(username:password)
```

The `HttpClient` injects this header via `httpx.AsyncClient(auth=(username, password))`.

For TLS clusters:
- Set `CB_ANALYTICS_TLS=true`
- Ports automatically become 18091 (management) and 18095 (analytics)
- Set `CB_ANALYTICS_VERIFY_SSL=false` for self-signed certificates in development

---

## Port Reference

| Port | TLS Port | Service |
|------|----------|---------|
| 8091 | 18091 | Management (cluster, RBAC, settings) |
| 8092 | 18092 | Views |
| 8093 | 18093 | Query (N1QL — not used by this SDK) |
| 8094 | 18094 | Search |
| **8095** | **18095** | **Analytics (SQL++, admin, config, links)** |
| 8096 | 18096 | Eventing |

This SDK uses **8091** for the management API and **8095** for the Analytics API.

---

## Error Code Mapping

Analytics query errors follow Couchbase's documented error code ranges:

| Code range | Category | Description |
|---|---|---|
| 24000–24299 | Compilation | Syntax errors, unknown identifiers |
| 24300–24399 | Metadata | Dataverse/dataset/link not found |
| 24400–24499 | Parameters | Invalid request parameters |
| 24500–24549 | Not Found | Resource not found |
| 24550–24599 | Already Exists | Duplicate resource creation |
| 25000–25099 | Execution | Runtime query failures |
| 25100–25149 | Timeout | Query timeout exceeded |
| 25150–25199 | Cancelled | Query was cancelled |
| 25300–25399 | Network | Replication/connection errors |
| 20000 | Authentication | Invalid credentials |
| 20001 | Authorization | Insufficient permissions |

---

## Configuration Architecture

```
AnalyticsClientConfig (pydantic-settings)
     │
     ├── Reads from: environment variables (CB_ANALYTICS_* prefix)
     ├── Reads from: .env file (python-dotenv)
     └── Reads from: constructor kwargs (highest priority)

Validation:
  - Port range: 1–65535
  - Computed properties: management_url, analytics_url
  - TLS: switches scheme from http→https and port default from 8091→18091
```

---

## Testing Architecture

```
tests/
├── conftest.py          ← shared fixtures (config, mock client)
├── unit/                ← fast, no network, fully mocked with respx
│   ├── test_cluster_api.py         (31 tests)
│   ├── test_analytics_api.py       (30 tests)
│   ├── test_security_api.py        (28 tests)
│   └── test_server_groups_and_models.py (22 tests)
└── integration/         ← skipped if CB_ANALYTICS_HOST not set
    └── test_integration.py         (24 tests)

Mock strategy:
  respx.mock decorator intercepts httpx requests at the transport level.
  No real HTTP connections are made in unit tests.
  Tests verify:
    - Correct HTTP method and path for each endpoint
    - Request body construction
    - Response model parsing
    - Error code → exception mapping
    - Query error propagation

Coverage target: ≥ 90% on src/cb_analytics/ (excluding gui and cli)
```

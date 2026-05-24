# Configuration

Every setting is environment-driven. Set them via `.env` (loaded by your
process supervisor) or directly in the shell. The single-source-of-truth
example is `.env.example` at the repository root.

## MCP server

| variable | default | description |
|---|---|---|
| `MCP_API_KEY` | (required) | Bearer token Claude must send. Min 32 chars. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `MCP_HOST` | `0.0.0.0` | Bind address. |
| `MCP_PORT` | `8000` | Listen port. |
| `MCP_SERVER_URL` | `http://localhost:8000` | Public URL when behind a TLS proxy. Used in OAuth metadata. |
| `MCP_ISSUER_URL` | same as above | OAuth issuer URL. |

## Couchbase cluster (single-cluster mode)

| variable | default | description |
|---|---|---|
| `CB_ANALYTICS_HOST` | (required) | Host or IP of the cluster. |
| `CB_ANALYTICS_USERNAME` | `Administrator` | Couchbase user. |
| `CB_ANALYTICS_PASSWORD` | (required) | Password (stored as `SecretStr`). |
| `CB_ANALYTICS_CLUSTER_NAME` | `default` | Logical name shown in MCP tools. |
| `CB_ANALYTICS_TLS` | `false` | Use HTTPS. |
| `CB_ANALYTICS_VERIFY_SSL` | `true` | Verify cluster TLS certs. |
| `CB_ANALYTICS_MGMT_PORT` | `8091` | Management REST port. |
| `CB_ANALYTICS_ANALYTICS_PORT` | `8095` | Analytics REST port. |
| `CB_ANALYTICS_TIMEOUT_SECONDS` | `60` | Per-request timeout. |
| `CB_ANALYTICS_MAX_RETRIES` | `3` | Retries on connection error / 5xx. |

## Multi-cluster

To serve more than one cluster from one process, point to a JSON file:

```bash
CB_ANALYTICS_CLUSTERS_FILE=/etc/cb-analytics-mcp/clusters.json
```

The file is a JSON array of cluster objects — see `config/clusters.example.json`.
When this variable is set the single-cluster env vars above are **ignored**.

## Capella (optional)

| variable | default | description |
|---|---|---|
| `CB_CAPELLA_API_KEY_SECRET` | unset | If set, enables the 9 `capella_*` tools. |
| `CB_CAPELLA_BASE_URL` | `https://cloudapi.cloud.couchbase.com` | Capella v4 API root. |

## GUI

| variable | default | description |
|---|---|---|
| `GUI_ENABLED` | `true` | Toggle the bundled admin GUI. |
| `GUI_HOST` | `0.0.0.0` | Bind address. |
| `GUI_PORT` | `8080` | Listen port. |
| `GUI_USERNAME` | `admin` | Login username. |
| `GUI_PASSWORD` | (must be set if GUI on) | Login password. |
| `GUI_SESSION_SECRET` | (must be set) | Secret used to sign session cookies. Min 32 chars. |

## Observability

| variable | default | description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `LOG_FORMAT` | `json` | `json` (production) or `console` (dev). |
| `LOG_FILE` | (stdout only) | Optional file path. Live log tail in the GUI reads from this file. |
| `AUDIT_LOG_ENABLED` | `true` | Disable to skip the audit log entirely. |
| `AUDIT_LOG_FILE` | `./audit.log` | Where audit records are appended. |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP collector URL when tracing is on. |
| `OTEL_SERVICE_NAME` | `cb-analytics-mcp` | Service name for spans. |
| `METRICS_ENABLED` | `true` | Expose Prometheus metrics. |
| `METRICS_PORT` | `9100` | Where the metrics endpoint listens. |

## Limits

Safety limits with defaults tuned for typical single-operator deployments.
Tune them if your traffic shape or dataset size demands it.

| variable | default | description |
|---|---|---|
| `MAX_QUERY_ROWS` | `1000` | Soft cap on `execute_query` / `execute_query_readonly`. Responses include `truncated: true` and `full_row_count` when the cap kicks in. `0` disables the cap entirely. Use `execute_query_paginated` for the full result. |
| `RATE_LIMIT_QUERY_PER_SEC` | `10` | Token-bucket rate for `execute_query*`, `explain_query`, `infer_schema`. Per API key. |
| `RATE_LIMIT_READ_PER_SEC` | `60` | Token-bucket rate for read-only tools (list, get, ping, who_am_i, …). Per API key. |
| `RATE_LIMIT_WRITE_PER_SEC` | `1` | Token-bucket rate for mutating tools (upsert/delete user, links, cluster restarts, capella mutations, …). Per API key. Intentionally conservative — fingers-crossed-no-runaway. |
| `AUDIT_ROTATE_BYTES` | `10485760` (10 MB) | Rotate the audit log when it exceeds this size. `0` falls back to a plain unrotated FileHandler. |
| `AUDIT_ROTATE_KEEP` | `5` | How many rotated generations to keep (`audit.log.1` … `audit.log.N`). |

When a tool call hits a rate limit, the response is:

```json
{
  "ok": false,
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded for category 'write' (limit 1/sec). Retry in 0.83s.",
  "category": "write",
  "rate_per_sec": 1,
  "retry_after_sec": 0.83
}
```

Claude is told about these fields in tool descriptions and will back off
automatically. If you're calling tools directly (e.g. via the `tools call`
CLI), respect `retry_after_sec`.

## Validating

Use `cb-analytics-mcp --check` to validate the active configuration without
starting any servers. It returns 0 on success and prints a redacted summary;
on failure it returns 2 and prints the errors.

```bash
$ cb-analytics-mcp --check
[info] config_valid  config={
  "mcp": {"host": "0.0.0.0", "port": 8000, "api_key_set": true, ...},
  "clusters": [{"name": "prod", "host": "prod.example.com", ...}],
  "gui": {"enabled": true, "host": "0.0.0.0", "port": 8080, ...},
  "observability": {"log_level": "INFO", "audit_log_enabled": true, ...}
}
```

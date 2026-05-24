# Observability

This server emits four overlapping but distinct signals. Each can be turned
off independently; defaults are sensible for a single-instance deployment.

## 1. Structured logs

Every line is one JSON object on stdout (and optionally a file via
`LOG_FILE`). Examples:

```json
{"timestamp": "2026-05-24T03:10:00Z", "level": "info", "event": "server_starting", "config": {...}}
{"timestamp": "2026-05-24T03:10:01Z", "level": "info", "event": "cluster_connected", "name": "prod", "host": "prod.example.com"}
{"timestamp": "2026-05-24T03:10:42Z", "level": "warning", "event": "http_error_response", "method": "GET", "status_code": 404, "body_excerpt": "..."}
```

In development you can switch to a coloured human-readable renderer:

```
LOG_FORMAT=console
```

Every record passes through a redactor before it leaves the process. Keys
matching `password`, `secret`, `token`, `api_key`, `authorization`,
`credentials`, etc. (full list in `observability/redact.py`) are replaced
with `***REDACTED***`. Free-text patterns matching `Bearer <token>` or
`Basic <base64>` are also redacted in any string field.

## 2. Audit log

A separate JSON line per MCP tool invocation, appended to `AUDIT_LOG_FILE`
(default `./audit.log`). One record per call regardless of success or
failure. Sample:

```json
{
  "timestamp": "2026-05-24T03:11:00Z",
  "tool": "execute_query",
  "client_id": "claude-ai",
  "success": true,
  "duration_ms": 42.18,
  "pid": 4321,
  "args": {"statement": "SELECT * FROM Default.Users LIMIT 10", "cluster": "prod"},
  "result_summary": {"result_count": 10}
}
```

The audit log uses the same redactor; even if a caller passes a secret as a
tool argument it never lands on disk in plain form.

The dashboard and `/admin` GUI views read the tail of this file directly.

## 3. Prometheus metrics

Exposed on `METRICS_PORT` (default `9100`) as `/metrics`. Metric names:

| metric | type | labels | description |
|---|---|---|---|
| `cb_analytics_mcp_tool_invocations_total` | Counter | `tool`, `outcome` | Per-tool invocation count. |
| `cb_analytics_mcp_tool_duration_seconds` | Histogram | `tool` | Per-tool duration distribution. |
| `cb_analytics_mcp_http_requests_total` | Counter | `cluster`, `method`, `status` | Underlying HTTP calls to Couchbase. |
| `cb_analytics_mcp_cluster_pings_total` | Counter | `cluster`, `outcome` | Cluster reachability checks. |
| `cb_analytics_mcp_clusters_configured` | Gauge | (none) | Count of clusters in the active pool. |

Example scrape config:

```yaml
scrape_configs:
  - job_name: cb-analytics-mcp
    static_configs:
      - targets: ['cb-mcp:9100']
```

## 4. OpenTelemetry tracing

Opt-in by setting `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT`. The
server then:

- Creates a `TracerProvider` with `service.name=cb-analytics-mcp` (configurable).
- Instruments httpx so every outbound Couchbase call is a span.
- Exports spans via OTLP HTTP to your collector.

```bash
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
make run
```

## Choosing what to enable

| use case | log | audit | metrics | trace |
|---|---|---|---|---|
| Local development | console format | optional | optional | off |
| Single-instance production | json + file | on | on | optional |
| Multi-instance / k8s | json + stdout | on (rotated) | on | recommended |
| Hostile network audit posture | json + file + rotation | **required** | on | on |

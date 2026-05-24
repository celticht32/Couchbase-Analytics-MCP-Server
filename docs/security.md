# Security model

## Threat model

The MCP server sits between an LLM client (Claude) and one or more Couchbase
clusters. It must:

1. Authenticate every MCP request with a bearer token (`MCP_API_KEY`).
2. Authenticate every GUI session with username + password.
3. Hold cluster credentials at rest only as `SecretStr` and never log or
   render them.
4. Cap the blast radius of any tool: errors must never crash the server,
   secrets must never leak into logs.

## Authentication

### MCP

- Every MCP call must include `Authorization: Bearer <MCP_API_KEY>`.
- Comparison uses `hmac.compare_digest` with length-padding so neither the
  length nor content of the expected key leaks via timing.
- Minimum key length is 32 characters; the server refuses to start with a
  shorter key.

### GUI

- Login form posts username + password; both compared with
  `hmac.compare_digest`.
- Session cookies are signed by `GUI_SESSION_SECRET` via
  `starlette.middleware.sessions.SessionMiddleware`.
- Cookie defaults: `SameSite=lax`, `httpOnly` (set by Starlette), 8-hour
  expiry. Set `https_only=True` in code (or behind a reverse proxy enforcing
  TLS) for production.

## Secrets handling

| secret | source | storage | log/display |
|---|---|---|---|
| `MCP_API_KEY` | env / .env | `SecretStr` | redacted everywhere |
| Cluster passwords | env / clusters.json | `SecretStr` | redacted |
| Capella API key | env | `SecretStr` | redacted |
| GUI password | env | `SecretStr` | redacted |
| Link credentials (S3, GCS, Azure) | tool argument | `SecretStr` | redacted in audit log |

`SecretStr.__repr__` returns `***`; never use `print()` on a model that
contains one. `to_api_dict()` methods unwrap to the raw string only at the
HTTP-payload boundary.

## Redaction rules

The redactor in `observability/redact.py` enforces two layers:

1. **Key-based redaction.** A frozen set of key names (`password`, `secret`,
   `api_key`, `bearer`, `authorization`, `client_secret`, …) is checked
   case-insensitively against every dict key, recursively.
2. **Pattern-based redaction.** Free-text patterns catch `Bearer <token>` and
   `Basic <base64>` shapes anywhere in a string.

The redactor runs as a structlog processor, so every log record passes
through it before any handler sees it. It also runs over every tool argument
before the audit log gets it.

## SQL++ injection

`infer_schema` is the only tool that interpolates an identifier into a SQL++
statement (parameterised identifiers aren't supported by Analytics). The
identifier is whitelisted with a strict regex first:

```python
_DATASET_RE = re.compile(rf"^{_SEGMENT}(?:\.{_SEGMENT})*$")
```

Where `_SEGMENT` allows plain identifiers (`[A-Za-z_][A-Za-z0-9_]*`) and
backtick-quoted segments. Anything else (semicolons, comments, quotes)
raises `AnalyticsRequestError` before the SQL is built.

All other tools pass user input via named parameters (`$id`, `$dv`, etc.).

## What Claude can do, what it can't

A connected Claude has every right granted to the cluster user configured
in `CB_ANALYTICS_USERNAME`. **Do not connect Claude with a Full Admin
account in production.** Create a least-privileged user — usually
`analytics_admin` plus the specific buckets / scopes you want exposed — and
configure that user's credentials in `.env`.

The MCP server itself has no notion of "read-only mode"; it relies on
Couchbase RBAC to enforce write protection.

## TLS

Run behind a TLS-terminating reverse proxy (nginx, Caddy, AWS ALB, etc).
Set `MCP_SERVER_URL` and `MCP_ISSUER_URL` to the public HTTPS URL so the
OAuth metadata that FastMCP advertises matches reality.

## Auditing

Every tool invocation produces one audit-log record with timestamp, tool
name, client id, duration, success/failure, and redacted args. To meet
SOC2 / HIPAA-style requirements you should:

- Rotate the audit file (logrotate or container log driver).
- Ship audit lines to an immutable store (S3 with object-lock, etc).
- Disable `AUDIT_LOG_ENABLED=false` in dev only.

## Reporting issues

If you find a security issue please open a private report via the GitHub
repository's security advisories tab, **not** as a public issue.

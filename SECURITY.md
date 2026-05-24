# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | ✅ Current |
| 1.0.x   | ⚠️ Critical fixes only |
| < 1.0   | ❌ Not supported |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Email **cahrendt@github.com** with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Any suggested mitigations

You will receive an acknowledgement within 48 hours and a status update within 7 days.

## Security Considerations

### Credentials
- Passwords and API keys are stored as Pydantic `SecretStr` — they never appear in
  `repr()`, logs, or tracebacks
- Credentials are unwrapped from `SecretStr` only at the HTTP serialization boundary
  inside `to_api_dict()` methods
- Never hardcode passwords — use `CB_ANALYTICS_PASSWORD` environment variable or a
  secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.)

### SQL++ Injection
- The SDK emits a `UserWarning` when it detects statement patterns that suggest
  string interpolation (f-strings, `%s`, `.format()`, bare `{...}`)
- Always use parameterized queries: `AnalyticsQueryRequest(statement="...", args=[val])`
  or `named_args={"name": val}`

### TLS
- Set `CB_ANALYTICS_TLS=true` and use ports 18091/18095 for encrypted connections
- Set `CB_ANALYTICS_VERIFY_SSL=true` (the default) — only disable for development
  with self-signed certificates

### Network
- The circuit breaker limits blast radius when the cluster is degraded; it opens
  after `circuit_fail_max` consecutive failures and resets after `circuit_reset_timeout`
- All requests have an outer `asyncio.timeout` guard in addition to the httpx timeout

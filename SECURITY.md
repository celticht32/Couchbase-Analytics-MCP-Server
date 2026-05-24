# Security policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in the form — include reproduction steps and the affected version.

I'll acknowledge receipt within 7 days and aim to publish a fix or
mitigation within 30 days, depending on severity.

## Supported versions

| version | supported |
|---|---|
| 1.0.x | ✓ |
| < 1.0 | pre-release; no support |

## What is in scope

- Authentication and session handling bugs (MCP token verifier, GUI login).
- Secret leakage through logs, audit records, or error messages.
- Privilege escalation between the GUI user, the MCP API key, and the
  Couchbase service account.
- SQL injection in any tool that interpolates identifiers into a SQL++
  statement (currently only `infer_schema`, which is whitelisted).
- Path traversal in the static-file or template handlers.
- Container escape or hardening regressions in the published Docker image.

## What is out of scope

- Bugs in upstream dependencies (Couchbase, FastAPI, structlog, etc.) —
  report those to the relevant projects.
- Issues that require already-compromised credentials (e.g. "with the
  MCP_API_KEY an attacker can call tools" — yes, that's by design).
- Denial-of-service via legitimate but expensive SQL++ queries — Couchbase
  RBAC and the cluster's own quota controls are the right mitigation.
- Issues in user-supplied Couchbase cluster credentials (rotate them).

## Hardening guidance

The [Security model](docs/security.md) doc describes the threat model in
detail and includes a hardening checklist for production deployments.
Operators should review it before exposing this server to untrusted
networks.

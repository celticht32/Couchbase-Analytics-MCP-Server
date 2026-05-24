---
name: cb-analytics-mcp-setup
description: |
  Use this skill when the user is setting up cb-analytics-mcp from scratch
  - generating secrets, configuring .env, running --check, picking single-
  vs multi-cluster mode, or troubleshooting startup. Trigger when the user
  mentions "install", "configure", "first run", "MCP_API_KEY", "GUI_PASSWORD",
  "clusters.json", or "cb-analytics-mcp --check".
---

# cb-analytics-mcp setup

You're helping the user bring up a fresh cb-analytics-mcp installation.

## Required env vars (the server will refuse to start without these)

- `MCP_API_KEY` — bearer token for Claude. **Min 32 chars.**
  Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- At least one of:
  - Single cluster: `CB_ANALYTICS_HOST` **and** `CB_ANALYTICS_PASSWORD`
  - Multi cluster: `CB_ANALYTICS_CLUSTERS_FILE` pointing at a JSON array
- If GUI is enabled (default): `GUI_SESSION_SECRET` (≥32 chars) and a non-
  default `GUI_PASSWORD`.

## Validation flow

Always recommend `cb-analytics-mcp --check` before `make run`. It returns:

- exit 0 + a `config_valid` log line on success
- exit 2 + a list of human-readable errors on failure

## Single vs multi-cluster decision

- **One Couchbase cluster.** Use env vars only. Simpler.
- **More than one cluster** (prod, stage, dev), or **one cluster but multi-
  tenant access patterns.** Use `CB_ANALYTICS_CLUSTERS_FILE`. The file is a
  JSON array; each entry has `name`, `host`, `username`, `password`, and
  optional `tls`, `mgmt_port`, `analytics_port`, `verify_ssl`,
  `timeout_seconds`, `max_retries`. See `config/clusters.example.json`.

## Common gotchas

- A `MCP_API_KEY` under 32 chars → ValueError at startup. Pad it.
- `GUI_PASSWORD=changeme` is rejected in strict mode (`--check` flags it).
- TLS to Couchbase: set `CB_ANALYTICS_TLS=true` **and** the correct
  TLS-port numbers (`18091`/`18095` are common).
- Capella tools require **both** `CB_CAPELLA_API_KEY_SECRET` and a working
  outbound HTTPS path to `cloudapi.cloud.couchbase.com`.
- The audit log writer creates its parent directory on first record. If
  the path is on a read-only mount, set `AUDIT_LOG_ENABLED=false` or pick
  a writable location.

## What to do after a successful --check

1. `make run` to start both servers.
2. Browse to `http://localhost:8080` to confirm the GUI.
3. From the GUI, run `SELECT 1` in the query editor to confirm cluster
   reachability end-to-end.
4. Point Claude at `http://<host>:8000/mcp` with the bearer token from
   step 1 (see `connecting-claude-ai.md` in the project docs).

# cb-analytics-mcp documentation

A standalone MCP server + admin GUI for Couchbase Enterprise Analytics and
Capella Analytics.

## Sections

1. [Installation](installation.md) — install, dependencies, first run.
2. [Configuration](configuration.md) — every environment variable explained.
3. [Connecting Claude.ai, Desktop, and Code](connecting-claude-ai.md).
4. [GUI walkthrough](gui-guide.md) — login, dashboard, query editor, admin, logs.
5. [Observability](observability.md) — structured logging, audit trail, Prometheus, OpenTelemetry.
6. [Tool reference](tool-reference.md) — all 52 MCP tools with signatures and examples.
7. [Security model](security.md) — authentication, secret handling, RBAC.
8. [Deployment](deployment.md) — Docker, Compose, TLS, hardening.
9. [Architecture](architecture.md) — the internal design.

## What is this?

`cb-analytics-mcp` lets an LLM client (claude.ai, Claude Desktop, Claude Code,
or any MCP-compliant agent) drive Couchbase Analytics via a strict set of 51
tools, with full audit logging and observability. It bundles an admin GUI for
operators who prefer a browser.

```
┌──────────────┐     bearer-token     ┌───────────────────────┐
│  claude.ai   │ ───────────────────▶ │   cb-analytics-mcp    │
│  Claude Code │     HTTPS / MCP      │  ┌─────────────────┐  │
│  …           │                      │  │ 52 tools        │  │
└──────────────┘                      │  └─────────────────┘  │
                                      │  ┌─────────────────┐  │
   admin user ──── HTTPS ───────────▶ │  │ GUI (FastAPI)   │  │
                                      │  └─────────────────┘  │
                                      └─────────┬─────────────┘
                                                │ REST
                                                ▼
                                       ┌────────────────────┐
                                       │ Couchbase cluster  │
                                       │ (Enterprise or     │
                                       │  Capella Analytics)│
                                       └────────────────────┘
```

## License

MIT © 2026 Chris Ahrendt.

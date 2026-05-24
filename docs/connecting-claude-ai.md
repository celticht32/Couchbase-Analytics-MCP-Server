# Connecting Claude

This server speaks the Model Context Protocol (MCP) over **Streamable HTTP**.
The same endpoint works from claude.ai, Claude Desktop, and Claude Code.

## URL & token

```
URL:    http(s)://<your-server>:8000/mcp
Auth:   Bearer <MCP_API_KEY>
```

`MCP_API_KEY` is the token you set in `.env`. Treat it as a secret; it has
the full power of every tool the server exposes.

## claude.ai (web)

1. Open **Settings → Connectors → Add custom connector**.
2. Name: `cb-analytics-mcp` (or whatever you like).
3. URL: `https://your-server.example.com/mcp` (HTTPS required by claude.ai).
4. Auth: paste your `MCP_API_KEY`.
5. Save and toggle the connector on for a new conversation.

You should see the 55 tools listed when you click the connector's name in
the conversation. Ask Claude *"Use cb-analytics-mcp to list the dataverses
in my production cluster"* to confirm.

## Claude Desktop

In `~/.config/Claude/claude_desktop_config.json` (Linux) or the equivalent
on macOS / Windows:

```json
{
  "mcpServers": {
    "cb-analytics-mcp": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY"
      }
    }
  }
}
```

Restart Claude Desktop to pick up the change.

## Claude Code

```bash
claude mcp add cb-analytics --url http://localhost:8000/mcp --token "$MCP_API_KEY"
```

Then from any Claude Code session, ask *"Show me the recent slow queries in
Analytics"* — Claude will discover and call the right tools.

## Verifying the server is up

The server exposes a streamable HTTP MCP endpoint; the simplest sanity check
is to query the GUI (which uses the same process):

```bash
curl http://localhost:8080/login
# → HTML response, status 200
```

And the metrics endpoint:

```bash
curl http://localhost:9100/metrics | head
# → # HELP cb_analytics_mcp_clusters_configured ...
```

## What gets sent over the wire

Claude never sees:

- Cluster passwords (held inside `SecretStr`, not transmitted).
- Capella API keys.
- Session secrets.
- Any value whose key matches the redactor pattern
  (see [Security](security.md)).

Every tool invocation appears in the audit log with redacted args and the
result summary.

## Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `401 Unauthorized` from claude.ai | wrong / missing `MCP_API_KEY` | re-paste the token, check for trailing newlines |
| `Connection refused` | server not listening on the URL claude.ai sees | ensure the URL is reachable from claude.ai's egress |
| Tools listed but every call returns `AnalyticsAuthError` | cluster credentials in `.env` are wrong | run `cb-analytics-mcp --check` and try `ping_cluster` in the GUI |
| `Cluster unreachable` in dashboard | network or firewall | open management + analytics ports from MCP server to cluster |

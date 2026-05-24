# Deployment

This server is one Python process exposing two ports: `8000` (MCP) and
`8080` (GUI). Prometheus metrics live on `9100`.

## Docker

The `Dockerfile` produces a small image (~250 MB) with Python 3.12 slim.

```bash
make docker            # builds cb-analytics-mcp:latest
docker run --rm -p 8000:8000 -p 8080:8080 -p 9100:9100 \
  --env-file .env \
  cb-analytics-mcp:latest
```

## Docker Compose

A full reverse-proxy + MCP + metrics stack:

```bash
docker compose up -d
```

The compose file wires:

- `mcp`: this server, reading `.env` and the optional cluster JSON.
- `nginx`: TLS termination on `:443` proxying to `:8000` and `:8080`.
- (optional) `prometheus`: scrapes `mcp:9100`.

## Health probes

Two unauthenticated endpoints on the GUI port (`:8080` by default):

| endpoint | purpose | semantics |
|---|---|---|
| `/healthz` | liveness | always returns 200 with `{"status": "ok"}` if the process is up. Use for load-balancer health and Kubernetes `livenessProbe`. |
| `/readyz`  | readiness | returns 200 only if at least one configured cluster is reachable; 503 if every cluster's `ping()` fails. Body lists each cluster's state. Use for Kubernetes `readinessProbe` so the pod is removed from rotation when its cluster is unreachable. |

Neither endpoint sets a session cookie or touches the audit log.

## Behind a reverse proxy

When TLS-terminating elsewhere, you usually want:

```bash
MCP_SERVER_URL=https://mcp.example.com
MCP_ISSUER_URL=https://mcp.example.com
```

So the OAuth metadata FastMCP advertises matches the URL claude.ai is
hitting.

In your proxy, forward:

| upstream path | from | comment |
|---|---|---|
| `/mcp`, `/mcp/*` | claude.ai | MCP streamable HTTP endpoint |
| `/`, `/login`, `/query`, `/admin`, `/logs`, `/static`, … | browsers | GUI |
| `/metrics` | Prometheus | usually firewalled to internal network |

An example nginx config is in `nginx/nginx.conf`.

## Kubernetes

A minimal `Deployment` + `Service` looks like:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cb-analytics-mcp
spec:
  replicas: 2   # stateless; safe to scale
  template:
    spec:
      containers:
        - name: mcp
          image: ghcr.io/celticht32/cb-analytics-mcp:1.0.0
          ports:
            - { name: mcp,     containerPort: 8000 }
            - { name: gui,     containerPort: 8080 }
            - { name: metrics, containerPort: 9100 }
          envFrom:
            - secretRef:
                name: cb-analytics-mcp-env
          readinessProbe:
            httpGet: { path: /readyz, port: gui }
            initialDelaySeconds: 2
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /healthz, port: gui }
            initialDelaySeconds: 10
            periodSeconds: 15
```

The audit log is best treated as ephemeral inside the pod and shipped to a
log aggregator via your existing pipeline. If you need an on-disk audit,
mount a volume at `AUDIT_LOG_FILE`'s parent directory.

## Hardening checklist

- [ ] `MCP_API_KEY` is generated cryptographically, ≥48 chars.
- [ ] `GUI_SESSION_SECRET` is a fresh 48-byte URL-safe token.
- [ ] `GUI_PASSWORD` is not `changeme`.
- [ ] Couchbase user has *only* the roles it needs (not Full Admin).
- [ ] TLS terminates upstream; `MCP_SERVER_URL` points to the HTTPS URL.
- [ ] `:9100` (metrics) is not exposed to the public internet.
- [ ] Audit log is rotated and shipped off-host.
- [ ] Container runs as non-root.

## Updates

This project follows semantic versioning. Patch releases (1.0.x) never
change tool signatures; minor releases (1.x.0) may add tools; major
releases may remove or rename them.

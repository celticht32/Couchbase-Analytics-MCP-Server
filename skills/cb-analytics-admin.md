---
name: cb-analytics-admin
description: >
  Operational workflow for monitoring, managing, and troubleshooting
  Couchbase Enterprise Analytics using cb-analytics. Use for health
  checks, cancelling queries, restart decisions, and config tuning.
---

# cb-analytics Admin Skill

## Health check sequence (run in this order)

```python
# 1. Service state
status = await client.admin.get_service_status()
print(f"State: {status.state}")          # ACTIVE / INACTIVE / BOOTSTRAP
print(f"CCRevLag: {status.ccRevLag}")     # revision lag — high = cluster sync delay
print(f"Nodes: {status.authorizedNodes}")

# 2. Ingestion health
ingestion = await client.admin.get_ingestion_status()
for link in ingestion.links:
    print(f"{link.name}: {link.state}")   # CONNECTED / DISCONNECTED

# 3. Active queries
active = await client.admin.get_active_requests()
for req in active:
    print(f"{req.clientContextID}: {req.elapsedTime} — {req.state}")
```

## Cancel a long-running query
```python
await client.admin.cancel_request("ctx-abc-123")
```

## Configuration tuning
```python
from cb_analytics.models import ServiceConfig

# View current config
cfg = await client.config.get_service_config()
print(f"resultTtl: {cfg.resultTtl}")

# Update (only set fields are sent — 0 and False are preserved)
await client.config.update_service_config(ServiceConfig(resultTtl=7200))
```

## Restart decisions
- **Restart node** (`restart_node`): Recovers a single stuck node without affecting others.
- **Restart service** (`restart_service`): Restarts ALL nodes. **Interrupts all running queries.** Confirm first.

```python
# CONFIRM before calling — this cancels all active queries
await client.admin.restart_service()
```

## Analytics replica settings (affects rebalance)
```python
from cb_analytics.models import AnalyticsSettings

settings = await client.settings.get_settings()
print(f"Replicas: {settings.numReplicas}")

# numReplicas=0 is valid — single copy. Always rebalance after changing.
await client.settings.update_settings(AnalyticsSettings(numReplicas=1))
```

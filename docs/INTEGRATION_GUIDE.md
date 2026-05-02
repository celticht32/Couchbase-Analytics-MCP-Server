# Integration Guide

## Prerequisites

- Python 3.11+
- Couchbase Enterprise Analytics 2.0+ (or Couchbase Server 7.x Enterprise with Analytics service)
- RBAC user with appropriate permissions

### Minimum RBAC permissions

| Operation | Required role |
|---|---|
| Execute SQL++ queries | `analytics_reader` or `analytics_select` |
| Manage datasets/links | `analytics_admin` |
| Restart service | `Full Admin` or `Cluster Admin` |
| RBAC management | `Full Admin` or `Security Admin` |
| View all users | `Full Admin` |

---

## Installation

```bash
pip install cb-analytics
```

For development (testing, linting):
```bash
pip install "cb-analytics[dev]"
```

---

## Basic SDK usage

### 1. Context manager (recommended)

```python
import asyncio
from cb_analytics import AnalyticsClient, AnalyticsClientConfig
from cb_analytics.models import AnalyticsQueryRequest

async def main():
    config = AnalyticsClientConfig(
        host="my-cluster.internal",
        username="analytics_user",
        password="SecretPass123!",
    )

    async with AnalyticsClient(config) as client:
        result = await client.analytics.execute(
            AnalyticsQueryRequest(statement="SELECT 1 AS n")
        )
        print(result.results)

asyncio.run(main())
```

### 2. Explicit close

```python
client = AnalyticsClient(config)
try:
    result = await client.analytics.execute(...)
finally:
    await client.close()
```

### 3. Environment variables (12-factor apps)

```bash
export CB_ANALYTICS_HOST=my-cluster
export CB_ANALYTICS_USERNAME=admin
export CB_ANALYTICS_PASSWORD=pass
```

```python
# No explicit config needed — reads from environment
async with AnalyticsClient() as client:
    ...
```

---

## Query patterns

### Simple query

```python
from cb_analytics.models import AnalyticsQueryRequest

result = await client.analytics.execute(
    AnalyticsQueryRequest(statement="SELECT * FROM `Default`.airline LIMIT 10")
)
for row in result.results:
    print(row)
```

### Positional parameters

```python
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT * FROM `Default`.airline WHERE id = $1",
        args=[42],
    )
)
```

### Named parameters

```python
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT * FROM `Default`.airline WHERE callsign = $callsign",
        named_args={"callsign": "UAL"},
    )
)
```

### Request-plus consistency (read your own writes)

```python
from cb_analytics.models import ScanConsistency

result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT COUNT(*) FROM `Default`.orders",
        scan_consistency=ScanConsistency.REQUEST_PLUS,
    )
)
```

### With timeout

```python
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT * FROM big_table",
        timeout="120s",
    )
)
```

### Read-only via GET

```python
# Uses HTTP GET — suitable for queries you want cached/proxied
result = await client.analytics.execute_readonly(
    AnalyticsQueryRequest(statement="SELECT 1 AS n")
)
```

### Error handling

```python
from cb_analytics.exceptions import AnalyticsQueryError, AnalyticsConnectionError

try:
    result = await client.analytics.execute(
        AnalyticsQueryRequest(statement="SELECT * FROM nonexistent_dataset")
    )
except AnalyticsQueryError as e:
    print(f"SQL++ error [{e.code}]: {e}")
    if e.line:
        print(f"  at line {e.line}, column {e.column}")
except AnalyticsConnectionError as e:
    print(f"Connection failed (will be retried automatically): {e}")
```

---

## Admin patterns

### Monitor active queries

```python
active = await client.admin.get_active_requests()
for req in active:
    print(f"[{req.state}] {req.elapsedTime} — {req.statement[:80]}")
```

### Cancel a query

```python
await client.admin.cancel_request("my-client-context-id")
```

### Check ingestion lag

```python
ingestion = await client.admin.get_ingestion_status()
for link in ingestion.links:
    print(link)
```

### Restart service (use with caution)

```python
# Restarts Analytics service on all nodes — interrupts running queries
await client.admin.restart_service()

# Restart only this node
await client.admin.restart_node()
```

---

## Configuration patterns

### View all config

```python
svc_config = await client.config.get_service_config()
print(f"Result TTL: {svc_config.resultTtl}s")
print(f"Memory budget: {svc_config.activeMemoryGlobalBudget} bytes")
```

### Update a parameter

```python
from cb_analytics.models import ServiceConfig

updated = await client.config.update_service_config(
    ServiceConfig(resultTtl=7200)  # only set fields are sent
)
```

### Analytics settings (replica count)

```python
from cb_analytics.models import AnalyticsSettings

settings = await client.settings.get_settings()
print(f"Replicas: {settings.numReplicas}")

# Set 2 replicas (requires cluster rebalance after)
await client.settings.update_settings(AnalyticsSettings(numReplicas=2))
```

---

## Links management

### List all links

```python
links = await client.links.get_all_links()
for link in links:
    print(f"{link.name} ({link.type})")

# Filter by type
s3_links = await client.links.get_all_links(link_type="s3")
```

### Create an S3 link

```python
await client.links.create_link(
    name="myS3Link",
    dataverse="Default",
    config={
        "type": "s3",
        "region": "us-east-1",
        "accessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "secretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    },
)
```

### Create a remote Couchbase link

```python
await client.links.create_link(
    name="remoteCluster",
    dataverse="Default",
    config={
        "type": "couchbase",
        "hostname": "remote-cluster.internal",
        "username": "admin",
        "password": "pass",
        "encryption": "full",
    },
)
```

### Delete a link

```python
await client.links.delete_link("myS3Link")
```

---

## RBAC patterns

### Create a user

```python
from cb_analytics.models import RbacDomain, UserUpsertRequest

await client.security.upsert_user(
    domain=RbacDomain.LOCAL,
    username="alice",
    request=UserUpsertRequest(
        password="SecurePass123!",
        roles="analytics_reader[*]",
        name="Alice Smith",
    ),
)
```

### Create a group

```python
from cb_analytics.models import GroupUpsertRequest

await client.security.upsert_group(
    groupname="analytics-team",
    request=GroupUpsertRequest(
        description="Analytics read-only users",
        roles="analytics_reader[*]",
    ),
)
```

### Check permissions

```python
from cb_analytics.models import PermissionCheckRequest

perms = await client.security.check_permissions(
    PermissionCheckRequest(
        permissions="cluster.analytics!read,cluster.admin!write"
    )
)
print(perms)  # {"cluster.analytics!read": True, "cluster.admin!write": False}
```

### Configure LDAP

```python
from cb_analytics.models import LdapSettings

await client.security.configure_ldap(
    LdapSettings(
        authenticationEnabled=True,
        hosts=["ldap.company.com"],
        port=389,
        bindDN="cn=service,dc=company,dc=com",
        bindPass="ldappass",
        userDNMapping='{"query": "cn=%u,dc=company,dc=com"}',
    )
)
```

---

## Cluster management

### Node initialization (new cluster setup)

```python
from cb_analytics.models import ClusterInitRequest

result = await client.cluster.initialize_cluster(
    ClusterInitRequest(
        username="Administrator",
        password="password",
        services="kv,cbas",
        clusterName="MyCluster",
        memoryQuota=2048,
        cbasMemoryQuota=1024,
        port="SAME",
    )
)
print(result.new_base_uri)
```

### Rebalance after node changes

```python
from cb_analytics.models import RebalanceRequest

# Get current node list first
node_info = await client.cluster.get_node_info()
known = ",".join(
    n.get("otpNode", "") for n in node_info.nodes
)

await client.cluster.rebalance(
    RebalanceRequest(knownNodes=known)
)

# Monitor progress
import asyncio
while True:
    progress = await client.cluster.get_rebalance_progress()
    print(f"Rebalance: {progress.status}")
    if progress.status == "none":
        break
    await asyncio.sleep(5)
```

### Server groups

```python
from cb_analytics.models import ServerGroupCreateRequest

# Create a rack-aware group
group = await client.server_groups.create_group(
    ServerGroupCreateRequest(name="Rack A")
)

# List groups
groups = await client.server_groups.get_groups()
for g in groups.groups:
    print(f"{g.name}: {len(g.nodes)} node(s)")
```

---

## TUI usage

Launch the interactive terminal UI:

```bash
cb-analytics-gui

# Or with pre-set credentials:
CB_ANALYTICS_HOST=my-cluster \
CB_ANALYTICS_USERNAME=admin \
CB_ANALYTICS_PASSWORD=pass \
cb-analytics-gui
```

### Key bindings

| Key | Action |
|-----|--------|
| `F1` | Switch to Query tab |
| `F2` | Switch to Monitor tab |
| `F3` | Switch to Config tab |
| `F4` | Switch to RBAC tab |
| `F5` | Switch to Links tab |
| `F6` | Switch to Cluster tab |
| `Ctrl+R` | Refresh all panels |
| `Ctrl+Q` | Quit |

---

## Common error scenarios

### Connection refused

```
AnalyticsConnectionError: Connection refused
```

- Check `CB_ANALYTICS_HOST` and port numbers
- Verify Couchbase is running: `curl http://localhost:8091/pools`
- Check firewall rules

### Auth failure

```
AnalyticsAuthError: Authentication failed
```

- Verify username/password
- Check RBAC roles include the required permissions
- For Analytics queries: user needs `analytics_reader` or higher

### Query syntax error

```
AnalyticsQueryError: Syntax error near 'BADTOKEN' [24000] at line 1, column 8
```

- Fix the SQL++ statement
- Use `cb-analytics query explain "..."` to check the plan before execution

### TLS issues

```
AnalyticsConnectionError: SSL verification failed
```

- For development with self-signed certs: `CB_ANALYTICS_VERIFY_SSL=false`
- For production: provide the CA certificate path or load it into the trust store

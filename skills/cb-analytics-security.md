---
name: cb-analytics-security
description: >
  RBAC and security guide for cb-analytics. Covers minimum required roles
  for each operation, user/group management, checking permissions, and
  credential security.
---

# cb-analytics Security Skill

## Minimum RBAC roles per operation
| Operation | Minimum role |
|---|---|
| Execute SQL++ queries (SELECT) | `analytics_reader` |
| Execute DDL (CREATE/DROP dataset) | `analytics_admin` |
| Manage links | `analytics_admin` |
| View active requests | `analytics_reader` |
| Cancel any request | `analytics_admin` |
| Restart service | `Full Admin` or `Cluster Admin` |
| View/edit RBAC users | `Full Admin` or `Security Admin` |
| Modify cluster config | `Full Admin` |

## Check permissions before attempting operations
```python
from cb_analytics.models import PermissionCheckRequest

perms = await client.security.check_permissions(
    PermissionCheckRequest(permissions="cluster.analytics!read,cluster.admin!write")
)
# Returns dict[str, bool]
if not perms.get("cluster.analytics!read"):
    print("User lacks analytics read permission")
```

## Create a user with minimum analytics access
```python
from cb_analytics.models import RbacDomain, UserUpsertRequest

await client.security.upsert_user(
    domain=RbacDomain.LOCAL,
    username="analytics_reader",
    request=UserUpsertRequest(
        password="SecurePass123!",   # SecretStr — never logged
        roles="analytics_reader[*]",
        name="Analytics Read-Only",
    ),
)
```

## Create a group and assign users to it
```python
from cb_analytics.models import GroupUpsertRequest

await client.security.upsert_group(
    "analytics-team",
    GroupUpsertRequest(description="Analytics users", roles="analytics_reader[*]"),
)
# Then set the user's groups field when upserting
await client.security.upsert_user(
    RbacDomain.LOCAL, "alice",
    UserUpsertRequest(password="Pass123!", roles="", groups="analytics-team"),
)
```

## Password security
- All `password` fields in models are `SecretStr` — they never appear in repr() or logs
- Call `.get_secret_value()` only when absolutely needed (the SDK does this for you)
- Use environment variables or a secrets manager — never hardcode passwords

## Who am I?
```python
me = await client.cluster.who_am_i()
print(me["id"], me["roles"])
```

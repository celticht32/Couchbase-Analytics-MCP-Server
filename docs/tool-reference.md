# Tool reference

All 52 MCP tools, organised by group. Each tool's signature is given as it
appears to Claude. Most tools accept an optional `cluster` parameter; if you
omit it the default (first-configured) cluster is used.

Every result follows the same shape:

```json
{ "ok": true, "data": ..., "cluster": "prod" }
```

or, on failure:

```json
{ "ok": false, "error": "AnalyticsAuthError", "message": "HTTP 401: ..." }
```

## Meta — 2 tools

### `list_clusters()`

Return the configured cluster names, the default, and whether Capella is
enabled.

### `get_capabilities()`

Return name, version, and the available tool groups.

## Schema — 3 tools

### `list_dataverses(cluster=None)`

List every dataverse in the cluster's Analytics metadata.

### `list_datasets(dataverse=None, cluster=None)`

List datasets, optionally filtered by dataverse.

### `infer_schema(dataset, sample_size=100, cluster=None)`

Sample `sample_size` documents and report observed top-level fields with
presence counts and value types. Dataset names are whitelisted by a strict
regex before interpolation to prevent SQL++ injection.

## Query — 2 tools

### `execute_query(statement, named_args=None, positional_args=None, scan_consistency=None, timeout="120s", cluster=None)`

Run any SQL++ statement, including DDL and DML. `scan_consistency` may be
`not_bounded`, `request_plus`, or `at_plus`.

### `execute_query_readonly(statement, scan_consistency=None, timeout="120s", cluster=None)`

Run a read-only SELECT. The service can apply extra optimisations and the
client adds `readonly=true` to the payload.

## Admin — 7 tools

| tool | summary |
|---|---|
| `get_service_status(cluster=None)` | Analytics service state, replica lag, authorised nodes. |
| `get_ingestion_status(cluster=None)` | Per-link ingestion status with pending operations. |
| `get_active_requests(cluster=None)` | Currently-running queries. |
| `get_completed_requests(client_context_id=None, cluster=None)` | Recently-completed queries (history slice). |
| `cancel_request(client_context_id, cluster=None)` | Cancel an in-flight query. |
| `restart_service(cluster=None)` | Cluster-wide Analytics restart. **Destructive.** |
| `restart_node(cluster=None)` | Restart only the local Analytics node. |

## Config — 4 tools

| tool | summary |
|---|---|
| `get_service_config(cluster=None)` | Service-level config (resultTtl, compilerParallelism, …). |
| `update_service_config(settings, cluster=None)` | Update specific keys. |
| `get_analytics_settings(cluster=None)` | Cluster-wide settings (numReplicas). |
| `update_analytics_settings(num_replicas, cluster=None)` | Change replica count. |

## Links — 5 tools

| tool | summary |
|---|---|
| `list_links(dataverse=None, link_type=None, cluster=None)` | List Analytics data-source links. |
| `get_link(name, cluster=None)` | Get a single link. |
| `create_link(name, dataverse, config, cluster=None)` | Create a link. `config` is a typed dict matching the link kind (S3, Azure, GCS, Couchbase). |
| `update_link(name, config, cluster=None)` | Update an existing link's config. |
| `delete_link(name, cluster=None)` | Delete a link. |

Link credentials in `config` are redacted automatically by the audit logger.

## Libraries (UDF) — 2 tools

| tool | summary |
|---|---|
| `list_libraries(cluster=None)` | List installed UDF libraries with their functions. |
| `delete_library(scope, library_name, cluster=None)` | Delete a library. |

## Security / RBAC — 9 tools

| tool | summary |
|---|---|
| `list_users(domain=None, cluster=None)` | List users (optionally filtered to `local` / `external`). |
| `get_user(domain, username, cluster=None)` | Get a single user. |
| `upsert_user(domain, username, roles, password=None, full_name=None, cluster=None)` | Create or update a user. `roles` is a comma-separated role list. |
| `delete_user(domain, username, cluster=None)` | Delete a user. |
| `list_groups(cluster=None)` | List all groups. |
| `upsert_group(groupname, roles, description=None, cluster=None)` | Create or update a group. |
| `delete_group(groupname, cluster=None)` | Delete a group. |
| `list_roles(cluster=None)` | Enumerate all available roles. |
| `check_permissions(permissions, cluster=None)` | Test the current user against a comma-separated permission list. |

## Cluster — 9 tools

| tool | summary |
|---|---|
| `ping_cluster(cluster=None)` | Liveness check. |
| `get_cluster_info(cluster=None)` | UUID + version. |
| `get_cluster_details(cluster=None)` | Nodes, memory quotas, rebalance status. |
| `get_cluster_tasks(cluster=None)` | In-flight cluster tasks. |
| `get_rebalance_progress(cluster=None)` | Current rebalance progress (or `none`). |
| `get_auto_failover_settings(cluster=None)` | Read auto-failover config. |
| `configure_auto_failover(enabled, timeout=120, max_count=1, cluster=None)` | Update auto-failover config. |
| `get_system_events(since_time=None, cluster=None)` | Recent system events. |
| `who_am_i(cluster=None)` | The authenticated user as seen by the cluster. |

## Capella — 9 tools

These require `CB_CAPELLA_API_KEY_SECRET` to be set; otherwise the tools
return a clear `RuntimeError`.

| tool | summary |
|---|---|
| `capella_list_organizations()` | List orgs visible to the API key. |
| `capella_list_clusters(org_id, project_id)` | List clusters in a project. |
| `capella_get_cluster(org_id, project_id, cluster_id)` | Get cluster details. |
| `capella_create_cluster(org_id, project_id, cluster_spec)` | Create a cluster. |
| `capella_delete_cluster(org_id, project_id, cluster_id)` | Delete a cluster. **Destructive.** |
| `capella_list_backups(org_id, project_id, cluster_id)` | List backups. |
| `capella_create_backup(org_id, project_id, cluster_id)` | Trigger a backup. |
| `capella_restore_backup(org_id, project_id, cluster_id, backup_id, target_cluster_id=None)` | Restore a backup. |
| `capella_list_api_keys(org_id)` | List API keys for an org. |

---
name: cb-analytics-query
description: |
  Use this skill when the user wants to write or improve SQL++ queries against
  Couchbase Analytics through cb-analytics-mcp. Trigger when they mention
  "SQL++", "Analytics query", "execute_query", "scan_consistency", "request_plus",
  or anything about querying datasets, dataverses, joins, aggregations,
  windowing, or N1QL/SQL++ language features in this server's context.
---

# Querying Couchbase Analytics via cb-analytics-mcp

You have two SQL++ tools available:

- `execute_query(statement, named_args, positional_args, scan_consistency, timeout, cluster)`
- `execute_query_readonly(statement, scan_consistency, timeout, cluster)`

## When to use which

- **`execute_query_readonly`** for any `SELECT`. The Analytics service can
  optimise read-only requests more aggressively and the response payload is
  the same.
- **`execute_query`** for DDL (CREATE DATAVERSE, CREATE DATASET, …),
  parameterised SELECTs with values, and anything that might modify state.

## Parameterisation rules

Never interpolate user-controlled values into the statement string. Use
`named_args`:

```python
execute_query(
    statement="SELECT * FROM Default.Orders o WHERE o.customer_id = $cust",
    named_args={"cust": "C-1234"},
)
```

Identifiers (dataset names, field names) **can't** be parameterised by SQL++.
If you must inject one, validate it first (the server already does this for
`infer_schema`).

## Scan consistency

- `not_bounded` (default) — fastest, may see stale results.
- `request_plus` — wait for ingest to catch up to this point in time. Use
  when correctness matters more than latency.
- `at_plus` — wait for a specific mutation token; rarely needed outside SDK
  code.

## Result shape

The tool returns `{ok: true, data: {results: [...], metrics: {...}, warnings: [...], request_id, status}, cluster}`. Important fields:

- `data.metrics.executionTime`: time spent executing the plan
- `data.metrics.elapsedTime`: total request time (including I/O)
- `data.metrics.resultCount`: row count
- `data.warnings`: non-fatal issues — surface these to the user

## Common patterns

### Counting documents

```sql
SELECT VALUE COUNT(*) FROM Default.Users
```

### Schema discovery

Prefer the `infer_schema` tool over `SELECT VALUE OBJECT_NAMES(d) FROM x d`;
it returns a typed summary including presence rates.

### Working with multiple clusters

Always pass `cluster="..."` if there's any ambiguity. Use `list_clusters`
first if you don't know what's configured.

### Diagnosing slow queries

1. `get_active_requests` — see what's running now.
2. `get_completed_requests` — recent history with timings.
3. `EXPLAIN <stmt>` via `execute_query_readonly` returns the plan.

## What to avoid

- Don't run `SELECT *` against multi-million-row datasets without `LIMIT`.
- Don't use `request_plus` on hot-path queries unless the freshness is
  actually needed.
- Don't drop or replace datasets without checking `get_active_requests`
  first — in-flight queries against the target will fail.

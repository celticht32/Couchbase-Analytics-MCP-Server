---
name: cb-analytics-query
description: >
  Guide for writing and executing SQL++ queries against Couchbase Enterprise
  Analytics and Capella Analytics using cb-analytics. Use when writing SQL++
  statements, choosing scan consistency, using parameters, or understanding
  query response shapes.
---

# cb-analytics Query Skill

## Always use the analytics API group

```python
from cb_analytics import AnalyticsClient, AnalyticsClientConfig
from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency

async with AnalyticsClient(config) as client:
    result = await client.analytics.execute(
        AnalyticsQueryRequest(statement="SELECT 1 AS ping")
    )
    print(result.results)          # list of dicts
    print(result.metrics.elapsedTime)
```

## Naming convention
- Dataverses and datasets are backtick-quoted: `` `Default`.airline ``
- Scope path: `` `bucket-name`.`scope-name`.`collection` `` (3-part)
- Default dataverse is always named `Default`

## ALWAYS use parameterized queries — never string interpolation
```python
# WRONG — injection risk
stmt = f"SELECT * FROM airline WHERE id = {user_id}"

# CORRECT — positional
AnalyticsQueryRequest(statement="SELECT * FROM airline WHERE id = $1", args=[user_id])

# CORRECT — named
AnalyticsQueryRequest(
    statement="SELECT * FROM airline WHERE callsign = $callsign",
    named_args={"callsign": "UAL"},
)
```

## Scan consistency options
| Value | When to use |
|---|---|
| `not_bounded` | Default. May miss very recent writes. Fastest. |
| `request_plus` | Wait for all mutations up to this request time. Use for read-your-own-writes. |
| `at_plus` | Wait for specific mutation tokens (advanced). |

## Schema discovery workflow (do this BEFORE writing queries)
```python
# 1. Find dataverses
result = await client.analytics.execute(
    AnalyticsQueryRequest(statement="SELECT dv.DataverseName FROM Metadata.`Dataverse` AS dv")
)
# 2. Find datasets in a dataverse
result = await client.analytics.execute(
    AnalyticsQueryRequest(
        statement="SELECT ds.DatasetName, ds.DataverseName FROM Metadata.`Dataset` AS ds WHERE ds.DataverseName = $dv",
        named_args={"dv": "Default"}
    )
)
# 3. Infer schema of a dataset
result = await client.analytics.execute(
    AnalyticsQueryRequest(statement='SELECT RAW OBJECT_NAMES(d) FROM `Default`.airline d LIMIT 1')
)
```

## Response shape
```python
result.requestID        # str
result.status           # "success" | "fatal" | "running"
result.results          # list[Any]  — rows
result.metrics.resultCount     # int
result.metrics.elapsedTime     # str  e.g. "142ms"
result.metrics.executionTime   # str
result.metrics.resultSize      # int bytes
result.warnings         # list[AnalyticsWarning]
result.errors           # list[AnalyticsError] — non-empty means AnalyticsQueryError was raised
```

## Error codes (common)
| Code | Meaning |
|---|---|
| 24000 | Syntax error — check SQL++ spelling |
| 24006 | Dataset not found — check dataverse.dataset name |
| 24025 | Dataverse not found |
| 25000 | Runtime execution error |
| 25100 | Query timeout — increase timeout= parameter |

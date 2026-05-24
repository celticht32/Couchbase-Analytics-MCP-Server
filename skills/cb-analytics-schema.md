---
name: cb-analytics-schema
description: >
  Workflow for discovering what data exists in Enterprise Analytics before
  writing queries. Use BEFORE any SELECT statement to avoid hallucinating
  dataset or field names.
---

# cb-analytics Schema Discovery Skill

## MANDATORY: Discover before you query

**Never assume dataset names exist. Always discover first.**

## Step-by-step workflow

### Step 1: List dataverses
```python
result = await client.analytics.execute(AnalyticsQueryRequest(
    statement="SELECT dv.DataverseName FROM Metadata.`Dataverse` AS dv ORDER BY dv.DataverseName"
))
dataverses = [r["DataverseName"] for r in result.results]
```

### Step 2: List datasets in chosen dataverse
```python
result = await client.analytics.execute(AnalyticsQueryRequest(
    statement="""
        SELECT ds.DatasetName, ds.DataverseName, ds.BucketName
        FROM Metadata.`Dataset` AS ds
        WHERE ds.DataverseName = $dv
    """,
    named_args={"dv": "Default"}
))
```

### Step 3: Sample one document to discover field names
```python
result = await client.analytics.execute(AnalyticsQueryRequest(
    statement="SELECT d FROM `Default`.airline d LIMIT 1"
))
if result.results:
    print(result.results[0].keys())
```

### Step 4: Infer type information
```python
result = await client.analytics.execute(AnalyticsQueryRequest(
    statement="SELECT RAW TYPEOF(d.field_name) FROM `Default`.airline d LIMIT 100"
))
```

## Links and ingestion freshness
```python
# Check which links are connected and data is flowing
ingestion = await client.admin.get_ingestion_status()
for link in ingestion.links:
    print(f"{link.name}: {link.state} — {len(link.datasetStates)} datasets")
```

## Do not hallucinate — verify first
If unsure whether a field exists, use:
```python
result = await client.analytics.execute(AnalyticsQueryRequest(
    statement="SELECT d.* FROM `Default`.airline d WHERE IS_KNOWN(d.suspected_field) LIMIT 5"
))
```

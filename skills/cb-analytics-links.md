---
name: cb-analytics-links
description: >
  Guide for creating and managing Analytics data source links in
  cb-analytics. Covers Couchbase DCP, S3, Azure Blob, and GCS link types,
  credential handling, and connection lifecycle.
---

# cb-analytics Links Skill

## Link types and when to use them
| Type | Source | Auth |
|---|---|---|
| `couchbase` | Local or remote Couchbase cluster (KV DCP stream) | username/password |
| `s3` | AWS S3 bucket | accessKeyId + secretAccessKey (+ optional sessionToken) |
| `azureblob` | Azure Blob Storage | accountKey OR sharedAccessSignature |
| `gcs` | Google Cloud Storage | jsonCredentials service account |

## Create a typed link (recommended — credentials use SecretStr)
```python
from cb_analytics.models import S3LinkConfig, CouchbaseLinkConfig, EncryptionLevel

# S3 link
s3_config = S3LinkConfig(
    region="us-east-1",
    accessKeyId="AKIAIOSFODNN7EXAMPLE",
    secretAccessKey="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)
await client.links.create_link("myS3Link", "Default", s3_config)

# Remote Couchbase link
cb_config = CouchbaseLinkConfig(
    hostname="remote-cluster.internal",
    username="admin",
    password="pass",
    encryption=EncryptionLevel.FULL,
)
await client.links.create_link("remoteCluster", "Default", cb_config)
```

## List and inspect links
```python
# All links
links = await client.links.get_all_links()

# Filter by type
s3_links = await client.links.get_all_links(link_type="s3")

# Filter by dataverse
dv_links = await client.links.get_all_links(dataverse="MyDataverse")
```

## Important: link must be DISCONNECTED before deletion
If a link is still connected to active datasets, `delete_link()` will raise
`AnalyticsRequestError`. Disconnect the link first via SQL++:
```python
await client.analytics.execute(AnalyticsQueryRequest(
    statement="DISCONNECT LINK Default.myS3Link"
))
await client.links.delete_link("myS3Link")
```

## Credentials are never logged
All link config models use `SecretStr` internally. Call `to_api_dict()` only
at the serialization boundary. Never pass raw credential strings to log statements.

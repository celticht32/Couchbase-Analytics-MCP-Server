# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Schema introspection tools."""

from __future__ import annotations

import re
from typing import Any

from cb_analytics_mcp.couchbase.models import AnalyticsQueryRequest
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok

# Plain identifier: letters/digits/underscore, optionally dot-separated.
# Backtick-quoted segments are allowed if they don't themselves contain backticks.
_PLAIN_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_BACKTICK_IDENT = r"`[^`]+`"
_SEGMENT = rf"(?:{_PLAIN_IDENT}|{_BACKTICK_IDENT})"
_DATASET_RE = re.compile(rf"^{_SEGMENT}(?:\.{_SEGMENT})*$")


def _is_safe_identifier(name: str) -> bool:
    """Whitelist test for dataset/dataverse identifiers."""
    if not name or len(name) > 256:
        return False
    return bool(_DATASET_RE.fullmatch(name))


async def list_dataverses_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    req = AnalyticsQueryRequest(
        statement="SELECT VALUE m.DataverseName FROM Metadata.`Dataverse` m",
        readonly=True,
    )
    result = await client.analytics.execute(req)
    return fmt_ok(result.results, cluster=name)


async def list_datasets_impl(
    pool: ClientPool,
    dataverse: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    if dataverse:
        statement = (
            "SELECT VALUE {{'name': d.DatasetName, 'dataverse': d.DataverseName}} "
            "FROM Metadata.`Dataset` d "
            "WHERE d.DataverseName = $dv"
        )
        req = AnalyticsQueryRequest(statement=statement, named_args={"dv": dataverse}, readonly=True)
    else:
        statement = (
            "SELECT VALUE {'name': d.DatasetName, 'dataverse': d.DataverseName} FROM Metadata.`Dataset` d"
        )
        req = AnalyticsQueryRequest(statement=statement, readonly=True)
    result = await client.analytics.execute(req)
    return fmt_ok(result.results, cluster=name)


async def infer_schema_impl(
    pool: ClientPool,
    dataset: str,
    sample_size: int = 100,
    cluster: str | None = None,
) -> dict[str, Any]:
    """Use SQL++ to sample a dataset and report observed top-level fields and types."""
    name, client = pool.resolve(cluster)

    # SQL++ identifiers can't be parameterised — the dataset name has to be
    # interpolated into the FROM clause. Validate strictly first.
    if not _is_safe_identifier(dataset):
        from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError

        raise AnalyticsRequestError(
            f"Invalid dataset name: {dataset!r}. Allowed: identifiers, dot-paths, and backtick-quoted names."
        )

    # Best-effort: read up to sample_size docs, summarise field presence and value types
    # nosec B608 - dataset name is whitelisted via _is_safe_identifier above;
    # SQL++ does not permit parameterised identifiers.
    statement = f"SELECT VALUE d FROM {dataset} d LIMIT $n"  # noqa: S608  # nosec B608
    req = AnalyticsQueryRequest(statement=statement, named_args={"n": int(sample_size)}, readonly=True)
    result = await client.analytics.execute(req)
    rows = result.results or []

    fields: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            entry = fields.setdefault(
                key,
                {"present_count": 0, "types": set()},
            )
            entry["present_count"] += 1
            entry["types"].add(type(value).__name__)

    summarised = {
        key: {
            "present_count": entry["present_count"],
            "presence_pct": round(100.0 * entry["present_count"] / max(len(rows), 1), 1),
            "types": sorted(entry["types"]),
        }
        for key, entry in sorted(fields.items())
    }
    return fmt_ok(
        {
            "dataset": dataset,
            "rows_sampled": len(rows),
            "fields": summarised,
        },
        cluster=name,
    )


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def list_dataverses(cluster: str | None = None) -> dict[str, Any]:
        """List all dataverses on the specified cluster (or default)."""
        return await call_tool_observed(
            "list_dataverses",
            list_dataverses_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def list_datasets(dataverse: str | None = None, cluster: str | None = None) -> dict[str, Any]:
        """List datasets, optionally filtered by dataverse."""
        return await call_tool_observed(
            "list_datasets",
            list_datasets_impl,
            pool,
            dataverse,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"dataverse": dataverse, "cluster": cluster},
        )

    @mcp.tool()
    async def infer_schema(
        dataset: str, sample_size: int = 100, cluster: str | None = None
    ) -> dict[str, Any]:
        """Sample a dataset and infer the observed top-level field schema."""
        return await call_tool_observed(
            "infer_schema",
            infer_schema_impl,
            pool,
            dataset,
            sample_size,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"dataset": dataset, "sample_size": sample_size, "cluster": cluster},
        )

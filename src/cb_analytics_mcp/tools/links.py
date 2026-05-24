# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Analytics link management tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def list_links_impl(
    pool: ClientPool,
    dataverse: str | None = None,
    link_type: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    links = await client.links.get_all_links(dataverse=dataverse, link_type=link_type)
    return fmt_ok([link.model_dump() for link in links], cluster=name)


async def get_link_impl(pool: ClientPool, name: str, cluster: str | None = None) -> dict[str, Any]:
    cluster_name, client = pool.resolve(cluster)
    link = await client.links.get_link(name)
    return fmt_ok(link.model_dump(), cluster=cluster_name)


async def create_link_impl(
    pool: ClientPool,
    name: str,
    dataverse: str,
    config: dict[str, Any],
    cluster: str | None = None,
) -> dict[str, Any]:
    cluster_name, client = pool.resolve(cluster)
    await client.links.create_link(name, dataverse, config)
    return fmt_ok({"created": name, "dataverse": dataverse}, cluster=cluster_name)


async def update_link_impl(
    pool: ClientPool,
    name: str,
    config: dict[str, Any],
    cluster: str | None = None,
) -> dict[str, Any]:
    cluster_name, client = pool.resolve(cluster)
    await client.links.update_link(name, config)
    return fmt_ok({"updated": name}, cluster=cluster_name)


async def delete_link_impl(pool: ClientPool, name: str, cluster: str | None = None) -> dict[str, Any]:
    cluster_name, client = pool.resolve(cluster)
    await client.links.delete_link(name)
    return fmt_ok({"deleted": name}, cluster=cluster_name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def list_links(
        dataverse: str | None = None,
        link_type: str | None = None,
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """List Analytics data-source links, optionally filtered by dataverse or type."""
        return await call_tool_observed(
            "list_links",
            list_links_impl,
            pool,
            dataverse,
            link_type,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"dataverse": dataverse, "link_type": link_type, "cluster": cluster},
        )

    @mcp.tool()
    async def get_link(name: str, cluster: str | None = None) -> dict[str, Any]:
        """Get details for a specific Analytics link."""
        return await call_tool_observed(
            "get_link",
            get_link_impl,
            pool,
            name,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"name": name, "cluster": cluster},
        )

    @mcp.tool()
    async def create_link(
        name: str,
        dataverse: str,
        config: dict[str, Any],
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Create an Analytics link. `config` should match the link type
        (S3, Azure Blob, GCS, or Couchbase).
        """
        return await call_tool_observed(
            "create_link",
            create_link_impl,
            pool,
            name,
            dataverse,
            config,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"name": name, "dataverse": dataverse, "cluster": cluster},
            # NB: config contains secrets — redacted automatically by audit
        )

    @mcp.tool()
    async def update_link(
        name: str,
        config: dict[str, Any],
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Analytics link's configuration."""
        return await call_tool_observed(
            "update_link",
            update_link_impl,
            pool,
            name,
            config,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"name": name, "cluster": cluster},
        )

    @mcp.tool()
    async def delete_link(name: str, cluster: str | None = None) -> dict[str, Any]:
        """Delete an Analytics link."""
        return await call_tool_observed(
            "delete_link",
            delete_link_impl,
            pool,
            name,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"name": name, "cluster": cluster},
        )

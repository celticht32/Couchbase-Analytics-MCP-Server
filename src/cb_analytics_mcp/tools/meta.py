# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Meta tools — server-level info that doesn't touch a cluster."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def list_clusters_impl(pool: ClientPool) -> dict[str, Any]:
    """Return the configured cluster names and their reachability info."""
    return fmt_ok(
        {
            "clusters": pool.cluster_names,
            "default": pool.default_name() if not pool.is_empty else None,
            "count": len(pool.cluster_names),
            "capella_configured": pool.has_capella,
        }
    )


async def get_capabilities_impl(pool: ClientPool) -> dict[str, Any]:
    """Return what this server can do."""
    return fmt_ok(
        {
            "name": "cb-analytics-mcp",
            "version": __import__("cb_analytics_mcp").__version__,
            "multi_cluster": len(pool.cluster_names) > 1,
            "capella_enabled": pool.has_capella,
            "tool_groups": [
                "meta",
                "schema",
                "query",
                "admin",
                "config",
                "links",
                "libraries",
                "security",
                "cluster",
                "capella",
            ],
        }
    )


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def list_clusters() -> dict[str, Any]:
        """List the configured Couchbase clusters served by this MCP server."""
        return await call_tool_observed(
            "list_clusters",
            list_clusters_impl,
            pool,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={},
        )

    @mcp.tool()
    async def get_capabilities() -> dict[str, Any]:
        """Return information about this MCP server's capabilities and version."""
        return await call_tool_observed(
            "get_capabilities",
            get_capabilities_impl,
            pool,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={},
        )

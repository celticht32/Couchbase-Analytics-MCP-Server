# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""UDF library tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def list_libraries_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    libs = await client.libraries.list_libraries()
    return fmt_ok([lib.model_dump() for lib in libs], cluster=name)


async def delete_library_impl(
    pool: ClientPool,
    scope: str,
    library_name: str,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.libraries.delete_library(scope, library_name)
    return fmt_ok({"deleted": library_name, "scope": scope}, cluster=name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def list_libraries(cluster: str | None = None) -> dict[str, Any]:
        """List installed UDF libraries on the Analytics service."""
        return await call_tool_observed(
            "list_libraries",
            list_libraries_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def delete_library(scope: str, library_name: str, cluster: str | None = None) -> dict[str, Any]:
        """Delete a UDF library from a scope."""
        return await call_tool_observed(
            "delete_library",
            delete_library_impl,
            pool,
            scope,
            library_name,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"scope": scope, "library_name": library_name, "cluster": cluster},
        )

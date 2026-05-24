# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Analytics service admin tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def get_service_status_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    status = await client.admin.get_service_status()
    return fmt_ok(status.model_dump(), cluster=name)


async def get_ingestion_status_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    status = await client.admin.get_ingestion_status()
    return fmt_ok(status.model_dump(), cluster=name)


async def get_active_requests_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    items = await client.admin.get_active_requests()
    return fmt_ok([r.model_dump() for r in items], cluster=name)


async def get_completed_requests_impl(
    pool: ClientPool,
    client_context_id: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    items = await client.admin.get_completed_requests(client_context_id)
    return fmt_ok([r.model_dump() for r in items], cluster=name)


async def cancel_request_impl(
    pool: ClientPool, client_context_id: str, cluster: str | None = None
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.admin.cancel_request(client_context_id)
    return fmt_ok({"cancelled": client_context_id}, cluster=name)


async def restart_service_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.admin.restart_service()
    return fmt_ok({"restarted": "service"}, cluster=name)


async def restart_node_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.admin.restart_node()
    return fmt_ok({"restarted": "node"}, cluster=name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def get_service_status(cluster: str | None = None) -> dict[str, Any]:
        """Return the Analytics service status (state, authorized nodes, replication lag)."""
        return await call_tool_observed(
            "get_service_status",
            get_service_status_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_ingestion_status(cluster: str | None = None) -> dict[str, Any]:
        """Return the ingestion status across all configured links and datasets."""
        return await call_tool_observed(
            "get_ingestion_status",
            get_ingestion_status_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_active_requests(cluster: str | None = None) -> dict[str, Any]:
        """List currently running SQL++ requests."""
        return await call_tool_observed(
            "get_active_requests",
            get_active_requests_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_completed_requests(
        client_context_id: str | None = None, cluster: str | None = None
    ) -> dict[str, Any]:
        """List recently completed SQL++ requests."""
        return await call_tool_observed(
            "get_completed_requests",
            get_completed_requests_impl,
            pool,
            client_context_id,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"client_context_id": client_context_id, "cluster": cluster},
        )

    @mcp.tool()
    async def cancel_request(client_context_id: str, cluster: str | None = None) -> dict[str, Any]:
        """Cancel an in-flight Analytics request by its client context ID."""
        return await call_tool_observed(
            "cancel_request",
            cancel_request_impl,
            pool,
            client_context_id,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"client_context_id": client_context_id, "cluster": cluster},
        )

    @mcp.tool()
    async def restart_service(cluster: str | None = None) -> dict[str, Any]:
        """Restart the Analytics service cluster-wide. Destructive — runs no queries during restart."""
        return await call_tool_observed(
            "restart_service",
            restart_service_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def restart_node(cluster: str | None = None) -> dict[str, Any]:
        """Restart only the local Analytics node."""
        return await call_tool_observed(
            "restart_node",
            restart_node_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

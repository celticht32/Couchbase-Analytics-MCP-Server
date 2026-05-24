# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Cluster-level tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.couchbase.models import AutoFailoverSettings
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def ping_cluster_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    ok = await client.ping()
    return fmt_ok({"reachable": ok}, cluster=name)


async def get_cluster_info_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    info = await client.cluster.get_cluster_info()
    return fmt_ok(info.model_dump(), cluster=name)


async def get_cluster_details_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    details = await client.cluster.get_cluster_details()
    return fmt_ok(details.model_dump(), cluster=name)


async def get_cluster_tasks_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    tasks = await client.cluster.get_cluster_tasks()
    return fmt_ok([t.model_dump() for t in tasks], cluster=name)


async def get_rebalance_progress_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    p = await client.cluster.get_rebalance_progress()
    return fmt_ok(p.model_dump(), cluster=name)


async def get_auto_failover_settings_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    s = await client.cluster.get_auto_failover_settings()
    return fmt_ok(s.model_dump(), cluster=name)


async def configure_auto_failover_impl(
    pool: ClientPool,
    enabled: bool,
    timeout: int = 120,
    max_count: int = 1,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    s = AutoFailoverSettings(enabled=enabled, timeout=timeout, maxCount=max_count)
    await client.cluster.configure_auto_failover(s)
    return fmt_ok(s.model_dump(), cluster=name)


async def get_system_events_impl(
    pool: ClientPool,
    since_time: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    events = await client.cluster.get_system_events(since_time)
    return fmt_ok([e.model_dump() for e in events], cluster=name)


async def who_am_i_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    me = await client.cluster.who_am_i()
    return fmt_ok(me, cluster=name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def ping_cluster(cluster: str | None = None) -> dict[str, Any]:
        """Verify the cluster is reachable."""
        return await call_tool_observed(
            "ping_cluster",
            ping_cluster_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_cluster_info(cluster: str | None = None) -> dict[str, Any]:
        """Return basic cluster info (uuid, implementation version)."""
        return await call_tool_observed(
            "get_cluster_info",
            get_cluster_info_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_cluster_details(cluster: str | None = None) -> dict[str, Any]:
        """Return detailed cluster info (nodes, memory quotas, rebalance status)."""
        return await call_tool_observed(
            "get_cluster_details",
            get_cluster_details_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_cluster_tasks(cluster: str | None = None) -> dict[str, Any]:
        """List in-flight cluster tasks (rebalances, compactions, etc)."""
        return await call_tool_observed(
            "get_cluster_tasks",
            get_cluster_tasks_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_rebalance_progress(cluster: str | None = None) -> dict[str, Any]:
        """Return the current rebalance progress, if any."""
        return await call_tool_observed(
            "get_rebalance_progress",
            get_rebalance_progress_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def get_auto_failover_settings(cluster: str | None = None) -> dict[str, Any]:
        """Return the current auto-failover settings."""
        return await call_tool_observed(
            "get_auto_failover_settings",
            get_auto_failover_settings_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def configure_auto_failover(
        enabled: bool,
        timeout: int = 120,
        max_count: int = 1,
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Configure auto-failover (enabled, timeout, max_count)."""
        return await call_tool_observed(
            "configure_auto_failover",
            configure_auto_failover_impl,
            pool,
            enabled,
            timeout,
            max_count,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "enabled": enabled,
                "timeout": timeout,
                "max_count": max_count,
                "cluster": cluster,
            },
        )

    @mcp.tool()
    async def get_system_events(since_time: str | None = None, cluster: str | None = None) -> dict[str, Any]:
        """List recent system events, optionally since a given ISO timestamp."""
        return await call_tool_observed(
            "get_system_events",
            get_system_events_impl,
            pool,
            since_time,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"since_time": since_time, "cluster": cluster},
        )

    @mcp.tool()
    async def who_am_i(cluster: str | None = None) -> dict[str, Any]:
        """Return the authenticated user info as seen by the cluster."""
        return await call_tool_observed(
            "who_am_i",
            who_am_i_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

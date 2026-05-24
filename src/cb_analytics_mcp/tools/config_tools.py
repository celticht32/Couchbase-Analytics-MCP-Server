# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Analytics config & settings tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.couchbase.models import AnalyticsSettings, ServiceConfig
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def get_service_config_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    cfg = await client.config.get_service_config()
    return fmt_ok(cfg.model_dump(exclude_none=True), cluster=name)


async def update_service_config_impl(
    pool: ClientPool,
    settings: dict[str, Any],
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    cfg = ServiceConfig(**settings)
    updated = await client.config.update_service_config(cfg)
    return fmt_ok(updated.model_dump(exclude_none=True), cluster=name)


async def get_analytics_settings_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    s = await client.settings.get_settings()
    return fmt_ok(s.model_dump(), cluster=name)


async def update_analytics_settings_impl(
    pool: ClientPool,
    num_replicas: int,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    s = AnalyticsSettings(numReplicas=int(num_replicas))
    updated = await client.settings.update_settings(s)
    return fmt_ok(updated.model_dump(), cluster=name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def get_service_config(cluster: str | None = None) -> dict[str, Any]:
        """Return the Analytics service-level configuration."""
        return await call_tool_observed(
            "get_service_config",
            get_service_config_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def update_service_config(settings: dict[str, Any], cluster: str | None = None) -> dict[str, Any]:
        """Update Analytics service-level configuration (e.g. resultTtl, compilerParallelism)."""
        return await call_tool_observed(
            "update_service_config",
            update_service_config_impl,
            pool,
            settings,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"settings": settings, "cluster": cluster},
        )

    @mcp.tool()
    async def get_analytics_settings(cluster: str | None = None) -> dict[str, Any]:
        """Return cluster-wide Analytics settings (e.g. replica count)."""
        return await call_tool_observed(
            "get_analytics_settings",
            get_analytics_settings_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def update_analytics_settings(num_replicas: int, cluster: str | None = None) -> dict[str, Any]:
        """Update cluster-wide Analytics settings (e.g. numReplicas)."""
        return await call_tool_observed(
            "update_analytics_settings",
            update_analytics_settings_impl,
            pool,
            num_replicas,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"num_replicas": num_replicas, "cluster": cluster},
        )

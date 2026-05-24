# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Capella Cloud Management tools."""

from __future__ import annotations

from typing import Any

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


async def capella_list_organizations_impl(pool: ClientPool) -> dict[str, Any]:
    orgs = await pool.capella.list_organizations()
    return fmt_ok(orgs)


async def capella_list_clusters_impl(pool: ClientPool, org_id: str, project_id: str) -> dict[str, Any]:
    clusters = await pool.capella.list_clusters(org_id, project_id)
    return fmt_ok(clusters)


async def capella_get_cluster_impl(
    pool: ClientPool, org_id: str, project_id: str, cluster_id: str
) -> dict[str, Any]:
    cluster = await pool.capella.get_cluster(org_id, project_id, cluster_id)
    return fmt_ok(cluster)


async def capella_create_cluster_impl(
    pool: ClientPool, org_id: str, project_id: str, cluster_spec: dict[str, Any]
) -> dict[str, Any]:
    result = await pool.capella.create_cluster(org_id, project_id, cluster_spec)
    return fmt_ok(result)


async def capella_delete_cluster_impl(
    pool: ClientPool, org_id: str, project_id: str, cluster_id: str
) -> dict[str, Any]:
    await pool.capella.delete_cluster(org_id, project_id, cluster_id)
    return fmt_ok({"deleted": cluster_id})


async def capella_list_backups_impl(
    pool: ClientPool, org_id: str, project_id: str, cluster_id: str
) -> dict[str, Any]:
    backups = await pool.capella.list_backups(org_id, project_id, cluster_id)
    return fmt_ok(backups)


async def capella_create_backup_impl(
    pool: ClientPool, org_id: str, project_id: str, cluster_id: str
) -> dict[str, Any]:
    result = await pool.capella.create_backup(org_id, project_id, cluster_id)
    return fmt_ok(result)


async def capella_restore_backup_impl(
    pool: ClientPool,
    org_id: str,
    project_id: str,
    cluster_id: str,
    backup_id: str,
    target_cluster_id: str | None = None,
) -> dict[str, Any]:
    result = await pool.capella.restore_backup(
        org_id, project_id, cluster_id, backup_id, target_cluster_id=target_cluster_id
    )
    return fmt_ok(result)


async def capella_list_api_keys_impl(pool: ClientPool, org_id: str) -> dict[str, Any]:
    keys = await pool.capella.list_api_keys(org_id)
    return fmt_ok(keys)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def capella_list_organizations() -> dict[str, Any]:
        """List all Capella organizations the API key has access to."""
        return await call_tool_observed(
            "capella_list_organizations",
            capella_list_organizations_impl,
            pool,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={},
        )

    @mcp.tool()
    async def capella_list_clusters(org_id: str, project_id: str) -> dict[str, Any]:
        """List Capella clusters in a project."""
        return await call_tool_observed(
            "capella_list_clusters",
            capella_list_clusters_impl,
            pool,
            org_id,
            project_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id},
        )

    @mcp.tool()
    async def capella_get_cluster(org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """Get a Capella cluster's details."""
        return await call_tool_observed(
            "capella_get_cluster",
            capella_get_cluster_impl,
            pool,
            org_id,
            project_id,
            cluster_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id, "cluster_id": cluster_id},
        )

    @mcp.tool()
    async def capella_create_cluster(
        org_id: str, project_id: str, cluster_spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new Capella cluster from a cluster spec dict."""
        return await call_tool_observed(
            "capella_create_cluster",
            capella_create_cluster_impl,
            pool,
            org_id,
            project_id,
            cluster_spec,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id},
        )

    @mcp.tool()
    async def capella_delete_cluster(org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """Delete a Capella cluster. Destructive."""
        return await call_tool_observed(
            "capella_delete_cluster",
            capella_delete_cluster_impl,
            pool,
            org_id,
            project_id,
            cluster_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id, "cluster_id": cluster_id},
        )

    @mcp.tool()
    async def capella_list_backups(org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """List backups for a Capella cluster."""
        return await call_tool_observed(
            "capella_list_backups",
            capella_list_backups_impl,
            pool,
            org_id,
            project_id,
            cluster_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id, "cluster_id": cluster_id},
        )

    @mcp.tool()
    async def capella_create_backup(org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """Trigger a new backup of a Capella cluster."""
        return await call_tool_observed(
            "capella_create_backup",
            capella_create_backup_impl,
            pool,
            org_id,
            project_id,
            cluster_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id, "project_id": project_id, "cluster_id": cluster_id},
        )

    @mcp.tool()
    async def capella_restore_backup(
        org_id: str,
        project_id: str,
        cluster_id: str,
        backup_id: str,
        target_cluster_id: str | None = None,
    ) -> dict[str, Any]:
        """Restore a Capella backup, optionally into a different target cluster."""
        return await call_tool_observed(
            "capella_restore_backup",
            capella_restore_backup_impl,
            pool,
            org_id,
            project_id,
            cluster_id,
            backup_id,
            target_cluster_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "org_id": org_id,
                "project_id": project_id,
                "cluster_id": cluster_id,
                "backup_id": backup_id,
                "target_cluster_id": target_cluster_id,
            },
        )

    @mcp.tool()
    async def capella_list_api_keys(org_id: str) -> dict[str, Any]:
        """List Capella API keys for an organization."""
        return await call_tool_observed(
            "capella_list_api_keys",
            capella_list_api_keys_impl,
            pool,
            org_id,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"org_id": org_id},
        )

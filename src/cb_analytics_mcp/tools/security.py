# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Security and RBAC tools."""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from cb_analytics_mcp.couchbase.models import (
    GroupUpsertRequest,
    PermissionCheckRequest,
    RbacDomain,
    UserUpsertRequest,
)
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


def _coerce_domain(value: str | None) -> RbacDomain | None:
    if not value:
        return None
    return RbacDomain(value.lower())


async def list_users_impl(
    pool: ClientPool,
    domain: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    users = await client.security.list_users(domain=_coerce_domain(domain))
    return fmt_ok([u.model_dump() for u in users], cluster=name)


async def get_user_impl(
    pool: ClientPool,
    domain: str,
    username: str,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    user = await client.security.get_user(RbacDomain(domain.lower()), username)
    return fmt_ok(user.model_dump(), cluster=name)


async def upsert_user_impl(
    pool: ClientPool,
    domain: str,
    username: str,
    roles: str,
    password: str | None = None,
    full_name: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    req = UserUpsertRequest(
        password=SecretStr(password) if password else None,
        roles=roles,
        name=full_name,
    )
    await client.security.upsert_user(RbacDomain(domain.lower()), username, req)
    return fmt_ok({"upserted": username, "domain": domain}, cluster=name)


async def delete_user_impl(
    pool: ClientPool,
    domain: str,
    username: str,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.security.delete_user(RbacDomain(domain.lower()), username)
    return fmt_ok({"deleted": username}, cluster=name)


async def list_groups_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    groups = await client.security.list_groups()
    return fmt_ok([g.model_dump() for g in groups], cluster=name)


async def upsert_group_impl(
    pool: ClientPool,
    groupname: str,
    roles: str,
    description: str | None = None,
    cluster: str | None = None,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    req = GroupUpsertRequest(description=description, roles=roles)
    await client.security.upsert_group(groupname, req)
    return fmt_ok({"upserted": groupname}, cluster=name)


async def delete_group_impl(pool: ClientPool, groupname: str, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    await client.security.delete_group(groupname)
    return fmt_ok({"deleted": groupname}, cluster=name)


async def list_roles_impl(pool: ClientPool, cluster: str | None = None) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    roles = await client.security.list_roles()
    return fmt_ok(roles, cluster=name)


async def check_permissions_impl(
    pool: ClientPool, permissions: str, cluster: str | None = None
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    result = await client.security.check_permissions(PermissionCheckRequest(permissions=permissions))
    return fmt_ok(result, cluster=name)


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def list_users(domain: str | None = None, cluster: str | None = None) -> dict[str, Any]:
        """List users, optionally filtered by domain ('local' or 'external')."""
        return await call_tool_observed(
            "list_users",
            list_users_impl,
            pool,
            domain,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"domain": domain, "cluster": cluster},
        )

    @mcp.tool()
    async def get_user(domain: str, username: str, cluster: str | None = None) -> dict[str, Any]:
        """Get a specific user by domain and username."""
        return await call_tool_observed(
            "get_user",
            get_user_impl,
            pool,
            domain,
            username,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"domain": domain, "username": username, "cluster": cluster},
        )

    @mcp.tool()
    async def upsert_user(
        domain: str,
        username: str,
        roles: str,
        password: str | None = None,
        full_name: str | None = None,
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Create or update a user. `roles` is a comma-separated list of role specs
        e.g. 'analytics_reader[*],query_select[bucket1]'.
        """
        return await call_tool_observed(
            "upsert_user",
            upsert_user_impl,
            pool,
            domain,
            username,
            roles,
            password,
            full_name,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "domain": domain,
                "username": username,
                "roles": roles,
                "full_name": full_name,
                "cluster": cluster,
                # password is in args but redacted by audit
                "password": password,
            },
        )

    @mcp.tool()
    async def delete_user(domain: str, username: str, cluster: str | None = None) -> dict[str, Any]:
        """Delete a user by domain and username."""
        return await call_tool_observed(
            "delete_user",
            delete_user_impl,
            pool,
            domain,
            username,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"domain": domain, "username": username, "cluster": cluster},
        )

    @mcp.tool()
    async def list_groups(cluster: str | None = None) -> dict[str, Any]:
        """List all groups."""
        return await call_tool_observed(
            "list_groups",
            list_groups_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def upsert_group(
        groupname: str,
        roles: str,
        description: str | None = None,
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a group."""
        return await call_tool_observed(
            "upsert_group",
            upsert_group_impl,
            pool,
            groupname,
            roles,
            description,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "groupname": groupname,
                "roles": roles,
                "description": description,
                "cluster": cluster,
            },
        )

    @mcp.tool()
    async def delete_group(groupname: str, cluster: str | None = None) -> dict[str, Any]:
        """Delete a group."""
        return await call_tool_observed(
            "delete_group",
            delete_group_impl,
            pool,
            groupname,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"groupname": groupname, "cluster": cluster},
        )

    @mcp.tool()
    async def list_roles(cluster: str | None = None) -> dict[str, Any]:
        """List all available roles."""
        return await call_tool_observed(
            "list_roles",
            list_roles_impl,
            pool,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"cluster": cluster},
        )

    @mcp.tool()
    async def check_permissions(permissions: str, cluster: str | None = None) -> dict[str, Any]:
        """
        Check whether the authenticated user has the given comma-separated permissions,
        e.g. 'cluster.analytics!read,cluster.admin!write'.
        """
        return await call_tool_observed(
            "check_permissions",
            check_permissions_impl,
            pool,
            permissions,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"permissions": permissions, "cluster": cluster},
        )

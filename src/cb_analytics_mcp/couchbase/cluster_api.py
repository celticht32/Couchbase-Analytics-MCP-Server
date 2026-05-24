# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Cluster, Security/RBAC, and Capella REST endpoints."""

from __future__ import annotations

from typing import Any

import structlog

from cb_analytics_mcp.couchbase.http_client import HttpClient
from cb_analytics_mcp.couchbase.models import (
    AutoFailoverSettings,
    ClusterDetails,
    ClusterInfo,
    ClusterTask,
    GroupInfo,
    GroupUpsertRequest,
    PermissionCheckRequest,
    RbacDomain,
    RebalanceProgress,
    SystemEvent,
    UserInfo,
    UserUpsertRequest,
)

log = structlog.get_logger(__name__)


# ── Cluster ────────────────────────────────────────────────────────────────────


class ClusterAPI:
    """Cluster-wide operations: ping, info, tasks, failover, events."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_cluster_info(self) -> ClusterInfo:
        r = await self._http.get_mgmt("/pools")
        return ClusterInfo.model_validate(r.json())

    async def get_cluster_details(self) -> ClusterDetails:
        r = await self._http.get_mgmt("/pools/default")
        body = r.json()
        # Extract memory quota fields cleanly
        details: dict[str, Any] = {
            "clusterName": body.get("clusterName"),
            "nodes": body.get("nodes", []),
            "rebalanceStatus": body.get("rebalanceStatus"),
            "balanced": body.get("balanced"),
            "memoryQuota": body.get("memoryQuota"),
            "cbasMemoryQuota": body.get("cbasMemoryQuota"),
        }
        return ClusterDetails.model_validate(details)

    async def get_cluster_tasks(self) -> list[ClusterTask]:
        r = await self._http.get_mgmt("/pools/default/tasks")
        body = r.json()
        items = body if isinstance(body, list) else []
        return [ClusterTask.model_validate(x) for x in items]

    async def get_rebalance_progress(self) -> RebalanceProgress:
        r = await self._http.get_mgmt("/pools/default/tasks")
        body = r.json()
        for task in body if isinstance(body, list) else []:
            if task.get("type") == "rebalance":
                return RebalanceProgress.model_validate(task)
        return RebalanceProgress(status="none")

    async def get_auto_failover_settings(self) -> AutoFailoverSettings:
        r = await self._http.get_mgmt("/settings/autoFailover")
        return AutoFailoverSettings.model_validate(r.json())

    async def configure_auto_failover(self, settings: AutoFailoverSettings) -> None:
        body = {
            "enabled": "true" if settings.enabled else "false",
            "timeout": str(settings.timeout),
            "maxCount": str(settings.maxCount),
        }
        await self._http.post_mgmt("/settings/autoFailover", data=body)

    async def get_system_events(self, since_time: str | None = None) -> list[SystemEvent]:
        params: dict[str, Any] = {}
        if since_time:
            params["sinceTime"] = since_time
        r = await self._http.get_mgmt("/events", params=params or None)
        body = r.json()
        items = body if isinstance(body, list) else body.get("events", [])
        return [SystemEvent.model_validate(x) for x in items]

    async def who_am_i(self) -> dict[str, Any]:
        r = await self._http.get_mgmt("/whoami")
        result = r.json()
        return result if isinstance(result, dict) else {}


# ── Security / RBAC ────────────────────────────────────────────────────────────


class SecurityAPI:
    """User, group, role, and permission-check endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def list_users(self, domain: RbacDomain | None = None) -> list[UserInfo]:
        path = "/settings/rbac/users"
        if domain is not None:
            path += f"/{domain.value}"
        r = await self._http.get_mgmt(path)
        body = r.json()
        items = body if isinstance(body, list) else []
        return [UserInfo.model_validate(x) for x in items]

    async def get_user(self, domain: RbacDomain, username: str) -> UserInfo:
        r = await self._http.get_mgmt(f"/settings/rbac/users/{domain.value}/{username}")
        return UserInfo.model_validate(r.json())

    async def upsert_user(
        self,
        domain: RbacDomain,
        username: str,
        request: UserUpsertRequest,
    ) -> None:
        body: dict[str, str] = {"roles": request.roles}
        if request.password is not None:
            body["password"] = request.password.get_secret_value()
        if request.name:
            body["name"] = request.name
        await self._http.put_mgmt(
            f"/settings/rbac/users/{domain.value}/{username}",
            data=body,
        )

    async def delete_user(self, domain: RbacDomain, username: str) -> None:
        await self._http.delete_mgmt(f"/settings/rbac/users/{domain.value}/{username}")

    async def list_groups(self) -> list[GroupInfo]:
        r = await self._http.get_mgmt("/settings/rbac/groups")
        body = r.json()
        items = body if isinstance(body, list) else []
        return [GroupInfo.model_validate(x) for x in items]

    async def upsert_group(self, groupname: str, request: GroupUpsertRequest) -> None:
        body: dict[str, str] = {"roles": request.roles}
        if request.description:
            body["description"] = request.description
        await self._http.put_mgmt(f"/settings/rbac/groups/{groupname}", data=body)

    async def delete_group(self, groupname: str) -> None:
        await self._http.delete_mgmt(f"/settings/rbac/groups/{groupname}")

    async def list_roles(self) -> list[dict[str, Any]]:
        r = await self._http.get_mgmt("/settings/rbac/roles")
        body = r.json()
        return body if isinstance(body, list) else []

    async def check_permissions(self, request: PermissionCheckRequest) -> dict[str, bool]:
        r = await self._http.post_mgmt(
            "/pools/default/checkPermissions",
            data={"permissions": request.permissions},
        )
        body = r.json()
        return body if isinstance(body, dict) else {}


# ── Capella Management API ────────────────────────────────────────────────────


class CapellaClient:
    """
    Client for the Capella Cloud Management API v4.

    Uses bearer-token auth (CB_CAPELLA_API_KEY_SECRET) — separate from
    self-managed cluster auth.
    """

    def __init__(
        self,
        api_key_secret: str,
        base_url: str = "https://cloudapi.cloud.couchbase.com",
        timeout: float = 60.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = self._make_client(api_key_secret, timeout)

    @staticmethod
    def _make_client(api_key_secret: str, timeout: float) -> Any:
        import httpx

        return httpx.AsyncClient(
            base_url="https://cloudapi.cloud.couchbase.com",
            headers={
                "Authorization": f"Bearer {api_key_secret}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._client.request(method, path, **kwargs)
        if response.status_code == 204 or not response.content:
            return None
        if 200 <= response.status_code < 300:
            return response.json()

        # Map errors consistently
        from cb_analytics_mcp.couchbase.exceptions import (
            AnalyticsAuthError,
            AnalyticsNotFoundError,
            AnalyticsRequestError,
            AnalyticsServerError,
        )

        body = response.text[:500]
        if response.status_code in (401, 403):
            raise AnalyticsAuthError(f"Capella {response.status_code}: {body}")
        if response.status_code == 404:
            raise AnalyticsNotFoundError(f"Capella 404: {body}")
        if response.status_code < 500:
            raise AnalyticsRequestError(
                f"Capella {response.status_code}: {body}", status_code=response.status_code
            )
        raise AnalyticsServerError(
            f"Capella {response.status_code}: {body}", status_code=response.status_code
        )

    @staticmethod
    def _as_list(result: Any) -> list[dict[str, Any]]:
        """Normalise a Capella list response — handles either {"data": [...]} or [...]."""
        if result is None:
            return []
        if isinstance(result, dict):
            data = result.get("data", [])
            return list(data) if isinstance(data, list) else []
        if isinstance(result, list):
            return list(result)
        return []

    # ── Organizations ──────────────────────────────────────────────────────────

    async def list_organizations(self) -> list[dict[str, Any]]:
        return self._as_list(await self._request("GET", "/v4/organizations"))

    # ── Clusters ───────────────────────────────────────────────────────────────

    async def list_clusters(self, org_id: str, project_id: str) -> list[dict[str, Any]]:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters"
        return self._as_list(await self._request("GET", path))

    async def get_cluster(self, org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters/{cluster_id}"
        result = await self._request("GET", path)
        return result or {}

    async def create_cluster(
        self,
        org_id: str,
        project_id: str,
        cluster_spec: dict[str, Any],
    ) -> dict[str, Any]:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters"
        result = await self._request("POST", path, json=cluster_spec)
        return result or {}

    async def delete_cluster(self, org_id: str, project_id: str, cluster_id: str) -> None:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters/{cluster_id}"
        await self._request("DELETE", path)

    # ── Backups ────────────────────────────────────────────────────────────────

    async def list_backups(self, org_id: str, project_id: str, cluster_id: str) -> list[dict[str, Any]]:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters/{cluster_id}/backups"
        return self._as_list(await self._request("GET", path))

    async def create_backup(self, org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        path = f"/v4/organizations/{org_id}/projects/{project_id}/clusters/{cluster_id}/backups"
        result = await self._request("POST", path, json={})
        return result or {}

    async def restore_backup(
        self,
        org_id: str,
        project_id: str,
        cluster_id: str,
        backup_id: str,
        target_cluster_id: str | None = None,
    ) -> dict[str, Any]:
        path = (
            f"/v4/organizations/{org_id}/projects/{project_id}"
            f"/clusters/{cluster_id}/backups/{backup_id}/restore"
        )
        body: dict[str, Any] = {}
        if target_cluster_id:
            body["targetClusterId"] = target_cluster_id
        result = await self._request("POST", path, json=body)
        return result or {}

    # ── API keys ───────────────────────────────────────────────────────────────

    async def list_api_keys(self, org_id: str) -> list[dict[str, Any]]:
        path = f"/v4/organizations/{org_id}/apikeys"
        return self._as_list(await self._request("GET", path))

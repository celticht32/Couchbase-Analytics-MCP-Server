# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Capella Analytics Management API client.

Targets: https://cloudapi.cloud.couchbase.com/v4/
Auth:    Bearer token (API key secret), NOT Basic Auth.

This is a completely separate product and API from self-managed
Enterprise Analytics. The Capella Management API manages cluster
lifecycle (create, scale, backup) rather than individual queries.
For SQL++ query execution within Capella Analytics, use the standard
AnalyticsClient pointed at the cluster's query endpoint.

References:
  https://docs.couchbase.com/analytics/management-api-guide/management-api-intro.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from cb_analytics.exceptions import (
    AnalyticsAuthError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)

log = structlog.get_logger(__name__)

CAPELLA_BASE_URL = "https://cloudapi.cloud.couchbase.com"


class CapellaConfig(BaseSettings):
    """
    Configuration for Capella Analytics Management API.

    Environment variables (CB_CAPELLA_ prefix):
      CB_CAPELLA_API_KEY_SECRET   — Bearer token (API key secret)
      CB_CAPELLA_BASE_URL         — Override API base (default: cloudapi.cloud.couchbase.com)
      CB_CAPELLA_TIMEOUT_SECONDS  — Per-request timeout
    """

    model_config = SettingsConfigDict(
        env_prefix="CB_CAPELLA_",
        env_file=".env",
        case_sensitive=False,
    )

    api_key_secret: SecretStr
    base_url: str = CAPELLA_BASE_URL
    timeout_seconds: float = 60.0


class CapellaAnalyticsClient:
    """
    Async context-manager client for the Capella Analytics Management API v4.

    API groups exposed:
      organizations   — list organizations
      clusters        — create/list/get/delete Columnar clusters
      backups         — create/list/restore backups
      api_keys        — manage API keys

    All requests use Bearer token authentication with the API key secret.
    The token is never logged.

    Example::

        config = CapellaConfig(api_key_secret="my-secret-token")
        async with CapellaAnalyticsClient(config) as capella:
            orgs = await capella.list_organizations()
            clusters = await capella.list_clusters(org_id=orgs[0]["id"], project_id="proj-id")
    """

    def __init__(self, config: CapellaConfig | None = None) -> None:
        self._config = config or CapellaConfig()  # type: ignore[call-arg]
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers={
                "Authorization": f"Bearer {self._config.api_key_secret.get_secret_value()}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self._config.timeout_seconds),
        )

    async def __aenter__(self) -> "CapellaAnalyticsClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with asyncio.timeout(self._config.timeout_seconds + 5):
                response = await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as e:
            raise AnalyticsConnectionError(f"Capella API connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise AnalyticsConnectionError(f"Capella API timeout: {e}") from e
        except TimeoutError as e:
            raise AnalyticsConnectionError(f"Capella API asyncio timeout: {e}") from e

        status = response.status_code
        if status == 204:
            return None
        body: Any = None
        try:
            body = response.json()
        except Exception:
            body = response.text

        if status in (200, 201, 202):
            return body
        if status == 401:
            raise AnalyticsAuthError("Capella API key invalid or expired (401)")
        if status == 403:
            raise AnalyticsAuthError("Capella API key lacks required role (403)")
        if status == 404:
            raise AnalyticsNotFoundError(f"Capella resource not found (404): {path}")
        if status == 400:
            raise AnalyticsRequestError(f"Capella bad request (400): {str(body)[:500]}")
        if status >= 500:
            raise AnalyticsServerError(f"Capella server error ({status}): {str(body)[:200]}")
        raise AnalyticsRequestError(f"Capella unexpected status {status}")

    # ── Organizations ─────────────────────────────────────────────────────────

    async def list_organizations(self) -> list[dict[str, Any]]:
        """GET /v4/organizations — list organizations accessible to this API key."""
        raw = await self._request("GET", "/v4/organizations")
        data = raw if isinstance(raw, dict) else {}
        return data.get("data", raw) if isinstance(raw, dict) else []

    # ── Clusters ──────────────────────────────────────────────────────────────

    async def list_clusters(self, org_id: str, project_id: str) -> list[dict[str, Any]]:
        """GET /v4/organizations/{org_id}/projects/{project_id}/analyticsClusters."""
        raw = await self._request(
            "GET",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters",
        )
        return (raw or {}).get("data", [])

    async def get_cluster(self, org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """GET /v4/organizations/{org}/projects/{proj}/analyticsClusters/{cluster}."""
        return await self._request(
            "GET",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters/{cluster_id}",
        ) or {}

    async def create_cluster(
        self, org_id: str, project_id: str, cluster_spec: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /v4/organizations/{org}/projects/{proj}/analyticsClusters."""
        return await self._request(
            "POST",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters",
            json=cluster_spec,
        ) or {}

    async def delete_cluster(self, org_id: str, project_id: str, cluster_id: str) -> None:
        """DELETE /v4/organizations/{org}/projects/{proj}/analyticsClusters/{cluster}."""
        await self._request(
            "DELETE",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters/{cluster_id}",
        )

    # ── Backups ───────────────────────────────────────────────────────────────

    async def list_backups(self, org_id: str, project_id: str, cluster_id: str) -> list[dict[str, Any]]:
        """GET .../analyticsClusters/{cluster}/backups."""
        raw = await self._request(
            "GET",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters/{cluster_id}/backups",
        )
        return (raw or {}).get("data", [])

    async def create_backup(self, org_id: str, project_id: str, cluster_id: str) -> dict[str, Any]:
        """POST .../analyticsClusters/{cluster}/backups — on-demand full backup."""
        return await self._request(
            "POST",
            f"/v4/organizations/{org_id}/projects/{project_id}/analyticsClusters/{cluster_id}/backups",
        ) or {}

    async def restore_backup(
        self,
        org_id: str,
        project_id: str,
        cluster_id: str,
        backup_id: str,
        target_cluster_id: str | None = None,
    ) -> dict[str, Any]:
        """POST .../backups/{backup_id}/restore."""
        payload: dict[str, Any] = {}
        if target_cluster_id:
            payload["targetClusterId"] = target_cluster_id
        return await self._request(
            "POST",
            f"/v4/organizations/{org_id}/projects/{project_id}"
            f"/analyticsClusters/{cluster_id}/backups/{backup_id}/restore",
            json=payload,
        ) or {}

    # ── API Keys ──────────────────────────────────────────────────────────────

    async def list_api_keys(self, org_id: str) -> list[dict[str, Any]]:
        """GET /v4/organizations/{org_id}/apikeys."""
        raw = await self._request("GET", f"/v4/organizations/{org_id}/apikeys")
        return (raw or {}).get("data", [])

    async def create_api_key(self, org_id: str, key_spec: dict[str, Any]) -> dict[str, Any]:
        """POST /v4/organizations/{org_id}/apikeys."""
        return await self._request("POST", f"/v4/organizations/{org_id}/apikeys", json=key_spec) or {}

    async def delete_api_key(self, org_id: str, key_id: str) -> None:
        """DELETE /v4/organizations/{org_id}/apikeys/{key_id}."""
        await self._request("DELETE", f"/v4/organizations/{org_id}/apikeys/{key_id}")

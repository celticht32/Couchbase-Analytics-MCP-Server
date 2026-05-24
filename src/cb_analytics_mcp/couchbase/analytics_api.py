# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Analytics REST endpoints — one class per documented group.

Each class takes an HttpClient and exposes the methods the MCP tools need.
"""

from __future__ import annotations

from typing import Any

import structlog

from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsLibraryError,
    AnalyticsQueryError,
)
from cb_analytics_mcp.couchbase.http_client import HttpClient
from cb_analytics_mcp.couchbase.models import (
    ActiveRequest,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsSettings,
    CompletedRequest,
    IngestionStatus,
    LibraryInfo,
    LinkInfo,
    ServiceConfig,
    ServiceStatus,
)

log = structlog.get_logger(__name__)


# ── Analytics service (query execution) ────────────────────────────────────────


class AnalyticsServiceAPI:
    """SQL++ query execution against the Analytics service."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def execute(self, request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
        response = await self._http.post_analytics(
            "/api/v1/request",
            json=request.to_api_payload(),
        )
        return self._parse_response(response.json())

    async def execute_readonly(self, request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
        params: dict[str, str | int] = {"statement": request.statement}
        if request.scan_consistency.value != "not_bounded":
            params["scan_consistency"] = request.scan_consistency.value
        if request.timeout:
            params["timeout"] = request.timeout
        response = await self._http.get_analytics("/api/v1/request", params=params)
        return self._parse_response(response.json())

    @staticmethod
    def _parse_response(body: dict[str, Any]) -> AnalyticsQueryResponse:
        resp = AnalyticsQueryResponse.model_validate(body)
        if resp.errors:
            first = resp.errors[0]
            raise AnalyticsQueryError(
                first.msg or "Query failed",
                code=first.code,
            )
        return resp


# ── Admin (status, requests, restart) ──────────────────────────────────────────


class AnalyticsAdminAPI:
    """Service status, ingestion, requests, and restart endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_service_status(self) -> ServiceStatus:
        r = await self._http.get_analytics("/analytics/cluster")
        return ServiceStatus.model_validate(r.json())

    async def get_ingestion_status(self) -> IngestionStatus:
        r = await self._http.get_analytics("/analytics/status/ingestion")
        body = r.json()
        # API returns {"links":[...]} OR just [...]
        if isinstance(body, list):
            body = {"links": body}
        return IngestionStatus.model_validate(body)

    async def get_active_requests(self) -> list[ActiveRequest]:
        r = await self._http.get_analytics("/analytics/admin/active_requests")
        body = r.json()
        items = body if isinstance(body, list) else body.get("requests", [])
        return [ActiveRequest.model_validate(x) for x in items]

    async def cancel_request(self, client_context_id: str) -> None:
        await self._http.delete_analytics(
            "/analytics/admin/active_requests",
            params={"client_context_id": client_context_id},
        )

    async def get_completed_requests(self, client_context_id: str | None = None) -> list[CompletedRequest]:
        params: dict[str, Any] = {}
        if client_context_id:
            params["client_context_id"] = client_context_id
        r = await self._http.get_analytics(
            "/analytics/admin/completed_requests",
            params=params or None,
        )
        body = r.json()
        items = body if isinstance(body, list) else body.get("requests", [])
        return [CompletedRequest.model_validate(x) for x in items]

    async def restart_node(self) -> None:
        await self._http.post_analytics("/analytics/node/restart")

    async def restart_service(self) -> None:
        await self._http.post_analytics("/analytics/cluster/restart")


# ── Config (service-level) ─────────────────────────────────────────────────────


class AnalyticsConfigAPI:
    """Service-level Analytics configuration."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_service_config(self) -> ServiceConfig:
        r = await self._http.get_analytics("/analytics/config/service")
        return ServiceConfig.model_validate(r.json())

    async def update_service_config(self, cfg: ServiceConfig) -> ServiceConfig:
        body = cfg.model_dump(exclude_none=True)
        r = await self._http.put_analytics("/analytics/config/service", json=body)
        return ServiceConfig.model_validate(r.json())


# ── Settings (cluster-wide Analytics settings, e.g. replicas) ──────────────────


class AnalyticsSettingsAPI:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_settings(self) -> AnalyticsSettings:
        r = await self._http.get_mgmt("/settings/analytics")
        return AnalyticsSettings.model_validate(r.json())

    async def update_settings(self, settings: AnalyticsSettings) -> AnalyticsSettings:
        body = settings.model_dump(exclude_none=True)
        r = await self._http.post_mgmt("/settings/analytics", data=body)
        # Couchbase echoes back the updated settings
        try:
            return AnalyticsSettings.model_validate(r.json())
        except ValueError:
            return settings  # no body → assume applied


# ── Links ──────────────────────────────────────────────────────────────────────


class AnalyticsLinksAPI:
    """Analytics data source link management."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_all_links(
        self,
        dataverse: str | None = None,
        link_type: str | None = None,
    ) -> list[LinkInfo]:
        params: dict[str, Any] = {}
        if dataverse:
            params["dataverse"] = dataverse
        if link_type:
            params["type"] = link_type
        r = await self._http.get_analytics("/analytics/link", params=params or None)
        body = r.json()
        items = body if isinstance(body, list) else body.get("links", [])
        return [LinkInfo.model_validate(x) for x in items]

    async def get_link(self, name: str) -> LinkInfo:
        r = await self._http.get_analytics(f"/analytics/link/{name}")
        body = r.json()
        if isinstance(body, list):
            if not body:
                from cb_analytics_mcp.couchbase.exceptions import AnalyticsNotFoundError

                raise AnalyticsNotFoundError(f"Link '{name}' not found")
            body = body[0]
        return LinkInfo.model_validate(body)

    async def create_link(
        self,
        name: str,
        dataverse: str,
        config: dict[str, Any] | Any,
    ) -> None:
        body = self._link_config_to_dict(config)
        body["name"] = name
        body["dataverse"] = dataverse
        await self._http.post_analytics("/analytics/link", json=body)

    async def update_link(
        self,
        name: str,
        config: dict[str, Any] | Any,
    ) -> None:
        body = self._link_config_to_dict(config)
        await self._http.put_analytics(f"/analytics/link/{name}", json=body)

    async def delete_link(self, name: str) -> None:
        await self._http.delete_analytics(f"/analytics/link/{name}")

    @staticmethod
    def _link_config_to_dict(config: Any) -> dict[str, Any]:
        if isinstance(config, dict):
            return dict(config)  # caller might pass dict — copy to avoid mutation
        # Typed S3LinkConfig / AzureBlobLinkConfig / GCSLinkConfig / CouchbaseLinkConfig
        if hasattr(config, "to_api_dict"):
            result = config.to_api_dict()
            if not isinstance(result, dict):
                raise TypeError(
                    f"{type(config).__name__}.to_api_dict() must return dict, got {type(result).__name__}"
                )
            return result
        raise TypeError(f"Unsupported link config type: {type(config).__name__}")


# ── Libraries (UDF) ────────────────────────────────────────────────────────────


class AnalyticsLibraryAPI:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def list_libraries(self) -> list[LibraryInfo]:
        r = await self._http.get_analytics("/analytics/library")
        body = r.json()
        items = body if isinstance(body, list) else body.get("libraries", [])
        return [LibraryInfo.model_validate(x) for x in items]

    async def delete_library(self, scope: str, library_name: str) -> None:
        try:
            await self._http.delete_analytics(f"/analytics/library/{scope}/{library_name}")
        except Exception as e:
            raise AnalyticsLibraryError(str(e)) from e

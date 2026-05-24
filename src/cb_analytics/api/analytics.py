# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Analytics Service, Admin, Config, Settings, Links, and Library APIs.

All credential fields use to_api_dict() which unwraps SecretStr at the
HTTP boundary — secrets never appear in logs or tracebacks.

Bug fixes vs v1.0:
  - model_dump replaced with to_api_dict() / exclude_unset to preserve 0/False
  - IngestionStatus parsed with IngestionStatus.from_raw()
  - named_args serialization documented
  - params={} vs None handled consistently
  - Library API added with remote-origin documentation
"""

from __future__ import annotations

from typing import Any

from cb_analytics.exceptions import AnalyticsLibraryError, AnalyticsQueryError
from cb_analytics.http_client import HttpClient, _warn_if_interpolated
from cb_analytics.models import (
    ActiveRequest,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsSettings,
    CompletedRequest,
    IngestionStatus,
    LibraryInfo,
    LinkConfig,
    LinkInfo,
    NodeConfig,
    ServiceConfig,
    ServiceStatus,
)


# ── Analytics Service API ─────────────────────────────────────────────────────

class AnalyticsServiceAPI:
    """POST/GET /api/v1/request — SQL++ query execution."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def execute(self, request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
        """
        POST /api/v1/request

        Execute a SQL++ statement. Use parameterized queries (args= or
        named_args=) instead of string interpolation to avoid injection risks.

        Named parameters are serialized as $name keys in the payload, as
        required by the Analytics REST API spec.

        Raises:
            AnalyticsQueryError: If the response body contains errors.
        """
        _warn_if_interpolated(request.statement)

        payload: dict[str, Any] = {"statement": request.statement}

        if request.args is not None:
            payload["args"] = request.args
        if request.named_args:
            # Named params use $name keys per the Analytics REST API spec
            payload.update({f"${k}": v for k, v in request.named_args.items()})
        if request.client_context_id:
            payload["client_context_id"] = request.client_context_id
        if request.timeout:
            payload["timeout"] = request.timeout
        if request.scan_consistency:
            payload["scan_consistency"] = request.scan_consistency.value
        if request.read_only is not None:
            payload["readonly"] = request.read_only
        if request.pretty is not None:
            payload["pretty"] = request.pretty
        if request.max_result_size is not None:
            payload["max_result_size"] = request.max_result_size

        raw = await self._http.analytics_post("/api/v1/request", json=payload)
        if raw is None:
            raise AnalyticsQueryError(message="Analytics service returned empty response (204)")
        response = AnalyticsQueryResponse.model_validate(raw)

        if response.errors:
            first = response.errors[0]
            raise AnalyticsQueryError(
                message=first.msg,
                code=first.code,
                query=first.query,
                line=first.line,
                column=first.column,
            )
        return response

    async def execute_readonly(self, request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
        """
        GET /api/v1/request

        Read-only SQL++ via HTTP GET. The statement is a query parameter.
        Use for simple queries; large payloads should use execute() (POST).
        """
        _warn_if_interpolated(request.statement)

        params: dict[str, Any] = {"statement": request.statement}
        if request.client_context_id:
            params["client_context_id"] = request.client_context_id
        if request.timeout:
            params["timeout"] = request.timeout
        if request.scan_consistency:
            params["scan_consistency"] = request.scan_consistency.value

        raw = await self._http.analytics_get("/api/v1/request", params=params)
        if raw is None:
            raise AnalyticsQueryError(message="Analytics service returned empty response (204)")
        response = AnalyticsQueryResponse.model_validate(raw)

        if response.errors:
            first = response.errors[0]
            raise AnalyticsQueryError(
                message=first.msg,
                code=first.code,
                query=first.query,
                line=first.line,
                column=first.column,
            )
        return response


# ── Analytics Admin API ───────────────────────────────────────────────────────

class AnalyticsAdminAPI:
    """Admin: active/completed requests, service status, restart, ingestion."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_active_requests(self) -> list[ActiveRequest]:
        """GET /api/v1/active_requests — currently executing queries."""
        raw = await self._http.analytics_get("/api/v1/active_requests")
        results = raw if isinstance(raw, list) else []
        return [ActiveRequest.model_validate(r) for r in results]

    async def cancel_request(self, client_context_id: str) -> None:
        """DELETE /api/v1/active_requests — cancel by clientContextID."""
        await self._http.analytics_delete(
            "/api/v1/active_requests",
            params={"client_context_id": client_context_id},
        )

    async def get_completed_requests(
        self,
        client_context_id: str | None = None,
        statement: str | None = None,
    ) -> list[CompletedRequest]:
        """GET /api/v1/completed_requests — recent query history."""
        params: dict[str, Any] = {}
        if client_context_id:
            params["client_context_id"] = client_context_id
        if statement:
            params["statement"] = statement

        raw = await self._http.analytics_get(
            "/api/v1/completed_requests",
            params=params if params else None,
        )
        results = raw if isinstance(raw, list) else []
        return [CompletedRequest.model_validate(r) for r in results]

    async def get_service_status(self) -> ServiceStatus:
        """GET /api/v1/status/service — service state and CC revision lag."""
        raw = await self._http.analytics_get("/api/v1/status/service")
        return ServiceStatus.model_validate(raw)

    async def restart_service(self) -> None:
        """POST /api/v1/service/restart — restart all Analytics nodes (interrupts queries)."""
        await self._http.analytics_post("/api/v1/service/restart")

    async def restart_node(self) -> None:
        """POST /api/v1/node/restart — restart this node only."""
        await self._http.analytics_post("/api/v1/node/restart")

    async def get_ingestion_status(self) -> IngestionStatus:
        """GET /api/v1/status/ingestion — per-link ingestion state."""
        raw = await self._http.analytics_get("/api/v1/status/ingestion")
        return IngestionStatus.from_raw(raw)


# ── Analytics Config API ──────────────────────────────────────────────────────

class AnalyticsConfigAPI:
    """GET/PUT /api/v1/config/service and /api/v1/config/node."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_service_config(self) -> ServiceConfig:
        """GET /api/v1/config/service."""
        raw = await self._http.analytics_get("/api/v1/config/service")
        return ServiceConfig.model_validate(raw)

    async def update_service_config(self, config: ServiceConfig) -> ServiceConfig:
        """
        PUT /api/v1/config/service.

        Only explicitly set fields are sent (uses exclude_unset so 0 and False
        are preserved). Changes take effect immediately.
        """
        raw = await self._http.analytics_put("/api/v1/config/service", json=config.to_api_dict())
        return ServiceConfig.model_validate(raw) if raw is not None else config

    async def get_node_config(self) -> NodeConfig:
        """GET /api/v1/config/node."""
        raw = await self._http.analytics_get("/api/v1/config/node")
        return NodeConfig.model_validate(raw)

    async def update_node_config(self, config: NodeConfig) -> NodeConfig:
        """PUT /api/v1/config/node — applies to this node only."""
        raw = await self._http.analytics_put("/api/v1/config/node", json=config.to_api_dict())
        return NodeConfig.model_validate(raw) if raw is not None else config


# ── Analytics Settings API ────────────────────────────────────────────────────

class AnalyticsSettingsAPI:
    """GET/POST /settings/analytics (management port 8091)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_settings(self) -> AnalyticsSettings:
        raw = await self._http.mgmt_get("/settings/analytics")
        return AnalyticsSettings.model_validate(raw)

    async def update_settings(self, settings: AnalyticsSettings) -> AnalyticsSettings:
        """POST /settings/analytics — preserves 0 and False values correctly."""
        payload = settings.to_api_dict()
        raw = await self._http.mgmt_post("/settings/analytics", data=payload)
        return AnalyticsSettings.model_validate(raw or payload)


# ── Analytics Links API ───────────────────────────────────────────────────────

class AnalyticsLinksAPI:
    """CRUD for Analytics links (Couchbase/S3/Azure Blob/GCS).

    Credentials are never logged — link configs use to_api_dict() which
    unwraps SecretStr values only at the HTTP serialization boundary.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def create_link(self, name: str, dataverse: str, config: LinkConfig | dict[str, Any]) -> dict[str, Any]:
        """
        POST /api/v1/link/{name}

        Create an Analytics link. Pass a typed LinkConfig model (recommended)
        or a raw dict. Credentials in the config are serialized safely.
        """
        if hasattr(config, "to_api_dict"):
            payload = {"dataverse": dataverse, "name": name, **config.to_api_dict()}  # type: ignore[union-attr]
        else:
            payload = {"dataverse": dataverse, "name": name, **config}  # type: ignore[arg-type]
        raw = await self._http.analytics_post(f"/api/v1/link/{name}", json=payload)
        return raw or {}

    async def get_link(self, name: str) -> LinkInfo:
        """GET /api/v1/link/{name} — credentials are redacted in the response."""
        raw = await self._http.analytics_get(f"/api/v1/link/{name}")
        return LinkInfo.model_validate(raw) if raw is not None else LinkInfo()

    async def update_link(self, name: str, config: LinkConfig | dict[str, Any]) -> dict[str, Any]:
        """PUT /api/v1/link/{name} — link type cannot be changed."""
        if hasattr(config, "to_api_dict"):
            payload: dict[str, Any] = config.to_api_dict()  # type: ignore[union-attr]
        else:
            payload = dict(config)  # type: ignore[arg-type]
        raw = await self._http.analytics_put(f"/api/v1/link/{name}", json=payload)
        return raw or {}

    async def delete_link(self, name: str) -> None:
        """DELETE /api/v1/link/{name} — link must be disconnected first."""
        await self._http.analytics_delete(f"/api/v1/link/{name}")

    async def get_all_links(
        self,
        dataverse: str | None = None,
        link_type: str | None = None,
    ) -> list[LinkInfo]:
        """GET /api/v1/link — all links, optionally filtered."""
        params: dict[str, Any] = {}
        if dataverse:
            params["dataverse"] = dataverse
        if link_type:
            params["type"] = link_type

        raw = await self._http.analytics_get(
            "/api/v1/link",
            params=params if params else None,
        )
        results = raw if isinstance(raw, list) else []
        return [LinkInfo.model_validate(r) for r in results]


# ── Analytics Library API (UDF management) ────────────────────────────────────

class AnalyticsLibraryAPI:
    """
    Manage UDF libraries for SQL++ user-defined functions.

    IMPORTANT — Remote upload restriction:
        POST (upload) requires the request to originate locally from a node
        running the Analytics service. Remote uploads return 403 and the
        SDK raises AnalyticsLibraryError with a clear explanation.
        GET and DELETE work remotely without restriction.

    Endpoints (port 8095):
        GET    /analytics/library               — list all libraries
        PUT    /analytics/library/{scope}/{lib} — create or update
        DELETE /analytics/library/{scope}/{lib} — delete
    """

    _REMOTE_UPLOAD_MSG = (
        "Library upload requires the request to originate locally from a node "
        "running the Analytics service. Remote uploads are blocked by Couchbase "
        "Enterprise Analytics. Run this operation directly on an Analytics node, "
        "or use the Couchbase UI."
    )

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def list_libraries(self) -> list[LibraryInfo]:
        """GET /analytics/library — return all UDF libraries and their functions."""
        raw = await self._http.analytics_get("/analytics/library")
        results = raw if isinstance(raw, list) else []
        return [LibraryInfo.model_validate(r) for r in results]

    async def upload_library(
        self,
        scope: str,
        library_name: str,
        library_type: str,
        library_data: bytes,
    ) -> None:
        """
        PUT /analytics/library/{scope}/{library_name}

        Upload or replace a UDF library (Python .pyz or Java .jar).

        WARNING: This endpoint only works when called from a node running
        the Analytics service. Remote calls return 403 and raise
        AnalyticsLibraryError.

        Args:
            scope:         Analytics scope e.g. "travel-sample/inventory"
            library_name:  Library identifier e.g. "mylib"
            library_type:  "python" or "java"
            library_data:  Binary content of the .pyz or .jar file.

        Raises:
            AnalyticsLibraryError: If the server rejects the upload (typically
                                   because the request is not local-origin).
        """
        try:
            await self._http.analytics_put(
                f"/analytics/library/{scope}/{library_name}",
                json={"type": library_type, "data": library_data.hex()},
            )
        except Exception as exc:
            if "403" in str(exc) or "401" in str(exc):
                raise AnalyticsLibraryError(self._REMOTE_UPLOAD_MSG) from exc
            raise AnalyticsLibraryError(f"Library upload failed: {exc}") from exc

    async def delete_library(self, scope: str, library_name: str) -> None:
        """DELETE /analytics/library/{scope}/{library_name} — works remotely."""
        await self._http.analytics_delete(f"/analytics/library/{scope}/{library_name}")

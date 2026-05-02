# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Analytics Service API implementation.

Covers:
  - Service API: POST/GET /api/v1/request (query execution)
  - Admin API: active/completed requests, service status, restart, ingestion
  - Config API: service-level and node-level parameters
  - Settings API: /settings/analytics
  - Links API: CRUD for couchbase/s3/azureblob/gcs links
"""

from __future__ import annotations

from typing import Any

from cb_analytics.exceptions import AnalyticsQueryError
from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    ActiveRequest,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsSettings,
    CompletedRequest,
    IngestionStatus,
    LinkInfo,
    NodeConfig,
    ServiceConfig,
    ServiceStatus,
)


class AnalyticsServiceAPI:
    """
    POST /api/v1/request  — execute SQL++ statements.
    GET  /api/v1/request  — read-only SQL++ execution.

    Raises AnalyticsQueryError if the server returns errors in the
    query response body (status != "success").
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def execute(self, request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
        """
        POST /api/v1/request

        Execute a SQL++ statement against the Analytics service.
        Supports positional parameters, named parameters, scan consistency,
        timeout, and read-only mode.

        Raises:
            AnalyticsQueryError: If the response contains query-level errors.
        """
        payload: dict[str, Any] = {"statement": request.statement}

        if request.args:
            payload["args"] = request.args
        if request.named_args:
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

        Read-only SQL++ execution via HTTP GET. The statement is passed
        as a query parameter. Suitable for simple queries without large
        parameter payloads.
        """
        params: dict[str, Any] = {"statement": request.statement}
        if request.client_context_id:
            params["client_context_id"] = request.client_context_id
        if request.timeout:
            params["timeout"] = request.timeout
        if request.scan_consistency:
            params["scan_consistency"] = request.scan_consistency.value

        raw = await self._http.analytics_get("/api/v1/request", params=params)
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


class AnalyticsAdminAPI:
    """
    Admin operations: active/completed requests, service status,
    restart, ingestion status.

    All endpoints are under /api/v1/ on the Analytics port (8095).
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_active_requests(self) -> list[ActiveRequest]:
        """
        GET /api/v1/active_requests

        Return currently executing Analytics queries.
        """
        raw = await self._http.analytics_get("/api/v1/active_requests")
        results = raw if isinstance(raw, list) else []
        return [ActiveRequest.model_validate(r) for r in results]

    async def cancel_request(self, client_context_id: str) -> None:
        """
        DELETE /api/v1/active_requests

        Cancel a running query by its clientContextID.
        """
        await self._http.analytics_delete(
            "/api/v1/active_requests",
            params={"client_context_id": client_context_id},
        )

    async def get_completed_requests(
        self,
        client_context_id: str | None = None,
        statement: str | None = None,
    ) -> list[CompletedRequest]:
        """
        GET /api/v1/completed_requests

        Return recently completed Analytics queries.
        Optional filters by clientContextID or statement substring.
        """
        params: dict[str, Any] = {}
        if client_context_id:
            params["client_context_id"] = client_context_id
        if statement:
            params["statement"] = statement

        raw = await self._http.analytics_get("/api/v1/completed_requests", params=params or None)
        results = raw if isinstance(raw, list) else []
        return [CompletedRequest.model_validate(r) for r in results]

    async def get_service_status(self) -> ServiceStatus:
        """
        GET /api/v1/status/service

        Return Analytics service state, node authorization, and CC revision lag.
        """
        raw = await self._http.analytics_get("/api/v1/status/service")
        return ServiceStatus.model_validate(raw)

    async def restart_service(self) -> None:
        """
        POST /api/v1/service/restart

        Restart the entire Analytics service across all nodes.
        This interrupts all running queries.
        """
        await self._http.analytics_post("/api/v1/service/restart")

    async def restart_node(self) -> None:
        """
        POST /api/v1/node/restart

        Restart the Analytics service on this specific node only.
        """
        await self._http.analytics_post("/api/v1/node/restart")

    async def get_ingestion_status(self) -> IngestionStatus:
        """
        GET /api/v1/status/ingestion

        Return per-link/dataset ingestion status including pending mutations
        and connection state.
        """
        raw = await self._http.analytics_get("/api/v1/status/ingestion")
        return IngestionStatus.model_validate(raw)


class AnalyticsConfigAPI:
    """
    Configuration API: service-level and node-level parameters.

    Service-level parameters apply to all Analytics nodes.
    Node-level parameters apply only to the addressed node.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_service_config(self) -> ServiceConfig:
        """
        GET /api/v1/config/service

        Return all current service-level configuration parameters
        (memory budgets, result limits, compiler options, etc.).
        """
        raw = await self._http.analytics_get("/api/v1/config/service")
        return ServiceConfig.model_validate(raw)

    async def update_service_config(self, config: ServiceConfig) -> ServiceConfig:
        """
        PUT /api/v1/config/service

        Modify one or more service-level parameters.
        Only fields that are set (non-None) are sent.
        Changes take effect immediately and affect all running queries.
        """
        payload = {k: v for k, v in config.model_dump().items() if v is not None}
        raw = await self._http.analytics_put("/api/v1/config/service", json=payload)
        return ServiceConfig.model_validate(raw)

    async def get_node_config(self) -> NodeConfig:
        """
        GET /api/v1/config/node

        Return node-specific configuration parameters for this Analytics node.
        """
        raw = await self._http.analytics_get("/api/v1/config/node")
        return NodeConfig.model_validate(raw)

    async def update_node_config(self, config: NodeConfig) -> NodeConfig:
        """
        PUT /api/v1/config/node

        Modify node-specific parameters. Applies only to the addressed node.
        """
        payload = {k: v for k, v in config.model_dump().items() if v is not None}
        raw = await self._http.analytics_put("/api/v1/config/node", json=payload)
        return NodeConfig.model_validate(raw)


class AnalyticsSettingsAPI:
    """
    Settings API: /settings/analytics on the management port (8091).

    Controls cluster-wide Analytics settings such as replica count.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_settings(self) -> AnalyticsSettings:
        """
        GET /settings/analytics

        Return current Analytics settings (e.g. numReplicas).
        """
        raw = await self._http.mgmt_get("/settings/analytics")
        return AnalyticsSettings.model_validate(raw)

    async def update_settings(self, settings: AnalyticsSettings) -> AnalyticsSettings:
        """
        POST /settings/analytics

        Modify Analytics settings. Only non-None fields are sent.
        """
        payload = {k: v for k, v in settings.model_dump().items() if v is not None}
        raw = await self._http.mgmt_post("/settings/analytics", data=payload)
        return AnalyticsSettings.model_validate(raw or payload)


class AnalyticsLinksAPI:
    """
    Links API: create, query, edit, and delete Analytics links.

    Links define data ingestion sources:
      - couchbase: local or remote Couchbase cluster (KV DCP)
      - s3: AWS S3 bucket
      - azureblob: Azure Blob Storage
      - gcs: Google Cloud Storage
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def create_link(self, name: str, dataverse: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        POST /api/v1/link/{name}

        Create a new Analytics link. The link name must be unique within
        the specified dataverse.

        Args:
            name: Link name (URL-path segment, must not contain '/').
            dataverse: Dataverse in which to create the link.
            config: Link type-specific configuration dict (type, credentials, etc.)
        """
        payload = {"dataverse": dataverse, **config}
        raw = await self._http.analytics_post(f"/api/v1/link/{name}", json=payload)
        return raw or {}

    async def get_link(self, name: str) -> LinkInfo:
        """
        GET /api/v1/link/{name}

        Return metadata for a single link (credentials are redacted).
        """
        raw = await self._http.analytics_get(f"/api/v1/link/{name}")
        return LinkInfo.model_validate(raw)

    async def update_link(self, name: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        PUT /api/v1/link/{name}

        Edit an existing link's configuration. The link type cannot be changed.
        """
        raw = await self._http.analytics_put(f"/api/v1/link/{name}", json=config)
        return raw or {}

    async def delete_link(self, name: str) -> None:
        """
        DELETE /api/v1/link/{name}

        Delete a link. The link must be disconnected before deletion.
        """
        await self._http.analytics_delete(f"/api/v1/link/{name}")

    async def get_all_links(
        self,
        dataverse: str | None = None,
        link_type: str | None = None,
    ) -> list[LinkInfo]:
        """
        GET /api/v1/link

        Return all links, optionally filtered by dataverse or type.
        """
        params: dict[str, Any] = {}
        if dataverse:
            params["dataverse"] = dataverse
        if link_type:
            params["type"] = link_type

        raw = await self._http.analytics_get("/api/v1/link", params=params or None)
        results = raw if isinstance(raw, list) else []
        return [LinkInfo.model_validate(r) for r in results]

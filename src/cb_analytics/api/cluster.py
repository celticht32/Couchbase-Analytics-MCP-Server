# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Cluster & Nodes API implementation.

Bug fixes vs v1.0:
  - Credential models use to_api_dict() — SecretStr unwrapped at boundary
  - eventsStreaming endpoint added as async generator
  - GET/POST /settings/rebalance added
  - GET /pools/default/settings/memcached/global added
  - model_dump replaced with to_api_dict() to preserve 0/False
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

import structlog

from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AddNodeRequest,
    AlertSettings,
    AlternateAddressConfig,
    AutoFailoverSettings,
    ClusterInfo,
    ClusterInitRequest,
    ClusterInitResponse,
    ClusterTask,
    CredentialsRequest,
    EjectNodeRequest,
    FailoverRequest,
    LogCollectionRequest,
    MemoryConfigRequest,
    NodeInfo,
    NodeInitRequest,
    NodeServices,
    PoolsDefault,
    RebalanceProgress,
    RebalanceRequest,
    RebalanceRetryConfig,
    RecoveryTypeRequest,
    RenameNodeRequest,
    SetupServicesRequest,
    StatsSingleResponse,
    StatsMultipleRequest,
    SystemEvent,
)

log = structlog.get_logger(__name__)


class ClusterAPI:
    """REST API for Couchbase cluster and node management."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ── Initialization ────────────────────────────────────────────────────────

    async def initialize_cluster(self, request: ClusterInitRequest) -> ClusterInitResponse:
        """POST /clusterInit."""
        raw = await self._http.mgmt_post("/clusterInit", data=request.to_api_dict())
        return ClusterInitResponse.model_validate(raw) if raw is not None else ClusterInitResponse(newBaseUri="")

    async def initialize_node(self, request: NodeInitRequest) -> None:
        """POST /nodes/self/controller/settings."""
        data = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_post("/nodes/self/controller/settings", data=data)

    async def establish_credentials(self, request: CredentialsRequest) -> None:
        """POST /settings/web."""
        await self._http.mgmt_post("/settings/web", data=request.to_api_dict())

    async def rename_node(self, request: RenameNodeRequest) -> None:
        """POST /node/controller/rename."""
        await self._http.mgmt_post("/node/controller/rename", data=request.model_dump())

    async def configure_memory(self, request: MemoryConfigRequest) -> None:
        """POST /pools/default — memory quotas / cluster name."""
        data = {k: v for k, v in request.model_dump(by_alias=True, exclude_unset=True).items() if v is not None}
        await self._http.mgmt_post("/pools/default", data=data)

    async def setup_services(self, request: SetupServicesRequest) -> None:
        """POST /node/controller/setupServices."""
        await self._http.mgmt_post("/node/controller/setupServices", data=request.model_dump())

    # ── Node Addition / Removal ───────────────────────────────────────────────

    async def add_node(self, request: AddNodeRequest) -> dict[str, Any]:
        """POST /controller/addNode."""
        raw = await self._http.mgmt_post("/controller/addNode", data=request.to_api_dict())
        return raw or {}

    async def join_cluster(self, cluster_ip: str, username: str, password: str) -> None:
        """POST /node/controller/doJoinCluster."""
        await self._http.mgmt_post(
            "/node/controller/doJoinCluster",
            data={"clusterMemberHostIp": cluster_ip, "user": username, "password": password},
        )

    async def eject_node(self, request: EjectNodeRequest) -> None:
        """POST /controller/ejectNode."""
        await self._http.mgmt_post("/controller/ejectNode", data=request.model_dump())

    # ── Rebalance ─────────────────────────────────────────────────────────────

    async def rebalance(self, request: RebalanceRequest) -> None:
        """POST /controller/rebalance."""
        data = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_post("/controller/rebalance", data=data)

    async def get_rebalance_progress(self) -> RebalanceProgress:
        """GET /pools/default/rebalanceProgress."""
        raw = await self._http.mgmt_get("/pools/default/rebalanceProgress")
        return RebalanceProgress.model_validate(raw)

    async def get_retry_rebalance_config(self) -> RebalanceRetryConfig:
        """GET /pools/default/retryRebalance."""
        raw = await self._http.mgmt_get("/pools/default/retryRebalance")
        return RebalanceRetryConfig.model_validate(raw)

    async def configure_rebalance_retry(self, config: RebalanceRetryConfig) -> None:
        """POST /pools/default/retryRebalance."""
        data = {k: v for k, v in config.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/pools/default/retryRebalance", data=data)

    async def get_pending_retry_rebalance(self) -> dict[str, Any]:
        """GET /pools/default/pendingRetryRebalance."""
        return await self._http.mgmt_get("/pools/default/pendingRetryRebalance") or {}

    async def cancel_rebalance_retry(self, rebalance_id: str) -> None:
        """POST /controller/cancelRebalanceRetry/{rebalance_id}."""
        await self._http.mgmt_post(f"/controller/cancelRebalanceRetry/{rebalance_id}")

    async def get_rebalance_settings(self) -> dict[str, Any]:
        """GET /settings/rebalance — concurrent vBucket move limit."""
        return await self._http.mgmt_get("/settings/rebalance") or {}

    async def configure_rebalance_settings(self, settings: dict[str, Any]) -> None:
        """POST /settings/rebalance — set concurrent vBucket move limit."""
        await self._http.mgmt_post("/settings/rebalance", json=settings)

    # ── Failover ──────────────────────────────────────────────────────────────

    async def hard_failover(self, request: FailoverRequest) -> None:
        """POST /controller/failOver."""
        data = request.model_dump(exclude_none=True)
        await self._http.mgmt_post("/controller/failOver", data=data)

    async def graceful_failover(self, otp_node: str) -> None:
        """POST /controller/startGracefulFailover."""
        await self._http.mgmt_post("/controller/startGracefulFailover", data={"otpNode": otp_node})

    async def set_recovery_type(self, request: RecoveryTypeRequest) -> None:
        """POST /controller/setRecoveryType."""
        await self._http.mgmt_post("/controller/setRecoveryType", data=request.model_dump())

    # ── Auto-Failover ─────────────────────────────────────────────────────────

    async def get_auto_failover_settings(self) -> AutoFailoverSettings:
        """GET /settings/autoFailover."""
        raw = await self._http.mgmt_get("/settings/autoFailover")
        return AutoFailoverSettings.model_validate(raw)

    async def configure_auto_failover(self, settings: AutoFailoverSettings) -> None:
        """POST /settings/autoFailover — preserves False/0 values correctly."""
        data = {k: v for k, v in settings.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/settings/autoFailover", data=data)

    async def reset_auto_failover(self) -> None:
        """POST /settings/autoFailover/resetCount."""
        await self._http.mgmt_post("/settings/autoFailover/resetCount")

    # ── Settings and Connections ──────────────────────────────────────────────

    async def get_internal_settings(self) -> dict[str, Any]:
        """GET /internalSettings."""
        return await self._http.mgmt_get("/internalSettings") or {}

    async def set_internal_settings(self, settings: dict[str, Any]) -> None:
        """POST /internalSettings."""
        await self._http.mgmt_post("/internalSettings", data=settings)

    async def get_cluster_connections(self) -> dict[str, Any]:
        """GET /pools/default/settings/memcached/global — cluster connection settings."""
        return await self._http.mgmt_get("/pools/default/settings/memcached/global") or {}

    async def configure_cluster_connections(self, settings: dict[str, Any]) -> None:
        """POST /pools/default/settings/memcached/global."""
        await self._http.mgmt_post("/pools/default/settings/memcached/global", json=settings)

    async def setup_alternate_address(self, config: AlternateAddressConfig) -> None:
        """PUT /node/controller/setupAlternateAddresses/external."""
        data = {k: v for k, v in config.model_dump().items() if v is not None}
        await self._http.mgmt_put("/node/controller/setupAlternateAddresses/external", data=data)

    async def delete_alternate_address(self) -> None:
        """DELETE /node/controller/setupAlternateAddresses/external."""
        await self._http.mgmt_delete("/node/controller/setupAlternateAddresses/external")

    async def get_alert_settings(self) -> AlertSettings:
        """GET /settings/alerts."""
        raw = await self._http.mgmt_get("/settings/alerts")
        return AlertSettings.model_validate(raw)

    async def configure_alerts(self, settings: AlertSettings) -> None:
        """POST /settings/alerts."""
        data = settings.model_dump(exclude_none=True)
        await self._http.mgmt_post("/settings/alerts", json=data)

    async def send_test_email(self) -> None:
        """POST /settings/alerts/sendTestEmail."""
        await self._http.mgmt_post("/settings/alerts/sendTestEmail")

    # ── Status and Events ─────────────────────────────────────────────────────

    async def get_cluster_tasks(self) -> list[ClusterTask]:
        """GET /pools/default/tasks."""
        raw = await self._http.mgmt_get("/pools/default/tasks")
        results = raw if isinstance(raw, list) else []
        return [ClusterTask.model_validate(t) for t in results]

    async def get_cluster_info(self) -> ClusterInfo:
        """GET /pools — top-level cluster info."""
        raw = await self._http.mgmt_get("/pools")
        return ClusterInfo.model_validate(raw)

    async def get_cluster_details(self) -> PoolsDefault:
        """GET /pools/default."""
        raw = await self._http.mgmt_get("/pools/default")
        return PoolsDefault.model_validate(raw)

    async def get_system_events(self, since_time: str | None = None) -> list[SystemEvent]:
        """GET /events — system events snapshot."""
        params: dict[str, Any] = {}
        if since_time:
            params["since"] = since_time
        raw = await self._http.mgmt_get("/events", params=params if params else None)
        if isinstance(raw, list):
            events = raw
        elif isinstance(raw, dict):
            events = raw.get("events", [])
        else:
            events = []
        return [SystemEvent.model_validate(e) for e in events]

    async def stream_events(
        self,
        max_events: int | None = None,
        timeout_seconds: float = 300.0,
    ) -> AsyncGenerator[SystemEvent, None]:
        """
        GET /eventsStreaming — Server-Sent Events stream.

        Yields parsed SystemEvent objects as they arrive from the server.
        The stream continues until the connection closes, max_events is
        reached, or timeout_seconds elapses.

        Args:
            max_events:      Stop after yielding this many events. None = unlimited.
            timeout_seconds: Total stream lifetime in seconds (default 5 min).

        Example::

            async for event in client.cluster.stream_events(max_events=100):
                print(event.description)
        """
        client = self._http._mgmt_client
        count = 0

        async def _generate() -> AsyncGenerator[SystemEvent, None]:
            nonlocal count
            async with client.stream("GET", "/eventsStreaming") as response:
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str:
                            try:
                                raw = json.loads(data_str)
                                yield SystemEvent.model_validate(raw)
                                count += 1
                                if max_events is not None and count >= max_events:
                                    return
                            except Exception:
                                log.debug("stream_events_parse_error", line=line[:200])

        try:
            async with asyncio.timeout(timeout_seconds):
                async for event in _generate():
                    yield event
        except asyncio.TimeoutError:
            log.debug("stream_events_timeout", timeout_seconds=timeout_seconds, events_yielded=count)

    async def get_node_info(self) -> NodeInfo:
        """GET /pools/nodes."""
        raw = await self._http.mgmt_get("/pools/nodes")
        return NodeInfo.model_validate(raw)

    async def list_node_services(self) -> NodeServices:
        """GET /pools/default/nodeServices."""
        raw = await self._http.mgmt_get("/pools/default/nodeServices")
        return NodeServices.model_validate(raw)

    async def get_orchestrator_info(self) -> dict[str, Any]:
        """GET /pools/default/terseClusterInfo."""
        return await self._http.mgmt_get("/pools/default/terseClusterInfo") or {}

    async def who_am_i(self) -> dict[str, Any]:
        """GET /whoami — authenticated user info."""
        return await self._http.mgmt_get("/whoami") or {}

    # ── Statistics ────────────────────────────────────────────────────────────

    async def get_statistic(
        self,
        metric_name: str,
        function_expression: str | None = None,
        start: int | None = None,
        end: int | None = None,
        step: int | None = None,
        nodes: list[str] | None = None,
    ) -> StatsSingleResponse:
        """GET /pools/default/stats/range/{metric_name}[/{function_expression}]."""
        path = f"/pools/default/stats/range/{metric_name}"
        if function_expression:
            path += f"/{function_expression}"
        params: dict[str, Any] = {}
        if start is not None:
            params["startTimestamp"] = start
        if end is not None:
            params["endTimestamp"] = end
        if step is not None:
            params["step"] = step
        if nodes:
            params["nodes"] = ",".join(nodes)
        raw = await self._http.mgmt_get(path, params=params if params else None)
        return StatsSingleResponse.model_validate(raw)

    async def get_multiple_statistics(self, request: StatsMultipleRequest) -> list[StatsSingleResponse]:
        """POST /pools/default/stats/range."""
        raw = await self._http.mgmt_post(
            "/pools/default/stats/range",
            json=request.model_dump(exclude_none=True),
        )
        results = raw if isinstance(raw, list) else []
        return [StatsSingleResponse.model_validate(r) for r in results]

    # ── Logging ───────────────────────────────────────────────────────────────

    async def start_log_collection(self, request: LogCollectionRequest) -> None:
        """POST /controller/startLogsCollection."""
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        await self._http.mgmt_post("/controller/startLogsCollection", data=data)

    async def cancel_log_collection(self) -> None:
        """POST /controller/cancelLogsCollection."""
        await self._http.mgmt_post("/controller/cancelLogsCollection")

    async def get_diagnostics(self) -> str:
        """GET /diag."""
        raw = await self._http.mgmt_get("/diag")
        return str(raw)

    async def get_sasl_logs(self, log_name: str | None = None) -> Any:
        """GET /sasl_logs[/{log_name}]."""
        path = f"/sasl_logs/{log_name}" if log_name else "/sasl_logs"
        return await self._http.mgmt_get(path)

    async def log_client_error(self, message: str) -> None:
        """POST /logClientError."""
        await self._http.mgmt_post("/logClientError", data={"msg": message})

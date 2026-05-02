# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Cluster & Nodes API implementation.

Covers all endpoints documented at:
  https://docs.couchbase.com/enterprise-analytics/current/reference/rest-cluster-intro.html

Sections implemented:
  - Cluster Initialization and Provisioning
  - Node Addition and Removal
  - Rebalance
  - Manual Failover
  - Auto-Failover
  - Settings and Connections
  - Status and Events
  - Statistics
  - Logging
"""

from __future__ import annotations

from typing import Any

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


class ClusterAPI:
    """
    REST API for Couchbase cluster and node management.

    All methods are async and return Pydantic models where a defined
    schema exists, or raw dicts/lists for highly variable responses.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ── Cluster Initialization and Provisioning ───────────────────────────────

    async def initialize_cluster(self, request: ClusterInitRequest) -> ClusterInitResponse:
        """
        POST /clusterInit

        Initialize and provision a new single-node cluster in one call.
        Combines node initialization, credential setup, service assignment,
        memory configuration, and cluster naming.
        """
        data = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        raw = await self._http.mgmt_post("/clusterInit", data=data)
        return ClusterInitResponse.model_validate(raw)

    async def initialize_node(self, request: NodeInitRequest) -> None:
        """
        POST /nodes/self/controller/settings

        Set data and analytics storage paths for a node.
        """
        data = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_post("/nodes/self/controller/settings", data=data)

    async def establish_credentials(self, request: CredentialsRequest) -> None:
        """
        POST /settings/web

        Set the administrator username and password for the cluster.
        """
        await self._http.mgmt_post(
            "/settings/web",
            data=request.model_dump(),
        )

    async def rename_node(self, request: RenameNodeRequest) -> None:
        """POST /node/controller/rename — set the node hostname."""
        await self._http.mgmt_post("/node/controller/rename", data=request.model_dump())

    async def configure_memory(self, request: MemoryConfigRequest) -> None:
        """
        POST /pools/default

        Configure memory quotas and/or cluster name.
        """
        data = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_post("/pools/default", data=data)

    async def setup_services(self, request: SetupServicesRequest) -> None:
        """POST /node/controller/setupServices — assign services to a node."""
        await self._http.mgmt_post(
            "/node/controller/setupServices",
            data=request.model_dump(),
        )

    # ── Node Addition and Removal ─────────────────────────────────────────────

    async def add_node(self, request: AddNodeRequest) -> dict[str, Any]:
        """POST /controller/addNode — add a node to the cluster."""
        raw = await self._http.mgmt_post(
            "/controller/addNode",
            data=request.model_dump(),
        )
        return raw or {}

    async def join_cluster(self, cluster_ip: str, username: str, password: str) -> None:
        """POST /node/controller/doJoinCluster — join this node to an existing cluster."""
        await self._http.mgmt_post(
            "/node/controller/doJoinCluster",
            data={"clusterMemberHostIp": cluster_ip, "user": username, "password": password},
        )

    async def eject_node(self, request: EjectNodeRequest) -> None:
        """POST /controller/ejectNode — remove a node from the cluster."""
        await self._http.mgmt_post("/controller/ejectNode", data=request.model_dump())

    # ── Rebalance ─────────────────────────────────────────────────────────────

    async def rebalance(self, request: RebalanceRequest) -> None:
        """POST /controller/rebalance — start a rebalance operation."""
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
        """POST /pools/default/retryRebalance — configure automatic retry on failure."""
        data = {k: v for k, v in config.model_dump().items() if v is not None}
        await self._http.mgmt_post("/pools/default/retryRebalance", data=data)

    async def get_pending_retry_rebalance(self) -> dict[str, Any]:
        """GET /pools/default/pendingRetryRebalance."""
        return await self._http.mgmt_get("/pools/default/pendingRetryRebalance") or {}

    async def cancel_rebalance_retry(self, rebalance_id: str) -> None:
        """POST /controller/cancelRebalanceRetry/{rebalance_id}."""
        await self._http.mgmt_post(f"/controller/cancelRebalanceRetry/{rebalance_id}")

    # ── Manual Failover ───────────────────────────────────────────────────────

    async def hard_failover(self, request: FailoverRequest) -> None:
        """POST /controller/failOver — perform a hard failover."""
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        await self._http.mgmt_post("/controller/failOver", data=data)

    async def graceful_failover(self, otp_node: str) -> None:
        """POST /controller/startGracefulFailover."""
        await self._http.mgmt_post(
            "/controller/startGracefulFailover",
            data={"otpNode": otp_node},
        )

    async def set_recovery_type(self, request: RecoveryTypeRequest) -> None:
        """POST /controller/setRecoveryType."""
        await self._http.mgmt_post("/controller/setRecoveryType", data=request.model_dump())

    # ── Auto-Failover ─────────────────────────────────────────────────────────

    async def get_auto_failover_settings(self) -> AutoFailoverSettings:
        """GET /settings/autoFailover."""
        raw = await self._http.mgmt_get("/settings/autoFailover")
        return AutoFailoverSettings.model_validate(raw)

    async def configure_auto_failover(self, settings: AutoFailoverSettings) -> None:
        """POST /settings/autoFailover — enable/configure auto-failover."""
        data = {k: v for k, v in settings.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/autoFailover", data=data)

    async def reset_auto_failover(self) -> None:
        """POST /settings/autoFailover/resetCount — reset the auto-failover counter."""
        await self._http.mgmt_post("/settings/autoFailover/resetCount")

    # ── Settings and Connections ──────────────────────────────────────────────

    async def get_internal_settings(self) -> dict[str, Any]:
        """GET /internalSettings."""
        return await self._http.mgmt_get("/internalSettings") or {}

    async def set_internal_settings(self, settings: dict[str, Any]) -> None:
        """POST /internalSettings."""
        await self._http.mgmt_post("/internalSettings", data=settings)

    async def get_max_parallel_indexers(self) -> dict[str, Any]:
        """GET /settings/maxParallelIndexers."""
        return await self._http.mgmt_get("/settings/maxParallelIndexers") or {}

    async def set_max_parallel_indexers(self, global_value: int) -> None:
        """POST /settings/maxParallelIndexers."""
        await self._http.mgmt_post(
            "/settings/maxParallelIndexers",
            data={"globalValue": str(global_value)},
        )

    async def setup_alternate_address(self, config: AlternateAddressConfig) -> None:
        """PUT /node/controller/setupAlternateAddresses/external."""
        data = {k: v for k, v in config.model_dump().items() if v is not None}
        await self._http.mgmt_put(
            "/node/controller/setupAlternateAddresses/external",
            data=data,
        )

    async def delete_alternate_address(self) -> None:
        """DELETE /node/controller/setupAlternateAddresses/external."""
        await self._http.mgmt_delete("/node/controller/setupAlternateAddresses/external")

    async def get_alert_settings(self) -> AlertSettings:
        """GET /settings/alerts."""
        raw = await self._http.mgmt_get("/settings/alerts")
        return AlertSettings.model_validate(raw)

    async def configure_alerts(self, settings: AlertSettings) -> None:
        """POST /settings/alerts — configure email alert notifications."""
        data = {k: v for k, v in settings.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/alerts", json=data)

    async def send_test_email(self) -> None:
        """POST /settings/alerts/sendTestEmail."""
        await self._http.mgmt_post("/settings/alerts/sendTestEmail")

    # ── Status and Events ─────────────────────────────────────────────────────

    async def get_cluster_tasks(self) -> list[ClusterTask]:
        """GET /pools/default/tasks — list currently running tasks."""
        raw = await self._http.mgmt_get("/pools/default/tasks")
        if isinstance(raw, list):
            return [ClusterTask.model_validate(t) for t in raw]
        return []

    async def get_rebalance_report(self, report_id: str) -> dict[str, Any]:
        """GET /logs/rebalanceReport?reportID={report_id}."""
        return await self._http.mgmt_get(
            "/logs/rebalanceReport",
            params={"reportID": report_id},
        ) or {}

    async def get_cluster_info(self) -> ClusterInfo:
        """GET /pools — top-level cluster info."""
        raw = await self._http.mgmt_get("/pools")
        return ClusterInfo.model_validate(raw)

    async def get_cluster_details(self) -> PoolsDefault:
        """GET /pools/default — detailed cluster view."""
        raw = await self._http.mgmt_get("/pools/default")
        return PoolsDefault.model_validate(raw)

    async def get_system_events(self, since_time: str | None = None) -> list[SystemEvent]:
        """GET /events — return system events."""
        params: dict[str, Any] = {}
        if since_time:
            params["since"] = since_time
        raw = await self._http.mgmt_get("/events", params=params)
        events = raw if isinstance(raw, list) else raw.get("events", []) if isinstance(raw, dict) else []
        return [SystemEvent.model_validate(e) for e in events]

    async def get_orchestrator_info(self) -> dict[str, Any]:
        """GET /pools/default/terseClusterInfo — identify the orchestrator node."""
        return await self._http.mgmt_get("/pools/default/terseClusterInfo") or {}

    async def get_node_info(self) -> NodeInfo:
        """GET /pools/nodes — information about all nodes."""
        raw = await self._http.mgmt_get("/pools/nodes")
        return NodeInfo.model_validate(raw)

    async def list_node_services(self) -> NodeServices:
        """GET /pools/default/nodeServices."""
        raw = await self._http.mgmt_get("/pools/default/nodeServices")
        return NodeServices.model_validate(raw)

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
        """
        GET /pools/default/stats/range/{metric_name}[/{function_expression}]
        """
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

        raw = await self._http.mgmt_get(path, params=params)
        return StatsSingleResponse.model_validate(raw)

    async def get_multiple_statistics(self, request: StatsMultipleRequest) -> list[StatsSingleResponse]:
        """POST /pools/default/stats/range — get multiple metrics at once."""
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
        """GET /diag — retrieve diagnostic and log information as text."""
        raw = await self._http.mgmt_get("/diag")
        return str(raw)

    async def get_sasl_logs(self, log_name: str | None = None) -> Any:
        """GET /sasl_logs[/{log_name}]."""
        path = f"/sasl_logs/{log_name}" if log_name else "/sasl_logs"
        return await self._http.mgmt_get(path)

    async def log_client_error(self, message: str) -> None:
        """POST /logClientError — log a client-side error on the server."""
        await self._http.mgmt_post("/logClientError", data={"msg": message})

    async def who_am_i(self) -> dict[str, Any]:
        """GET /whoami — return info about the authenticated user."""
        return await self._http.mgmt_get("/whoami") or {}

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unit tests for ClusterAPI — all endpoints mocked with respx."""

from __future__ import annotations

import pytest
import respx
import httpx

from cb_analytics.api.cluster import ClusterAPI
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.http_client import HttpClient
from cb_analytics.exceptions import AnalyticsAuthError, AnalyticsNotFoundError
from cb_analytics.models import (
    AddNodeRequest,
    AutoFailoverSettings,
    ClusterInitRequest,
    CredentialsRequest,
    EjectNodeRequest,
    FailoverRequest,
    LogCollectionRequest,
    MemoryConfigRequest,
    NodeInitRequest,
    RebalanceRequest,
    RebalanceRetryConfig,
    RecoveryType,
    RecoveryTypeRequest,
    RenameNodeRequest,
    SetupServicesRequest,
    StatsMultipleRequest,
)
from tests.conftest import MGMT_BASE, make_response, empty_response


@pytest.fixture
def cluster_api(config: AnalyticsClientConfig) -> ClusterAPI:
    http = HttpClient(
        management_url=MGMT_BASE,
        analytics_url="http://localhost:8095",
        username=config.username,
        password=config.password.get_secret_value(),
        timeout=10.0,
        verify_ssl=False,
        max_retries=1,
    )
    return ClusterAPI(http)


# ── Cluster Initialization ────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_initialize_cluster(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/clusterInit").mock(
        return_value=make_response({"newBaseUri": "http://10.0.0.1:8091/"})
    )
    req = ClusterInitRequest(
        username="admin",
        password="pass",
        services="kv,cbas",
        port="SAME",
    )
    result = await cluster_api.initialize_cluster(req)
    assert result.new_base_uri == "http://10.0.0.1:8091/"


@respx.mock
@pytest.mark.asyncio
async def test_initialize_node(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/nodes/self/controller/settings").mock(
        return_value=empty_response(200)
    )
    await cluster_api.initialize_node(NodeInitRequest(path="/opt/couchbase/data"))


@respx.mock
@pytest.mark.asyncio
async def test_establish_credentials(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/web").mock(return_value=empty_response(200))
    await cluster_api.establish_credentials(
        CredentialsRequest(username="admin", password="password")
    )


@respx.mock
@pytest.mark.asyncio
async def test_rename_node(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/node/controller/rename").mock(return_value=empty_response(200))
    await cluster_api.rename_node(RenameNodeRequest(hostname="node1.example.com"))


@respx.mock
@pytest.mark.asyncio
async def test_configure_memory(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default").mock(return_value=empty_response(200))
    await cluster_api.configure_memory(MemoryConfigRequest(memoryQuota=1024))


@respx.mock
@pytest.mark.asyncio
async def test_setup_services(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/node/controller/setupServices").mock(
        return_value=empty_response(200)
    )
    await cluster_api.setup_services(SetupServicesRequest(services="kv,cbas"))


# ── Node Addition / Removal ───────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_add_node(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/addNode").mock(
        return_value=make_response({"otpNode": "ns_1@node2"})
    )
    result = await cluster_api.add_node(
        AddNodeRequest(hostname="node2", user="admin", password="pass", services="kv")
    )
    assert result["otpNode"] == "ns_1@node2"


@respx.mock
@pytest.mark.asyncio
async def test_eject_node(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/ejectNode").mock(return_value=empty_response(200))
    await cluster_api.eject_node(EjectNodeRequest(otpNode="ns_1@node2"))


@respx.mock
@pytest.mark.asyncio
async def test_join_cluster(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/node/controller/doJoinCluster").mock(
        return_value=empty_response(200)
    )
    await cluster_api.join_cluster("10.0.0.1", "admin", "password")


# ── Rebalance ─────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_rebalance(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/rebalance").mock(return_value=empty_response(200))
    await cluster_api.rebalance(
        RebalanceRequest(knownNodes="ns_1@node1,ns_1@node2", ejectedNodes="ns_1@node3")
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_rebalance_progress(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/rebalanceProgress").mock(
        return_value=make_response({"status": "running", "rawProgress": {}})
    )
    result = await cluster_api.get_rebalance_progress()
    assert result.status == "running"


@respx.mock
@pytest.mark.asyncio
async def test_configure_rebalance_retry(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/retryRebalance").mock(
        return_value=empty_response(200)
    )
    await cluster_api.configure_rebalance_retry(
        RebalanceRetryConfig(enabled=True, afterTimePeriod=300, maxAttempts=3)
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_pending_retry_rebalance(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/pendingRetryRebalance").mock(
        return_value=make_response({"rebalanceId": "abc123", "retryAfter": 300})
    )
    result = await cluster_api.get_pending_retry_rebalance()
    assert result["rebalanceId"] == "abc123"


@respx.mock
@pytest.mark.asyncio
async def test_cancel_rebalance_retry(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/cancelRebalanceRetry/abc123").mock(
        return_value=empty_response(200)
    )
    await cluster_api.cancel_rebalance_retry("abc123")


# ── Failover ──────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_hard_failover(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/failOver").mock(return_value=empty_response(200))
    await cluster_api.hard_failover(FailoverRequest(otpNode="ns_1@node2"))


@respx.mock
@pytest.mark.asyncio
async def test_graceful_failover(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/startGracefulFailover").mock(
        return_value=empty_response(200)
    )
    await cluster_api.graceful_failover("ns_1@node2")


@respx.mock
@pytest.mark.asyncio
async def test_set_recovery_type(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/setRecoveryType").mock(
        return_value=empty_response(200)
    )
    await cluster_api.set_recovery_type(
        RecoveryTypeRequest(otpNode="ns_1@node2", recoveryType=RecoveryType.DELTA)
    )


# ── Auto-Failover ─────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_auto_failover_settings(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/autoFailover").mock(
        return_value=make_response({"enabled": True, "timeout": 120, "maxCount": 3})
    )
    result = await cluster_api.get_auto_failover_settings()
    assert result.enabled is True
    assert result.timeout == 120


@respx.mock
@pytest.mark.asyncio
async def test_configure_auto_failover(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/autoFailover").mock(return_value=empty_response(200))
    await cluster_api.configure_auto_failover(
        AutoFailoverSettings(enabled=True, timeout=120)
    )


@respx.mock
@pytest.mark.asyncio
async def test_reset_auto_failover(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/autoFailover/resetCount").mock(
        return_value=empty_response(200)
    )
    await cluster_api.reset_auto_failover()


# ── Status and Events ─────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_tasks(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(
        return_value=make_response([{"type": "rebalance", "status": "running", "progress": 45.2}])
    )
    tasks = await cluster_api.get_cluster_tasks()
    assert len(tasks) == 1
    assert tasks[0].type == "rebalance"
    assert tasks[0].progress == 45.2


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_info(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=make_response({
            "pools": [{"name": "default", "uri": "/pools/default"}],
            "isAdminCreds": True,
            "uuid": "abc-123",
            "implementationVersion": "7.6.0-0000-enterprise",
        })
    )
    info = await cluster_api.get_cluster_info()
    assert info.uuid == "abc-123"
    assert info.isAdminCreds is True


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_details(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default").mock(
        return_value=make_response({
            "name": "default",
            "nodes": [],
            "clusterName": "MyCluster",
            "balanced": True,
        })
    )
    details = await cluster_api.get_cluster_details()
    assert details.clusterName == "MyCluster"
    assert details.balanced is True


@respx.mock
@pytest.mark.asyncio
async def test_get_system_events(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/events").mock(
        return_value=make_response([
            {"timestamp": "2024-01-01T00:00:00Z", "component": "ns_server",
             "severity": "info", "description": "Node joined"}
        ])
    )
    events = await cluster_api.get_system_events()
    assert len(events) == 1
    assert events[0].component == "ns_server"


@respx.mock
@pytest.mark.asyncio
async def test_list_node_services(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/nodeServices").mock(
        return_value=make_response({"rev": 42, "nodesExt": []})
    )
    result = await cluster_api.list_node_services()
    assert result.rev == 42


# ── Statistics ────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_statistic(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/stats/range/kv_ops_per_sec").mock(
        return_value=make_response({"data": [{"metric": {}, "values": [[1, "42"]]}]})
    )
    result = await cluster_api.get_statistic("kv_ops_per_sec")
    assert len(result.data) == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_multiple_statistics(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/stats/range").mock(
        return_value=make_response([
            {"data": [{"metric": {}, "values": [[1, "10"]]}]},
            {"data": [{"metric": {}, "values": [[1, "20"]]}]},
        ])
    )
    result = await cluster_api.get_multiple_statistics(
        StatsMultipleRequest(specs=[{"metric": "m1"}, {"metric": "m2"}])
    )
    assert len(result) == 2


# ── Logging ───────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_start_log_collection(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/startLogsCollection").mock(
        return_value=empty_response(200)
    )
    await cluster_api.start_log_collection(LogCollectionRequest())


@respx.mock
@pytest.mark.asyncio
async def test_cancel_log_collection(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/cancelLogsCollection").mock(
        return_value=empty_response(200)
    )
    await cluster_api.cancel_log_collection()


@respx.mock
@pytest.mark.asyncio
async def test_log_client_error(cluster_api: ClusterAPI) -> None:
    respx.post(f"{MGMT_BASE}/logClientError").mock(return_value=empty_response(200))
    await cluster_api.log_client_error("Something went wrong")


@respx.mock
@pytest.mark.asyncio
async def test_who_am_i(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/whoami").mock(
        return_value=make_response({"id": "admin", "domain": "local", "roles": []})
    )
    result = await cluster_api.who_am_i()
    assert result["id"] == "admin"


# ── Error handling ────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=httpx.Response(401, content=b'{"message":"Unauthorized"}')
    )
    with pytest.raises(AnalyticsAuthError):
        await cluster_api.get_cluster_info()


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(cluster_api: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/stats/range/nonexistent").mock(
        return_value=httpx.Response(404, content=b"Not Found")
    )
    with pytest.raises(AnalyticsNotFoundError):
        await cluster_api.get_statistic("nonexistent")


# ── Regression tests for v1.1.0 bug fixes ─────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_hard_failover_allows_unsafe_false_preserved(cluster_api: ClusterAPI) -> None:
    """BUG FIX: allowUnsafe=False must NOT be stripped from the request body."""
    from cb_analytics.models import FailoverRequest
    route = respx.post(f"{MGMT_BASE}/controller/failOver").mock(
        return_value=make_response({})
    )
    await cluster_api.hard_failover(FailoverRequest(otpNode="ns_1@node1", allowUnsafe=False))
    import urllib.parse
    body = dict(urllib.parse.parse_qsl(route.calls[0].request.content.decode()))
    assert "allowUnsafe" in body, "allowUnsafe key should be present"
    assert body["allowUnsafe"] == "false", "allowUnsafe=False must not be stripped"


@respx.mock
@pytest.mark.asyncio
async def test_configure_alerts_enabled_false_preserved(cluster_api: ClusterAPI) -> None:
    """BUG FIX: AlertSettings.enabled=False must NOT be stripped."""
    from cb_analytics.models import AlertSettings
    route = respx.post(f"{MGMT_BASE}/settings/alerts").mock(
        return_value=make_response({})
    )
    await cluster_api.configure_alerts(AlertSettings(enabled=False))
    import json
    body = json.loads(route.calls[0].request.content)
    assert "enabled" in body, "enabled key should be present"
    assert body["enabled"] is False, "enabled=False must not be stripped"

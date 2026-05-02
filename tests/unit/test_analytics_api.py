# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unit tests for Analytics Service, Admin, Config, Settings, and Links APIs."""

from __future__ import annotations

import pytest
import respx
import httpx

from cb_analytics.api.analytics import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import AnalyticsQueryError
from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AnalyticsQueryRequest,
    AnalyticsSettings,
    NodeConfig,
    ScanConsistency,
    ServiceConfig,
)
from tests.conftest import ANALYTICS_BASE, MGMT_BASE, make_response, empty_response


@pytest.fixture
def http(config: AnalyticsClientConfig) -> HttpClient:
    return HttpClient(
        management_url=MGMT_BASE,
        analytics_url=ANALYTICS_BASE,
        username=config.username,
        password=config.password,
        timeout=10.0,
        verify_ssl=False,
        max_retries=1,
    )


# ── Analytics Service API ─────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_execute_success(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-1",
            "clientContextID": "ctx-1",
            "status": "success",
            "results": [{"n": 1}],
            "metrics": {
                "elapsedTime": "50ms",
                "executionTime": "40ms",
                "resultCount": 1,
                "resultSize": 8,
                "warningCount": 0,
                "errorCount": 0,
            },
            "warnings": [],
            "errors": [],
        })
    )
    result = await api.execute(AnalyticsQueryRequest(statement="SELECT 1 AS n"))
    assert result.status == "success"
    assert result.results == [{"n": 1}]
    assert result.metrics is not None
    assert result.metrics.resultCount == 1


@respx.mock
@pytest.mark.asyncio
async def test_execute_with_parameters(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-2",
            "status": "success",
            "results": [],
            "metrics": {"resultCount": 0, "resultSize": 0, "warningCount": 0, "errorCount": 0},
            "warnings": [],
            "errors": [],
        })
    )
    await api.execute(
        AnalyticsQueryRequest(statement="SELECT * FROM `ds` WHERE id = $1", args=[42])
    )
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_execute_with_scan_consistency(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-3",
            "status": "success",
            "results": [],
            "metrics": {"resultCount": 0, "resultSize": 0, "warningCount": 0, "errorCount": 0},
            "warnings": [],
            "errors": [],
        })
    )
    # Should not raise
    await api.execute(
        AnalyticsQueryRequest(
            statement="SELECT 1",
            scan_consistency=ScanConsistency.REQUEST_PLUS,
        )
    )


@respx.mock
@pytest.mark.asyncio
async def test_execute_raises_query_error(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-err",
            "status": "fatal",
            "results": [],
            "metrics": {"resultCount": 0, "resultSize": 0, "warningCount": 0, "errorCount": 1},
            "warnings": [],
            "errors": [{"code": 24000, "msg": "Syntax error near 'BADTOKEN'", "line": 1, "column": 8}],
        })
    )
    with pytest.raises(AnalyticsQueryError) as exc_info:
        await api.execute(AnalyticsQueryRequest(statement="SELECT BADTOKEN"))
    err = exc_info.value
    assert err.code == 24000
    assert "Syntax error" in err.args[0]
    assert err.line == 1
    assert err.column == 8


@respx.mock
@pytest.mark.asyncio
async def test_execute_readonly_get(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-ro",
            "status": "success",
            "results": [{"val": 42}],
            "metrics": {"resultCount": 1, "resultSize": 10, "warningCount": 0, "errorCount": 0},
            "warnings": [],
            "errors": [],
        })
    )
    result = await api.execute_readonly(AnalyticsQueryRequest(statement="SELECT 42 AS val"))
    assert result.results == [{"val": 42}]


@respx.mock
@pytest.mark.asyncio
async def test_execute_with_timeout(http: HttpClient) -> None:
    api = AnalyticsServiceAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "req-t",
            "status": "success",
            "results": [],
            "metrics": {"resultCount": 0, "resultSize": 0, "warningCount": 0, "errorCount": 0},
            "warnings": [],
            "errors": [],
        })
    )
    await api.execute(AnalyticsQueryRequest(statement="SELECT 1", timeout="30s"))


# ── Analytics Admin API ───────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_active_requests(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=make_response([
            {"clientContextID": "ctx-1", "elapsedTime": "5s", "state": "running",
             "statement": "SELECT * FROM big_table"},
        ])
    )
    reqs = await api.get_active_requests()
    assert len(reqs) == 1
    assert reqs[0].clientContextID == "ctx-1"
    assert reqs[0].state == "running"


@respx.mock
@pytest.mark.asyncio
async def test_get_active_requests_empty(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=make_response([])
    )
    reqs = await api.get_active_requests()
    assert reqs == []


@respx.mock
@pytest.mark.asyncio
async def test_cancel_request(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    route = respx.delete(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=empty_response(200)
    )
    await api.cancel_request("ctx-123")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_get_completed_requests(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/completed_requests").mock(
        return_value=make_response([
            {"clientContextID": "done-1", "state": "success",
             "elapsedTime": "100ms", "resultCount": 5}
        ])
    )
    reqs = await api.get_completed_requests()
    assert reqs[0].state == "success"
    assert reqs[0].resultCount == 5


@respx.mock
@pytest.mark.asyncio
async def test_get_service_status(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/service").mock(
        return_value=make_response({
            "authorizedNodes": ["node1", "node2"],
            "ccRevLag": 0,
            "state": "ACTIVE",
        })
    )
    status = await api.get_service_status()
    assert status.state == "ACTIVE"
    assert status.ccRevLag == 0


@respx.mock
@pytest.mark.asyncio
async def test_restart_service(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/service/restart").mock(
        return_value=empty_response(200)
    )
    await api.restart_service()


@respx.mock
@pytest.mark.asyncio
async def test_restart_node(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/node/restart").mock(
        return_value=empty_response(200)
    )
    await api.restart_node()


@respx.mock
@pytest.mark.asyncio
async def test_get_ingestion_status(http: HttpClient) -> None:
    api = AnalyticsAdminAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/ingestion").mock(
        return_value=make_response({
            "links": [
                {"name": "Local", "state": "CONNECTED", "datasetStates": []}
            ]
        })
    )
    result = await api.get_ingestion_status()
    assert len(result.links) == 1


# ── Analytics Config API ──────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_service_config(http: HttpClient) -> None:
    api = AnalyticsConfigAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({
            "storageBuffercacheSize": 1073741824,
            "activeMemoryGlobalBudget": 536870912,
            "resultTtl": 3600,
            "compilerParallelism": 0,
        })
    )
    config = await api.get_service_config()
    assert config.storageBuffercacheSize == 1073741824
    assert config.resultTtl == 3600


@respx.mock
@pytest.mark.asyncio
async def test_update_service_config(http: HttpClient) -> None:
    api = AnalyticsConfigAPI(http)
    respx.put(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({"resultTtl": 7200})
    )
    result = await api.update_service_config(ServiceConfig(resultTtl=7200))
    assert result.resultTtl == 7200


@respx.mock
@pytest.mark.asyncio
async def test_get_node_config(http: HttpClient) -> None:
    api = AnalyticsConfigAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/config/node").mock(
        return_value=make_response({"storageBuffercacheSize": 536870912})
    )
    result = await api.get_node_config()
    assert result.storageBuffercacheSize == 536870912


@respx.mock
@pytest.mark.asyncio
async def test_update_node_config(http: HttpClient) -> None:
    api = AnalyticsConfigAPI(http)
    respx.put(f"{ANALYTICS_BASE}/api/v1/config/node").mock(
        return_value=make_response({"storageBuffercacheSize": 268435456})
    )
    result = await api.update_node_config(NodeConfig(storageBuffercacheSize=268435456))
    assert result.storageBuffercacheSize == 268435456


# ── Analytics Settings API ────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_analytics_settings(http: HttpClient) -> None:
    api = AnalyticsSettingsAPI(http)
    respx.get(f"{MGMT_BASE}/settings/analytics").mock(
        return_value=make_response({"numReplicas": 1})
    )
    result = await api.get_settings()
    assert result.numReplicas == 1


@respx.mock
@pytest.mark.asyncio
async def test_update_analytics_settings(http: HttpClient) -> None:
    api = AnalyticsSettingsAPI(http)
    respx.post(f"{MGMT_BASE}/settings/analytics").mock(
        return_value=make_response({"numReplicas": 2})
    )
    result = await api.update_settings(AnalyticsSettings(numReplicas=2))
    assert result.numReplicas == 2


# ── Analytics Links API ───────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_create_link(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.post(f"{ANALYTICS_BASE}/api/v1/link/myS3Link").mock(
        return_value=make_response({"status": "created"})
    )
    result = await api.create_link(
        name="myS3Link",
        dataverse="Default",
        config={
            "type": "s3",
            "region": "us-east-1",
            "accessKeyId": "AKID",
            "secretAccessKey": "SECRET",
        },
    )
    assert result["status"] == "created"


@respx.mock
@pytest.mark.asyncio
async def test_get_link(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/link/myS3Link").mock(
        return_value=make_response({
            "dataverse": "Default",
            "name": "myS3Link",
            "type": "s3",
            "activeDatasets": ["airline", "hotel"],
        })
    )
    link = await api.get_link("myS3Link")
    assert link.name == "myS3Link"
    assert link.type == "s3"
    assert "airline" in (link.activeDatasets or [])


@respx.mock
@pytest.mark.asyncio
async def test_update_link(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.put(f"{ANALYTICS_BASE}/api/v1/link/myLink").mock(
        return_value=make_response({"status": "updated"})
    )
    result = await api.update_link("myLink", {"region": "eu-west-1"})
    assert result["status"] == "updated"


@respx.mock
@pytest.mark.asyncio
async def test_delete_link(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.delete(f"{ANALYTICS_BASE}/api/v1/link/myLink").mock(
        return_value=empty_response(200)
    )
    await api.delete_link("myLink")


@respx.mock
@pytest.mark.asyncio
async def test_get_all_links(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/link").mock(
        return_value=make_response([
            {"name": "Local", "type": "couchbase", "dataverse": "Default"},
            {"name": "myS3", "type": "s3", "dataverse": "MyDv"},
        ])
    )
    links = await api.get_all_links()
    assert len(links) == 2
    assert links[0].name == "Local"


@respx.mock
@pytest.mark.asyncio
async def test_get_all_links_filtered_by_type(http: HttpClient) -> None:
    api = AnalyticsLinksAPI(http)
    respx.get(f"{ANALYTICS_BASE}/api/v1/link").mock(
        return_value=make_response([
            {"name": "myS3", "type": "s3", "dataverse": "Default"},
        ])
    )
    links = await api.get_all_links(link_type="s3")
    assert all(lk.type == "s3" for lk in links)

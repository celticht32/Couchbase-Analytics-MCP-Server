# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the Analytics API classes."""

from __future__ import annotations

import httpx
import pytest
import respx

from cb_analytics_mcp.couchbase.analytics_api import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLibraryAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsLibraryError,
    AnalyticsQueryError,
)
from cb_analytics_mcp.couchbase.http_client import HttpClient
from cb_analytics_mcp.couchbase.models import (
    AnalyticsQueryRequest,
    ScanConsistency,
    ServiceConfig,
)
from tests.conftest import ANALYTICS_BASE, MGMT_BASE, empty_response, make_response

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def svc(http: HttpClient) -> AnalyticsServiceAPI:
    return AnalyticsServiceAPI(http)


@pytest.fixture
def adm(http: HttpClient) -> AnalyticsAdminAPI:
    return AnalyticsAdminAPI(http)


@pytest.fixture
def cfg(http: HttpClient) -> AnalyticsConfigAPI:
    return AnalyticsConfigAPI(http)


@pytest.fixture
def stg(http: HttpClient) -> AnalyticsSettingsAPI:
    return AnalyticsSettingsAPI(http)


@pytest.fixture
def lnk(http: HttpClient) -> AnalyticsLinksAPI:
    return AnalyticsLinksAPI(http)


@pytest.fixture
def lib(http: HttpClient) -> AnalyticsLibraryAPI:
    return AnalyticsLibraryAPI(http)


# ── AnalyticsServiceAPI ────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_execute_success(svc: AnalyticsServiceAPI) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response(
            {
                "requestID": "r1",
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
            }
        )
    )
    result = await svc.execute(AnalyticsQueryRequest(statement="SELECT 1"))
    assert result.requestID == "r1"
    assert result.results == [{"n": 1}]
    assert result.metrics is not None
    assert result.metrics.elapsedTime == "50ms"


@respx.mock
@pytest.mark.asyncio
async def test_execute_query_error_raises(svc: AnalyticsServiceAPI) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response(
            {
                "requestID": "r2",
                "status": "fatal",
                "results": [],
                "errors": [{"code": 24000, "msg": "Syntax error"}],
            }
        )
    )
    with pytest.raises(AnalyticsQueryError) as exc:
        await svc.execute(AnalyticsQueryRequest(statement="BAD"))
    assert exc.value.code == 24000


@respx.mock
@pytest.mark.asyncio
async def test_execute_readonly_uses_get(svc: AnalyticsServiceAPI) -> None:
    route = respx.get(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"results": [{"n": 1}], "status": "success"})
    )
    await svc.execute_readonly(
        AnalyticsQueryRequest(statement="SELECT 1", scan_consistency=ScanConsistency.REQUEST_PLUS)
    )
    assert route.called
    call_url = route.calls[0].request.url
    assert "scan_consistency=request_plus" in str(call_url)


# ── AnalyticsAdminAPI ──────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_service_status(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/cluster").mock(
        return_value=make_response({"state": "ACTIVE", "ccRevLag": 0, "authorizedNodes": ["n1", "n2"]})
    )
    status = await adm.get_service_status()
    assert status.state == "ACTIVE"
    assert status.authorizedNodes == ["n1", "n2"]


@respx.mock
@pytest.mark.asyncio
async def test_get_ingestion_status_list_form(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/status/ingestion").mock(
        return_value=make_response(
            [
                {"name": "s3link", "state": "CONNECTED", "pendingOperations": 0},
            ]
        )
    )
    s = await adm.get_ingestion_status()
    assert len(s.links) == 1
    assert s.links[0].name == "s3link"


@respx.mock
@pytest.mark.asyncio
async def test_cancel_request(adm: AnalyticsAdminAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/analytics/admin/active_requests").mock(
        return_value=empty_response(200)
    )
    await adm.cancel_request("ctx-abc")
    assert route.called
    assert "client_context_id=ctx-abc" in str(route.calls[0].request.url)


@respx.mock
@pytest.mark.asyncio
async def test_restart_service(adm: AnalyticsAdminAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/analytics/cluster/restart").mock(return_value=empty_response(200))
    await adm.restart_service()
    assert route.called


# ── AnalyticsConfigAPI ─────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_service_config(cfg: AnalyticsConfigAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/config/service").mock(
        return_value=make_response({"resultTtl": 3600, "compilerParallelism": 0})
    )
    c = await cfg.get_service_config()
    assert c.resultTtl == 3600


@respx.mock
@pytest.mark.asyncio
async def test_update_service_config(cfg: AnalyticsConfigAPI) -> None:
    respx.put(f"{ANALYTICS_BASE}/analytics/config/service").mock(
        return_value=make_response({"resultTtl": 7200})
    )
    out = await cfg.update_service_config(ServiceConfig(resultTtl=7200))
    assert out.resultTtl == 7200


# ── AnalyticsSettingsAPI ───────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_settings(stg: AnalyticsSettingsAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/analytics").mock(return_value=make_response({"numReplicas": 1}))
    s = await stg.get_settings()
    assert s.numReplicas == 1


# ── AnalyticsLinksAPI ──────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_all_links(lnk: AnalyticsLinksAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/link").mock(
        return_value=make_response(
            [
                {"name": "s3-1", "type": "s3", "dataverse": "Default", "activeDatasets": []},
                {"name": "cb-1", "type": "couchbase", "dataverse": "Default", "activeDatasets": ["a"]},
            ]
        )
    )
    links = await lnk.get_all_links()
    assert len(links) == 2
    assert links[0].name == "s3-1"


@respx.mock
@pytest.mark.asyncio
async def test_create_link(lnk: AnalyticsLinksAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/analytics/link").mock(return_value=empty_response(201))
    await lnk.create_link("myS3", "Default", {"type": "s3", "region": "us-east-1"})
    assert route.called
    body = route.calls[0].request.content.decode()
    assert "myS3" in body
    assert "us-east-1" in body


@respx.mock
@pytest.mark.asyncio
async def test_delete_link(lnk: AnalyticsLinksAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/analytics/link/myS3").mock(return_value=empty_response(200))
    await lnk.delete_link("myS3")
    assert route.called


# ── AnalyticsLibraryAPI ───────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_list_libraries(lib: AnalyticsLibraryAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/library").mock(
        return_value=make_response([{"name": "mylib", "scope": "Default", "functions": [{"name": "addOne"}]}])
    )
    libs = await lib.list_libraries()
    assert libs[0].name == "mylib"
    assert libs[0].functions[0].name == "addOne"


@respx.mock
@pytest.mark.asyncio
async def test_delete_library_wraps_error(lib: AnalyticsLibraryAPI) -> None:
    respx.delete(f"{ANALYTICS_BASE}/analytics/library/Default/mylib").mock(
        return_value=httpx.Response(409, text="In use")
    )
    with pytest.raises(AnalyticsLibraryError):
        await lib.delete_library("Default", "mylib")


# ── AnalyticsAdminAPI (missing methods) ──────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_service_status(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/cluster").mock(
        return_value=make_response({"state": "ACTIVE", "ccRevLag": 0, "authorizedNodes": ["n1"]})
    )
    out = await adm.get_service_status()
    assert out.state == "ACTIVE"


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_ingestion_status_dict_form(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/status/ingestion").mock(return_value=make_response({"links": []}))
    out = await adm.get_ingestion_status()
    assert out.links == []


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_ingestion_status_list_form(adm: AnalyticsAdminAPI) -> None:
    """API sometimes returns a bare list."""
    respx.get(f"{ANALYTICS_BASE}/analytics/status/ingestion").mock(return_value=make_response([]))
    out = await adm.get_ingestion_status()
    assert out.links == []


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_active_requests_list(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/admin/active_requests").mock(
        return_value=make_response([{"requestID": "r1", "statement": "SELECT 1", "state": "active"}])
    )
    out = await adm.get_active_requests()
    assert len(out) == 1


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_active_requests_dict(adm: AnalyticsAdminAPI) -> None:
    """API can return {requests: [...]}."""
    respx.get(f"{ANALYTICS_BASE}/analytics/admin/active_requests").mock(
        return_value=make_response({"requests": []})
    )
    out = await adm.get_active_requests()
    assert out == []


@respx.mock
@pytest.mark.asyncio
async def test_admin_cancel_request(adm: AnalyticsAdminAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/analytics/admin/active_requests").mock(
        return_value=empty_response(200)
    )
    await adm.cancel_request("ctx-123")
    assert route.called
    # The query string was set
    call = route.calls.last
    assert "client_context_id=ctx-123" in str(call.request.url)


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_completed_requests_no_filter(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/admin/completed_requests").mock(return_value=make_response([]))
    out = await adm.get_completed_requests()
    assert out == []


@respx.mock
@pytest.mark.asyncio
async def test_admin_get_completed_requests_filtered(adm: AnalyticsAdminAPI) -> None:
    route = respx.get(f"{ANALYTICS_BASE}/analytics/admin/completed_requests").mock(
        return_value=make_response({"requests": []})
    )
    await adm.get_completed_requests("ctx-9")
    call = route.calls.last
    assert "ctx-9" in str(call.request.url)


@respx.mock
@pytest.mark.asyncio
async def test_admin_restart_node(adm: AnalyticsAdminAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/analytics/node/restart").mock(return_value=empty_response(200))
    await adm.restart_node()
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_admin_restart_service(adm: AnalyticsAdminAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/analytics/cluster/restart").mock(return_value=empty_response(200))
    await adm.restart_service()
    assert route.called


# ── AnalyticsSettingsAPI ─────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_settings_get(stg: AnalyticsSettingsAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/analytics").mock(return_value=make_response({"numReplicas": 2}))
    out = await stg.get_settings()
    assert out.numReplicas == 2


@respx.mock
@pytest.mark.asyncio
async def test_settings_update_with_echo(stg: AnalyticsSettingsAPI) -> None:
    from cb_analytics_mcp.couchbase.models import AnalyticsSettings

    respx.post(f"{MGMT_BASE}/settings/analytics").mock(return_value=make_response({"numReplicas": 3}))
    out = await stg.update_settings(AnalyticsSettings(numReplicas=3))
    assert out.numReplicas == 3


@respx.mock
@pytest.mark.asyncio
async def test_settings_update_no_body(stg: AnalyticsSettingsAPI) -> None:
    """Couchbase sometimes responds with no body — should assume applied."""
    import httpx as _httpx

    from cb_analytics_mcp.couchbase.models import AnalyticsSettings

    respx.post(f"{MGMT_BASE}/settings/analytics").mock(return_value=_httpx.Response(200, content=b""))
    sent = AnalyticsSettings(numReplicas=1)
    out = await stg.update_settings(sent)
    assert out.numReplicas == 1


# ── AnalyticsConfigAPI ───────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_config_get_service_config(cfg: AnalyticsConfigAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/config/service").mock(
        return_value=make_response({"resultTtl": 3600})
    )
    out = await cfg.get_service_config()
    assert out.resultTtl == 3600


@respx.mock
@pytest.mark.asyncio
async def test_config_update_service_config(cfg: AnalyticsConfigAPI) -> None:
    respx.put(f"{ANALYTICS_BASE}/analytics/config/service").mock(
        return_value=make_response({"resultTtl": 7200})
    )
    out = await cfg.update_service_config(ServiceConfig(resultTtl=7200))
    assert out.resultTtl == 7200


# ── AnalyticsLinksAPI (more coverage) ────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_links_get_all_no_filter(lnk: AnalyticsLinksAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/link").mock(return_value=make_response([]))
    out = await lnk.get_all_links()
    assert out == []


@respx.mock
@pytest.mark.asyncio
async def test_links_get_all_filtered(lnk: AnalyticsLinksAPI) -> None:
    route = respx.get(f"{ANALYTICS_BASE}/analytics/link").mock(return_value=make_response({"links": []}))
    await lnk.get_all_links(dataverse="DV1", link_type="s3")
    call = route.calls.last
    assert "dataverse=DV1" in str(call.request.url)
    assert "type=s3" in str(call.request.url)


@respx.mock
@pytest.mark.asyncio
async def test_links_get_one_not_found(lnk: AnalyticsLinksAPI) -> None:
    """API returns empty list when link doesn't exist."""
    from cb_analytics_mcp.couchbase.exceptions import AnalyticsNotFoundError

    respx.get(f"{ANALYTICS_BASE}/analytics/link/none").mock(return_value=make_response([]))
    with pytest.raises(AnalyticsNotFoundError):
        await lnk.get_link("none")


@respx.mock
@pytest.mark.asyncio
async def test_links_get_one_list_form(lnk: AnalyticsLinksAPI) -> None:
    """API can return [{...}] for a single link."""
    respx.get(f"{ANALYTICS_BASE}/analytics/link/x").mock(
        return_value=make_response([{"name": "x", "type": "s3", "dataverse": "Default"}])
    )
    out = await lnk.get_link("x")
    assert out.name == "x"


@respx.mock
@pytest.mark.asyncio
async def test_links_create_with_dict(lnk: AnalyticsLinksAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/analytics/link").mock(return_value=empty_response(200))
    await lnk.create_link("myS3", "Default", {"type": "s3", "region": "us-east-1"})
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_links_create_with_typed_config(lnk: AnalyticsLinksAPI) -> None:
    """A typed S3LinkConfig should be converted via to_api_dict."""
    from pydantic import SecretStr

    from cb_analytics_mcp.couchbase.models import S3LinkConfig

    cfg_obj = S3LinkConfig(
        region="us-west-2",
        accessKeyId="AKIA",
        secretAccessKey=SecretStr("s"),
    )
    route = respx.post(f"{ANALYTICS_BASE}/analytics/link").mock(return_value=empty_response(200))
    await lnk.create_link("myS3", "Default", cfg_obj)
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_links_update_with_dict(lnk: AnalyticsLinksAPI) -> None:
    route = respx.put(f"{ANALYTICS_BASE}/analytics/link/myS3").mock(return_value=empty_response(200))
    await lnk.update_link("myS3", {"type": "s3"})
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_links_config_unsupported_type(lnk: AnalyticsLinksAPI) -> None:
    """A plain non-dict, non-typed value should raise TypeError."""
    with pytest.raises(TypeError, match="Unsupported"):
        await lnk.create_link("x", "Default", 12345)  # type: ignore[arg-type]

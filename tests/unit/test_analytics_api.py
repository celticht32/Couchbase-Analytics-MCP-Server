# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Analytics Service, Admin, Config, Settings, Links, and Library APIs."""

from __future__ import annotations

import pytest
import respx
import httpx

from cb_analytics.api.analytics import (
    AnalyticsAdminAPI, AnalyticsConfigAPI, AnalyticsLibraryAPI,
    AnalyticsLinksAPI, AnalyticsServiceAPI, AnalyticsSettingsAPI,
)
from cb_analytics.exceptions import AnalyticsLibraryError, AnalyticsQueryError
from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AnalyticsQueryRequest, AnalyticsSettings,
    ScanConsistency, ServiceConfig,
)
from tests.conftest import ANALYTICS_BASE, MGMT_BASE, make_response, empty_response

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

# ── AnalyticsServiceAPI.execute ───────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_execute_success(svc: AnalyticsServiceAPI) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "r1", "status": "success",
            "results": [{"n": 1}],
            "metrics": {"elapsedTime": "50ms", "executionTime": "40ms",
                        "resultCount": 1, "resultSize": 8, "warningCount": 0, "errorCount": 0},
            "warnings": [], "errors": [],
        })
    )
    result = await svc.execute(AnalyticsQueryRequest(statement="SELECT 1 AS n"))
    assert result.status == "success"
    assert result.results == [{"n": 1}]
    assert result.metrics is not None
    assert result.metrics.resultCount == 1


@respx.mock
@pytest.mark.asyncio
async def test_execute_with_positional_params(svc: AnalyticsServiceAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"requestID": "r2", "status": "success", "results": [],
                                    "metrics": {}, "warnings": [], "errors": []})
    )
    await svc.execute(AnalyticsQueryRequest(statement="SELECT * FROM ds WHERE id = $1", args=[42]))
    body = route.calls[0].request.content
    import json
    payload = json.loads(body)
    assert payload["args"] == [42]


@respx.mock
@pytest.mark.asyncio
async def test_execute_named_params_serialized_correctly(svc: AnalyticsServiceAPI) -> None:
    """Named params must become $name keys in the JSON payload."""
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"requestID": "r3", "status": "success", "results": [],
                                    "metrics": {}, "warnings": [], "errors": []})
    )
    await svc.execute(AnalyticsQueryRequest(statement="SELECT * FROM ds WHERE name = $name",
                                             named_args={"name": "Alice"}))
    import json
    payload = json.loads(route.calls[0].request.content)
    assert "$name" in payload
    assert payload["$name"] == "Alice"


@respx.mock
@pytest.mark.asyncio
async def test_execute_raises_query_error(svc: AnalyticsServiceAPI) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({
            "requestID": "rerr", "status": "fatal", "results": [],
            "metrics": {"errorCount": 1}, "warnings": [],
            "errors": [{"code": 24000, "msg": "Syntax error", "line": 1, "column": 8}],
        })
    )
    with pytest.raises(AnalyticsQueryError) as exc:
        await svc.execute(AnalyticsQueryRequest(statement="BAD SQL"))
    err = exc.value
    assert err.code == 24000
    assert err.line == 1
    assert err.column == 8


@respx.mock
@pytest.mark.asyncio
async def test_execute_with_scan_consistency(svc: AnalyticsServiceAPI) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"status": "success", "results": [],
                                    "metrics": {}, "warnings": [], "errors": []})
    )
    await svc.execute(AnalyticsQueryRequest(statement="SELECT 1",
                                             scan_consistency=ScanConsistency.REQUEST_PLUS))
    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["scan_consistency"] == "request_plus"


@respx.mock
@pytest.mark.asyncio
async def test_execute_readonly_get(svc: AnalyticsServiceAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"status": "success", "results": [{"val": 42}],
                                    "metrics": {}, "warnings": [], "errors": []})
    )
    result = await svc.execute_readonly(AnalyticsQueryRequest(statement="SELECT 42 AS val"))
    assert result.results == [{"val": 42}]


# ── AnalyticsAdminAPI ─────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_active_requests(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=make_response([{"clientContextID": "ctx-1", "state": "running"}])
    )
    reqs = await adm.get_active_requests()
    assert len(reqs) == 1
    assert reqs[0].state == "running"


@respx.mock
@pytest.mark.asyncio
async def test_cancel_request(adm: AnalyticsAdminAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=empty_response(200)
    )
    await adm.cancel_request("ctx-123")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_get_completed_requests(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/completed_requests").mock(
        return_value=make_response([{"clientContextID": "done-1", "state": "success", "resultCount": 5}])
    )
    reqs = await adm.get_completed_requests()
    assert reqs[0].resultCount == 5


@respx.mock
@pytest.mark.asyncio
async def test_get_service_status(adm: AnalyticsAdminAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/service").mock(
        return_value=make_response({"state": "ACTIVE", "ccRevLag": 0, "authorizedNodes": ["n1"]})
    )
    status = await adm.get_service_status()
    assert status.state == "ACTIVE"


@respx.mock
@pytest.mark.asyncio
async def test_get_ingestion_status_list_format(adm: AnalyticsAdminAPI) -> None:
    """Ingestion status may return a list — verify IngestionStatus.from_raw handles it."""
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/ingestion").mock(
        return_value=make_response([{"name": "Local", "state": "CONNECTED", "datasetStates": []}])
    )
    result = await adm.get_ingestion_status()
    assert len(result.links) == 1
    assert result.links[0].name == "Local"


@respx.mock
@pytest.mark.asyncio
async def test_get_ingestion_status_dict_format(adm: AnalyticsAdminAPI) -> None:
    """Ingestion status may also return {links: [...]} dict format."""
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/ingestion").mock(
        return_value=make_response({"links": [{"name": "S3", "state": "CONNECTED"}]})
    )
    result = await adm.get_ingestion_status()
    assert len(result.links) == 1


# ── AnalyticsConfigAPI ────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_service_config(cfg: AnalyticsConfigAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({"resultTtl": 3600, "compilerParallelism": 0})
    )
    result = await cfg.get_service_config()
    assert result.resultTtl == 3600
    # 0 is a valid value — must be preserved
    assert result.compilerParallelism == 0


@respx.mock
@pytest.mark.asyncio
async def test_update_service_config_preserves_zero(cfg: AnalyticsConfigAPI) -> None:
    """BUG FIX: model_dump with if v is not None would strip 0 — to_api_dict uses exclude_unset."""
    route = respx.put(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({"compilerParallelism": 0})
    )
    config = ServiceConfig(compilerParallelism=0)
    await cfg.update_service_config(config)
    import json
    payload = json.loads(route.calls[0].request.content)
    assert "compilerParallelism" in payload
    assert payload["compilerParallelism"] == 0


@respx.mock
@pytest.mark.asyncio
async def test_update_service_config_preserves_false(cfg: AnalyticsConfigAPI) -> None:
    """BUG FIX: False boolean values must not be stripped."""
    route = respx.put(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({})
    )
    # Use a field that could be bool in extended config
    config = ServiceConfig()
    config.model_fields_set.add("resultTtl")
    await cfg.update_service_config(ServiceConfig(resultTtl=0))
    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload.get("resultTtl") == 0


@respx.mock
@pytest.mark.asyncio
async def test_get_node_config(cfg: AnalyticsConfigAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/config/node").mock(
        return_value=make_response({"storageBuffercacheSize": 536870912})
    )
    result = await cfg.get_node_config()
    assert result.storageBuffercacheSize == 536870912


# ── AnalyticsSettingsAPI ──────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_analytics_settings(stg: AnalyticsSettingsAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/analytics").mock(return_value=make_response({"numReplicas": 1}))
    result = await stg.get_settings()
    assert result.numReplicas == 1


@respx.mock
@pytest.mark.asyncio
async def test_update_analytics_settings_preserves_zero(stg: AnalyticsSettingsAPI) -> None:
    """BUG FIX: numReplicas=0 must not be stripped."""
    route = respx.post(f"{MGMT_BASE}/settings/analytics").mock(
        return_value=make_response({"numReplicas": 0})
    )
    await stg.update_settings(AnalyticsSettings(numReplicas=0))
    import urllib.parse
    # data is form-encoded
    body = route.calls[0].request.content.decode()
    params = dict(urllib.parse.parse_qsl(body))
    assert params.get("numReplicas") == "0"


# ── AnalyticsLinksAPI ─────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_create_link_with_s3_config(lnk: AnalyticsLinksAPI) -> None:
    from cb_analytics.models import S3LinkConfig
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/link/myS3").mock(
        return_value=make_response({"status": "created"})
    )
    config = S3LinkConfig(region="us-east-1", accessKeyId="AKID", secretAccessKey="SECRET")
    await lnk.create_link("myS3", "Default", config)
    import json
    payload = json.loads(route.calls[0].request.content)
    # Secret must be present but should be the actual value at serialization point
    assert payload["secretAccessKey"] == "SECRET"
    assert payload["type"] == "s3"


@respx.mock
@pytest.mark.asyncio
async def test_get_all_links_no_filter(lnk: AnalyticsLinksAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/link").mock(
        return_value=make_response([{"name": "Local", "type": "couchbase"}])
    )
    links = await lnk.get_all_links()
    assert len(links) == 1


@respx.mock
@pytest.mark.asyncio
async def test_delete_link(lnk: AnalyticsLinksAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/api/v1/link/myLink").mock(return_value=empty_response(200))
    await lnk.delete_link("myLink")
    assert route.called


# ── AnalyticsLibraryAPI ───────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_list_libraries(lib: AnalyticsLibraryAPI) -> None:
    respx.get(f"{ANALYTICS_BASE}/analytics/library").mock(
        return_value=make_response([{"scope": "Default", "name": "mylib", "functions": []}])
    )
    libs = await lib.list_libraries()
    assert len(libs) == 1
    assert libs[0].name == "mylib"


@respx.mock
@pytest.mark.asyncio
async def test_delete_library(lib: AnalyticsLibraryAPI) -> None:
    route = respx.delete(f"{ANALYTICS_BASE}/analytics/library/Default/mylib").mock(
        return_value=empty_response(200)
    )
    await lib.delete_library("Default", "mylib")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_upload_library_403_raises_library_error(lib: AnalyticsLibraryAPI) -> None:
    """BUG FIX: 403 from remote upload gives AnalyticsLibraryError with clear message."""
    respx.put(f"{ANALYTICS_BASE}/analytics/library/Default/mylib").mock(
        return_value=httpx.Response(403, text="Upload from non-local origin is not allowed")
    )
    with pytest.raises(AnalyticsLibraryError) as exc:
        await lib.upload_library("Default", "mylib", "python", b"fake-data")
    assert "local" in str(exc.value).lower() or "403" in str(exc.value)


# ── Regression tests for v1.1.0 bug fixes ─────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_execute_raises_on_204_empty_response(svc: AnalyticsServiceAPI) -> None:
    """BUG FIX: execute() must raise AnalyticsQueryError if server returns 204/None."""
    import httpx
    from cb_analytics.exceptions import AnalyticsQueryError
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=httpx.Response(204)
    )
    with pytest.raises(AnalyticsQueryError, match="empty response"):
        await svc.execute(AnalyticsQueryRequest(statement="SELECT 1"))

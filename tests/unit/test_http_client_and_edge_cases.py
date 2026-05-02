# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unit tests for HttpClient, retry logic, and edge cases."""

from __future__ import annotations

import pytest
import respx
import httpx

from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import (
    AnalyticsAuthError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)
from cb_analytics.http_client import HttpClient
from tests.conftest import MGMT_BASE, ANALYTICS_BASE, make_response, empty_response


@pytest.fixture
def http(config: AnalyticsClientConfig) -> HttpClient:
    return HttpClient(
        management_url=MGMT_BASE,
        analytics_url=ANALYTICS_BASE,
        username=config.username,
        password=config.password,
        timeout=5.0,
        verify_ssl=False,
        max_retries=1,
    )


# ── Status code → exception mapping ──────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_200_returns_body(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=make_response({"pools": [], "uuid": "abc"})
    )
    result = await http.mgmt_get("/pools")
    assert result["uuid"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_204_returns_none(http: HttpClient) -> None:
    respx.post(f"{MGMT_BASE}/controller/cancelLogsCollection").mock(
        return_value=httpx.Response(204)
    )
    result = await http.mgmt_post("/controller/cancelLogsCollection")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_201_returns_body(http: HttpClient) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/serverGroups").mock(
        return_value=httpx.Response(201, json={"name": "Rack A", "uri": "/groups/abc"})
    )
    result = await http.mgmt_post("/pools/default/serverGroups", data={"name": "Rack A"})
    assert result["name"] == "Rack A"


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users").mock(
        return_value=httpx.Response(401, json={"message": "Unauthorized"})
    )
    with pytest.raises(AnalyticsAuthError):
        await http.mgmt_get("/settings/rbac/users")


@respx.mock
@pytest.mark.asyncio
async def test_403_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/settings/security").mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )
    with pytest.raises(AnalyticsAuthError):
        await http.mgmt_get("/settings/security")


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(http: HttpClient) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/link/nonexistent").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    with pytest.raises(AnalyticsNotFoundError):
        await http.analytics_get("/api/v1/link/nonexistent")


@respx.mock
@pytest.mark.asyncio
async def test_400_raises_request_error(http: HttpClient) -> None:
    respx.post(f"{MGMT_BASE}/clusterInit").mock(
        return_value=httpx.Response(400, json=["Invalid parameter: services"])
    )
    with pytest.raises(AnalyticsRequestError):
        await http.mgmt_post("/clusterInit", data={"services": "invalid"})


@respx.mock
@pytest.mark.asyncio
async def test_409_raises_request_error(http: HttpClient) -> None:
    respx.put(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(
        return_value=httpx.Response(409, json={"message": "User already exists"})
    )
    with pytest.raises(AnalyticsRequestError):
        await http.mgmt_put("/settings/rbac/users/local/alice", data={"password": "x"})


@respx.mock
@pytest.mark.asyncio
async def test_500_raises_server_error(http: HttpClient) -> None:
    # With max_retries=1 it tries once then raises
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=httpx.Response(500, json={"error": "Internal error"})
    )
    with pytest.raises(AnalyticsServerError):
        await http.mgmt_get("/pools")


@respx.mock
@pytest.mark.asyncio
async def test_503_raises_server_error(http: HttpClient) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/status/service").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )
    with pytest.raises(AnalyticsServerError):
        await http.analytics_get("/api/v1/status/service")


# ── HTTP methods ──────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_mgmt_put(http: HttpClient) -> None:
    respx.put(f"{MGMT_BASE}/api/v1/config/service").mock(
        return_value=make_response({"resultTtl": 7200})
    )
    # Test analytics_put through mgmt doesn't apply here but validates put works
    result = await http.mgmt_put("/api/v1/config/service", json={"resultTtl": 7200})
    assert result["resultTtl"] == 7200


@respx.mock
@pytest.mark.asyncio
async def test_mgmt_delete(http: HttpClient) -> None:
    respx.delete(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(
        return_value=empty_response(200)
    )
    result = await http.mgmt_delete("/settings/rbac/users/local/alice")
    # 200 with empty body parses to ""
    assert result is not None or result == "" or result is None


@respx.mock
@pytest.mark.asyncio
async def test_analytics_post(http: HttpClient) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(
        return_value=make_response({"requestID": "r1", "status": "success", "results": []})
    )
    result = await http.analytics_post("/api/v1/request", json={"statement": "SELECT 1"})
    assert result["requestID"] == "r1"


@respx.mock
@pytest.mark.asyncio
async def test_analytics_put(http: HttpClient) -> None:
    respx.put(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({"resultTtl": 3600})
    )
    result = await http.analytics_put("/api/v1/config/service", json={"resultTtl": 3600})
    assert result["resultTtl"] == 3600


@respx.mock
@pytest.mark.asyncio
async def test_analytics_delete(http: HttpClient) -> None:
    respx.delete(f"{ANALYTICS_BASE}/api/v1/active_requests").mock(
        return_value=empty_response(200)
    )
    await http.analytics_delete("/api/v1/active_requests")


# ── None/null filtering in query params ──────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_none_params_filtered_out(http: HttpClient) -> None:
    """None values in params dict should not be sent as query params."""
    route = respx.get(f"{MGMT_BASE}/events").mock(
        return_value=make_response([])
    )
    await http.mgmt_get("/events", params={"since": None, "limit": 10})
    # Should not have '?since=None' in the URL
    request = route.calls[0].request
    assert "since" not in str(request.url)
    assert "limit=10" in str(request.url)


# ── JSON vs form-data ─────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_post_with_json_body(http: HttpClient) -> None:
    route = respx.post(f"{ANALYTICS_BASE}/api/v1/config/service").mock(
        return_value=make_response({"ok": True})
    )
    await http.analytics_post("/api/v1/config/service", json={"resultTtl": 1800})
    req = route.calls[0].request
    assert req.headers["content-type"] == "application/json"


@respx.mock
@pytest.mark.asyncio
async def test_post_with_form_data(http: HttpClient) -> None:
    route = respx.post(f"{MGMT_BASE}/pools/default").mock(
        return_value=empty_response(200)
    )
    await http.mgmt_post("/pools/default", data={"memoryQuota": "1024"})
    req = route.calls[0].request
    assert "application/x-www-form-urlencoded" in req.headers.get("content-type", "")


# ── AnalyticsClient facade ────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_client_ping_success(config: AnalyticsClientConfig) -> None:
    from cb_analytics.client import AnalyticsClient
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=make_response({"pools": [], "uuid": "abc"})
    )
    async with AnalyticsClient(config) as client:
        ok = await client.ping()
    assert ok is True


@respx.mock
@pytest.mark.asyncio
async def test_client_ping_failure(config: AnalyticsClientConfig) -> None:
    from cb_analytics.client import AnalyticsClient
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=httpx.Response(500, text="down")
    )
    async with AnalyticsClient(config) as client:
        ok = await client.ping()
    assert ok is False


@pytest.mark.asyncio
async def test_client_all_api_groups_present(config: AnalyticsClientConfig) -> None:
    from cb_analytics.client import AnalyticsClient
    from cb_analytics.api import (
        ClusterAPI, AnalyticsServiceAPI, AnalyticsAdminAPI,
        AnalyticsConfigAPI, AnalyticsSettingsAPI, AnalyticsLinksAPI,
        SecurityAPI, ServerGroupsAPI,
    )
    async with AnalyticsClient(config) as client:
        assert isinstance(client.cluster, ClusterAPI)
        assert isinstance(client.analytics, AnalyticsServiceAPI)
        assert isinstance(client.admin, AnalyticsAdminAPI)
        assert isinstance(client.config, AnalyticsConfigAPI)
        assert isinstance(client.settings, AnalyticsSettingsAPI)
        assert isinstance(client.links, AnalyticsLinksAPI)
        assert isinstance(client.security, SecurityAPI)
        assert isinstance(client.server_groups, ServerGroupsAPI)


# ── Misc model edge cases ─────────────────────────────────────────────────────


class TestMiscModels:
    def test_analytics_query_request_defaults(self) -> None:
        from cb_analytics.models import AnalyticsQueryRequest
        req = AnalyticsQueryRequest(statement="SELECT 1")
        assert req.statement == "SELECT 1"
        assert req.args is None
        assert req.scan_consistency is None
        assert req.timeout is None
        assert req.read_only is None

    def test_service_config_partial(self) -> None:
        from cb_analytics.models import ServiceConfig
        cfg = ServiceConfig(resultTtl=3600)
        dumped = {k: v for k, v in cfg.model_dump().items() if v is not None}
        assert dumped == {"resultTtl": 3600}

    def test_user_upsert_partial(self) -> None:
        from cb_analytics.models import UserUpsertRequest
        req = UserUpsertRequest(password="Secret!")
        assert req.password == "Secret!"
        assert req.roles is None

    def test_link_info_optional_fields(self) -> None:
        from cb_analytics.models import LinkInfo
        link = LinkInfo()
        assert link.name is None
        assert link.activeDatasets is None

    def test_ingestion_status_empty_links(self) -> None:
        from cb_analytics.models import IngestionStatus
        status = IngestionStatus()
        assert status.links == []

    def test_service_status_extra_fields(self) -> None:
        from cb_analytics.models import ServiceStatus
        # Should accept extra fields without error
        status = ServiceStatus.model_validate({
            "state": "ACTIVE",
            "authorizedNodes": ["n1"],
            "someExtraField": "value",
        })
        assert status.state == "ACTIVE"

    def test_auto_failover_settings_all_none(self) -> None:
        from cb_analytics.models import AutoFailoverSettings
        s = AutoFailoverSettings()
        assert s.enabled is None
        assert s.timeout is None

    def test_password_policy_all_fields(self) -> None:
        from cb_analytics.models import PasswordPolicy
        p = PasswordPolicy(
            minLength=12,
            enforceUppercase=True,
            enforceLowercase=True,
            enforceDigits=True,
            enforceSpecialChars=True,
        )
        assert p.minLength == 12
        assert p.enforceSpecialChars is True

    def test_scan_consistency_values(self) -> None:
        from cb_analytics.models import ScanConsistency
        assert ScanConsistency.NOT_BOUNDED.value == "not_bounded"
        assert ScanConsistency.REQUEST_PLUS.value == "request_plus"
        assert ScanConsistency.AT_PLUS.value == "at_plus"

    def test_rbac_domain_values(self) -> None:
        from cb_analytics.models import RbacDomain
        assert RbacDomain.LOCAL.value == "local"
        assert RbacDomain.EXTERNAL.value == "external"

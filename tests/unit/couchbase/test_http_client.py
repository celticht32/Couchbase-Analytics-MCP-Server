# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the HTTP client."""

from __future__ import annotations

import httpx
import pytest
import respx

from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)
from cb_analytics_mcp.couchbase.http_client import HttpClient
from tests.conftest import ANALYTICS_BASE, MGMT_BASE, empty_response, make_response


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(
        management_url=MGMT_BASE,
        analytics_url=ANALYTICS_BASE,
        username="user",
        password="pass",
        timeout=2.0,
        verify_ssl=False,
        max_retries=2,
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_mgmt_success(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=make_response({"version": "7.6"}))
    r = await http.get_mgmt("/pools")
    assert r.status_code == 200
    assert r.json() == {"version": "7.6"}
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_post_analytics_success(http: HttpClient) -> None:
    respx.post(f"{ANALYTICS_BASE}/api/v1/request").mock(return_value=make_response({"status": "success"}))
    r = await http.post_analytics("/api/v1/request", json={"statement": "SELECT 1"})
    assert r.json()["status"] == "success"
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=httpx.Response(401, text="Unauthorized"))
    with pytest.raises(AnalyticsAuthError):
        await http.get_mgmt("/pools")
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_403_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=httpx.Response(403, text="Forbidden"))
    with pytest.raises(AnalyticsAuthError):
        await http.get_mgmt("/pools")
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/x").mock(return_value=httpx.Response(404, text="Not found"))
    with pytest.raises(AnalyticsNotFoundError):
        await http.get_mgmt("/x")
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_400_raises_request_error(http: HttpClient) -> None:
    respx.put(f"{MGMT_BASE}/x").mock(return_value=httpx.Response(400, text="Bad"))
    with pytest.raises(AnalyticsRequestError) as excinfo:
        await http.put_mgmt("/x")
    assert excinfo.value.status_code == 400
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_500_retries_then_raises(http: HttpClient) -> None:
    route = respx.get(f"{MGMT_BASE}/x").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(AnalyticsServerError):
        await http.get_mgmt("/x")
    # max_retries=2 means it tries twice
    assert route.call_count == 2
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_connection_error_raises_typed(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/x").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(AnalyticsConnectionError):
        await http.get_mgmt("/x")
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_204_no_content(http: HttpClient) -> None:
    respx.delete(f"{MGMT_BASE}/x").mock(return_value=empty_response(204))
    r = await http.delete_mgmt("/x")
    assert r.status_code == 204
    await http.close()


@respx.mock
@pytest.mark.asyncio
async def test_500_then_200_succeeds_on_retry(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/x").mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            make_response({"ok": True}),
        ]
    )
    r = await http.get_mgmt("/x")
    assert r.json() == {"ok": True}
    await http.close()

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Capella Analytics Management API client."""

from __future__ import annotations


import httpx
import pytest
import respx

from cb_analytics.capella.client import CAPELLA_BASE_URL, CapellaAnalyticsClient, CapellaConfig
from cb_analytics.exceptions import AnalyticsAuthError, AnalyticsNotFoundError


@pytest.fixture
def capella_config() -> CapellaConfig:
    return CapellaConfig(api_key_secret="test-bearer-token")


@pytest.fixture
async def capella(capella_config: CapellaConfig) -> CapellaAnalyticsClient:  # type: ignore[misc]
    async with CapellaAnalyticsClient(capella_config) as c:
        yield c


def make_resp(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


@respx.mock
@pytest.mark.asyncio
async def test_list_organizations(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations").mock(
        return_value=make_resp({"data": [{"id": "org-1", "name": "My Org"}]})
    )
    orgs = await capella.list_organizations()
    assert len(orgs) == 1
    assert orgs[0]["id"] == "org-1"


@respx.mock
@pytest.mark.asyncio
async def test_list_clusters(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters").mock(
        return_value=make_resp({"data": [{"id": "cluster-1", "name": "My Analytics"}]})
    )
    clusters = await capella.list_clusters("org1", "proj1")
    assert clusters[0]["id"] == "cluster-1"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters/cl1").mock(
        return_value=make_resp({"id": "cl1", "status": "healthy"})
    )
    cluster = await capella.get_cluster("org1", "proj1", "cl1")
    assert cluster["id"] == "cl1"


@respx.mock
@pytest.mark.asyncio
async def test_create_cluster(capella: CapellaAnalyticsClient) -> None:
    route = respx.post(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters").mock(
        return_value=make_resp({"id": "new-cl"}, status=201)
    )
    result = await capella.create_cluster("org1", "proj1", {"name": "new", "cloudProvider": "aws"})
    assert route.called
    assert result["id"] == "new-cl"


@respx.mock
@pytest.mark.asyncio
async def test_delete_cluster(capella: CapellaAnalyticsClient) -> None:
    route = respx.delete(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters/cl1").mock(
        return_value=httpx.Response(204)
    )
    await capella.delete_cluster("org1", "proj1", "cl1")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_list_backups(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters/cl1/backups").mock(
        return_value=make_resp({"data": [{"id": "bk-1", "status": "completed"}]})
    )
    backups = await capella.list_backups("org1", "proj1", "cl1")
    assert backups[0]["id"] == "bk-1"


@respx.mock
@pytest.mark.asyncio
async def test_create_backup(capella: CapellaAnalyticsClient) -> None:
    route = respx.post(f"{CAPELLA_BASE_URL}/v4/organizations/org1/projects/proj1/analyticsClusters/cl1/backups").mock(
        return_value=make_resp({"id": "bk-2"}, status=201)
    )
    await capella.create_backup("org1", "proj1", "cl1")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations").mock(return_value=httpx.Response(401))
    with pytest.raises(AnalyticsAuthError) as exc:
        await capella.list_organizations()
    assert "401" in str(exc.value)


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(capella: CapellaAnalyticsClient) -> None:
    respx.get(f"{CAPELLA_BASE_URL}/v4/organizations/bad/projects/bad/analyticsClusters/nope").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(AnalyticsNotFoundError):
        await capella.get_cluster("bad", "bad", "nope")


def test_capella_config_secret_not_in_repr() -> None:
    config = CapellaConfig(api_key_secret="my-secret-token")
    assert "my-secret-token" not in repr(config)
    assert config.api_key_secret.get_secret_value() == "my-secret-token"


def test_bearer_token_in_auth_header() -> None:
    """Verify the client sets Authorization: Bearer header (not Basic)."""
    config = CapellaConfig(api_key_secret="my-token")
    client = CapellaAnalyticsClient(config)
    headers = dict(client._client.headers)
    assert "bearer my-token" in headers.get("authorization", "").lower()

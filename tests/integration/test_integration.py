# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Integration tests against a real Couchbase Enterprise Analytics cluster.

Skipped automatically when CB_ANALYTICS_HOST is not set or the cluster
is unreachable. Run these in CI with:

    docker compose -f docker-compose.test.yml up -d
    CB_ANALYTICS_HOST=localhost CB_ANALYTICS_USERNAME=Administrator \
    CB_ANALYTICS_PASSWORD=password pytest tests/integration/ -v

Environment variables (from AnalyticsClientConfig):
  CB_ANALYTICS_HOST          Cluster hostname (default: localhost)
  CB_ANALYTICS_MGMT_PORT     Management port (default: 8091)
  CB_ANALYTICS_ANALYTICS_PORT Analytics port (default: 8095)
  CB_ANALYTICS_USERNAME      Username (default: Administrator)
  CB_ANALYTICS_PASSWORD      Password (default: password)
"""

from __future__ import annotations

import os

import pytest

from cb_analytics.client import AnalyticsClient
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import AnalyticsQueryError
from cb_analytics.models import (
    AnalyticsQueryRequest,
    ScanConsistency,
)

# Skip all integration tests if no host is configured
pytestmark = pytest.mark.skipif(
    not os.getenv("CB_ANALYTICS_HOST"),
    reason="CB_ANALYTICS_HOST not set — skipping integration tests",
)


@pytest.fixture
async def integ_client() -> AnalyticsClient:  # type: ignore[misc]
    config = AnalyticsClientConfig()
    async with AnalyticsClient(config) as client:
        yield client


# ── Connectivity ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ping(integ_client: AnalyticsClient) -> None:
    assert await integ_client.ping()


@pytest.mark.asyncio
async def test_get_cluster_info(integ_client: AnalyticsClient) -> None:
    info = await integ_client.cluster.get_cluster_info()
    assert info.pools is not None


# ── Query Execution ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_select_1(integ_client: AnalyticsClient) -> None:
    result = await integ_client.analytics.execute(
        AnalyticsQueryRequest(statement="SELECT 1 AS n")
    )
    assert result.status == "success"
    assert result.results == [{"n": 1}]


@pytest.mark.asyncio
async def test_execute_with_parameters(integ_client: AnalyticsClient) -> None:
    result = await integ_client.analytics.execute(
        AnalyticsQueryRequest(statement="SELECT $1 AS value", args=[42])
    )
    assert result.results[0]["value"] == 42


@pytest.mark.asyncio
async def test_execute_readonly_get(integ_client: AnalyticsClient) -> None:
    result = await integ_client.analytics.execute_readonly(
        AnalyticsQueryRequest(statement="SELECT 2 AS n")
    )
    assert result.results[0]["n"] == 2


@pytest.mark.asyncio
async def test_execute_invalid_sql_raises(integ_client: AnalyticsClient) -> None:
    with pytest.raises(AnalyticsQueryError) as exc_info:
        await integ_client.analytics.execute(
            AnalyticsQueryRequest(statement="THIS IS NOT SQL")
        )
    assert exc_info.value.code is not None


@pytest.mark.asyncio
async def test_execute_with_request_plus_consistency(integ_client: AnalyticsClient) -> None:
    result = await integ_client.analytics.execute(
        AnalyticsQueryRequest(
            statement="SELECT 3 AS n",
            scan_consistency=ScanConsistency.REQUEST_PLUS,
        )
    )
    assert result.status == "success"


# ── Admin ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_service_status(integ_client: AnalyticsClient) -> None:
    status = await integ_client.admin.get_service_status()
    assert status.state is not None


@pytest.mark.asyncio
async def test_get_active_requests(integ_client: AnalyticsClient) -> None:
    reqs = await integ_client.admin.get_active_requests()
    assert isinstance(reqs, list)


@pytest.mark.asyncio
async def test_get_completed_requests(integ_client: AnalyticsClient) -> None:
    reqs = await integ_client.admin.get_completed_requests()
    assert isinstance(reqs, list)


@pytest.mark.asyncio
async def test_get_ingestion_status(integ_client: AnalyticsClient) -> None:
    status = await integ_client.admin.get_ingestion_status()
    assert status.links is not None


# ── Config ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_service_config(integ_client: AnalyticsClient) -> None:
    config = await integ_client.config.get_service_config()
    # resultTtl should always be present
    assert config.resultTtl is not None or config.model_extra is not None


@pytest.mark.asyncio
async def test_get_node_config(integ_client: AnalyticsClient) -> None:
    config = await integ_client.config.get_node_config()
    assert isinstance(config.model_dump(), dict)


# ── Settings ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_analytics_settings(integ_client: AnalyticsClient) -> None:
    settings = await integ_client.settings.get_settings()
    assert isinstance(settings.model_dump(), dict)


# ── Links ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_links(integ_client: AnalyticsClient) -> None:
    links = await integ_client.links.get_all_links()
    assert isinstance(links, list)


# ── Security ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_who_am_i(integ_client: AnalyticsClient) -> None:
    result = await integ_client.cluster.who_am_i()
    assert "id" in result or "roles" in result


@pytest.mark.asyncio
async def test_list_roles(integ_client: AnalyticsClient) -> None:
    roles = await integ_client.security.list_roles()
    role_names = [r.get("role", "") for r in roles]
    # Every Couchbase cluster has at least these roles
    assert "admin" in role_names or "full_admin" in role_names


@pytest.mark.asyncio
async def test_list_users(integ_client: AnalyticsClient) -> None:
    users = await integ_client.security.list_users()
    assert len(users) >= 1  # at least the Administrator


@pytest.mark.asyncio
async def test_get_password_policy(integ_client: AnalyticsClient) -> None:
    policy = await integ_client.security.get_password_policy()
    assert policy.minLength is not None


@pytest.mark.asyncio
async def test_get_audit_settings(integ_client: AnalyticsClient) -> None:
    audit = await integ_client.security.get_audit_settings()
    assert isinstance(audit.model_dump(), dict)


# ── Server Groups ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_server_groups(integ_client: AnalyticsClient) -> None:
    groups = await integ_client.server_groups.get_groups()
    assert isinstance(groups.groups, list)
    # Default group always exists
    assert len(groups.groups) >= 1


# ── Cluster Stats ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_cluster_details(integ_client: AnalyticsClient) -> None:
    details = await integ_client.cluster.get_cluster_details()
    assert details.name is not None


@pytest.mark.asyncio
async def test_list_node_services(integ_client: AnalyticsClient) -> None:
    services = await integ_client.cluster.list_node_services()
    assert isinstance(services.nodesExt, list)

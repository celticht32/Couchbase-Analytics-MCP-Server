# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Exercise the register() closures for every tool group.

The _impl functions are unit-tested elsewhere; this file confirms that the
@mcp.tool() wrappers (a) are registered with the right names and (b) round-
trip arguments through call_tool_observed cleanly. We use a FakePool so no
real Couchbase is needed.
"""

from __future__ import annotations

from typing import Any

import pytest
from prometheus_client import CollectorRegistry

from cb_analytics_mcp.couchbase.models import (
    AnalyticsMetrics,
    AnalyticsQueryResponse,
    AnalyticsSettings,
    AutoFailoverSettings,
    ClusterDetails,
    ClusterInfo,
    GroupInfo,
    IngestionStatus,
    LibraryInfo,
    LinkInfo,
    RebalanceProgress,
    ServiceConfig,
    ServiceStatus,
    UserInfo,
)
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.tools import (
    admin,
    capella,
    cluster,
    config_tools,
    libraries,
    links,
    meta,
    query,
    schema,
    security,
)
from tests.unit.mcp.conftest import FakePool

# ── Test harness ─────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pool() -> FakePool:
    pool = FakePool(names=["default"])
    pool.enable_capella()
    return pool


@pytest.fixture
def mcp_with_tools(fake_pool: FakePool):  # type: ignore[no-untyped-def]
    """Build a fresh FastMCP and register every tool group with the FakePool."""
    from mcp.server.fastmcp import FastMCP

    from cb_analytics_mcp.cache import ResultCache

    fresh: FastMCP[Any] = FastMCP(name="test-mcp")
    audit = AuditLog(enabled=False)
    metrics = Metrics(registry=CollectorRegistry())
    cache = ResultCache()
    meta.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    schema.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    query.register(fresh, fake_pool, audit, metrics, cache=cache)  # type: ignore[arg-type]
    admin.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    config_tools.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    links.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    libraries.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    security.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    cluster.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    capella.register(fresh, fake_pool, audit, metrics)  # type: ignore[arg-type]
    return fresh


def _qr(rows: list[Any]) -> AnalyticsQueryResponse:
    return AnalyticsQueryResponse(
        requestID="r1",
        status="success",
        results=rows,
        metrics=AnalyticsMetrics(resultCount=len(rows)),
    )


async def _call(mcp: Any, tool_name: str, /, **kwargs: Any) -> dict[str, Any]:
    """Helper: call a tool on the MCP instance and return the structured content."""
    result = await mcp.call_tool(tool_name, kwargs)
    # FastMCP returns (content_list, structured_dict) since recent versions
    if isinstance(result, tuple) and len(result) == 2:
        return result[1]  # type: ignore[no-any-return]
    return result  # type: ignore[no-any-return]


# ── Meta ─────────────────────────────────────────────────────────────────────


class TestMetaRegistered:
    @pytest.mark.asyncio
    async def test_list_clusters(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "list_clusters")
        assert out["ok"] is True
        assert out["data"]["clusters"] == ["default"]

    @pytest.mark.asyncio
    async def test_get_capabilities(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "get_capabilities")
        assert out["ok"] is True
        assert out["data"]["name"] == "cb-analytics-mcp"


# ── Schema ───────────────────────────────────────────────────────────────────


class TestSchemaRegistered:
    @pytest.mark.asyncio
    async def test_list_dataverses(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute.return_value = _qr(["Default"])
        out = await _call(mcp_with_tools, "list_dataverses")
        assert out["ok"] is True
        assert out["data"] == ["Default"]

    @pytest.mark.asyncio
    async def test_list_datasets(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute.return_value = _qr([])
        out = await _call(mcp_with_tools, "list_datasets")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_infer_schema(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute.return_value = _qr([{"x": 1}])
        out = await _call(mcp_with_tools, "infer_schema", dataset="Default.X")
        assert out["ok"] is True
        assert out["data"]["rows_sampled"] == 1


# ── Query ────────────────────────────────────────────────────────────────────


class TestQueryRegistered:
    @pytest.mark.asyncio
    async def test_execute_query(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute.return_value = _qr([{"n": 1}])
        out = await _call(mcp_with_tools, "execute_query", statement="SELECT 1")
        assert out["ok"] is True
        assert out["data"]["results"] == [{"n": 1}]

    @pytest.mark.asyncio
    async def test_execute_query_readonly(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute_readonly.return_value = _qr([])
        out = await _call(mcp_with_tools, "execute_query_readonly", statement="SELECT 1")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_query_paginated(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute_readonly.return_value = _qr([{"n": 1}])
        out = await _call(
            mcp_with_tools,
            "execute_query_paginated",
            statement="SELECT 1",
            page_size=10,
        )
        assert out["ok"] is True
        assert out["data"]["pagination_handle"].startswith("p_")

    @pytest.mark.asyncio
    async def test_fetch_next_page(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        # First, get a handle from execute_query_paginated
        fake_pool.default().analytics.execute_readonly.return_value = _qr([{"n": i} for i in range(10)])
        first = await _call(
            mcp_with_tools,
            "execute_query_paginated",
            statement="SELECT 1",
            page_size=10,
        )
        handle = first["data"]["pagination_handle"]
        # Now fetch_next_page
        fake_pool.default().analytics.execute_readonly.return_value = _qr([])
        out = await _call(mcp_with_tools, "fetch_next_page", pagination_handle=handle)
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_explain_query(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().analytics.execute_readonly.return_value = _qr([{"plan": "scan"}])
        out = await _call(mcp_with_tools, "explain_query", statement="SELECT 1")
        assert out["ok"] is True
        assert "plan" in out["data"]


# ── Admin ────────────────────────────────────────────────────────────────────


class TestAdminRegistered:
    @pytest.mark.asyncio
    async def test_get_service_status(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().admin.get_service_status.return_value = ServiceStatus(state="OK")
        out = await _call(mcp_with_tools, "get_service_status")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_ingestion_status(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().admin.get_ingestion_status.return_value = IngestionStatus()
        out = await _call(mcp_with_tools, "get_ingestion_status")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_active_requests(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().admin.get_active_requests.return_value = []
        out = await _call(mcp_with_tools, "get_active_requests")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_completed_requests(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().admin.get_completed_requests.return_value = []
        out = await _call(mcp_with_tools, "get_completed_requests")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_cancel_request(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        out = await _call(mcp_with_tools, "cancel_request", client_context_id="c-1")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_restart_service(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "restart_service")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_restart_node(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "restart_node")
        assert out["ok"] is True


# ── Config ───────────────────────────────────────────────────────────────────


class TestConfigRegistered:
    @pytest.mark.asyncio
    async def test_get_service_config(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().config.get_service_config.return_value = ServiceConfig()
        out = await _call(mcp_with_tools, "get_service_config")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_update_service_config(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().config.update_service_config.return_value = ServiceConfig(resultTtl=600)
        out = await _call(mcp_with_tools, "update_service_config", settings={"resultTtl": 600})
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_analytics_settings(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().settings.get_settings.return_value = AnalyticsSettings(numReplicas=1)
        out = await _call(mcp_with_tools, "get_analytics_settings")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_update_analytics_settings(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().settings.update_settings.return_value = AnalyticsSettings(numReplicas=2)
        out = await _call(mcp_with_tools, "update_analytics_settings", num_replicas=2)
        assert out["ok"] is True


# ── Links ────────────────────────────────────────────────────────────────────


class TestLinksRegistered:
    @pytest.mark.asyncio
    async def test_list_links(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().links.get_all_links.return_value = []
        out = await _call(mcp_with_tools, "list_links")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_link(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().links.get_link.return_value = LinkInfo(name="x", type="s3", dataverse="Default")
        out = await _call(mcp_with_tools, "get_link", name="x")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_create_link(self, mcp_with_tools: Any) -> None:
        out = await _call(
            mcp_with_tools,
            "create_link",
            name="ml",
            dataverse="Default",
            config={"type": "s3"},
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_update_link(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "update_link", name="ml", config={"type": "s3"})
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_link(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "delete_link", name="ml")
        assert out["ok"] is True


# ── Libraries ────────────────────────────────────────────────────────────────


class TestLibrariesRegistered:
    @pytest.mark.asyncio
    async def test_list_libraries(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().libraries.list_libraries.return_value = [
            LibraryInfo(name="lib", scope="Default"),
        ]
        out = await _call(mcp_with_tools, "list_libraries")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_library(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "delete_library", scope="Default", library_name="lib")
        assert out["ok"] is True


# ── Security ─────────────────────────────────────────────────────────────────


class TestSecurityRegistered:
    @pytest.mark.asyncio
    async def test_list_users(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().security.list_users.return_value = []
        out = await _call(mcp_with_tools, "list_users")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_user(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().security.get_user.return_value = UserInfo(id="alice", domain="local")
        out = await _call(mcp_with_tools, "get_user", domain="local", username="alice")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_upsert_user(self, mcp_with_tools: Any) -> None:
        out = await _call(
            mcp_with_tools,
            "upsert_user",
            domain="local",
            username="alice",
            roles="reader",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_user(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "delete_user", domain="local", username="alice")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_list_groups(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().security.list_groups.return_value = [
            GroupInfo(id="g1", description="x"),
        ]
        out = await _call(mcp_with_tools, "list_groups")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_upsert_group(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "upsert_group", groupname="g1", roles="reader")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_group(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "delete_group", groupname="g1")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_list_roles(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().security.list_roles.return_value = []
        out = await _call(mcp_with_tools, "list_roles")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_check_permissions(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().security.check_permissions.return_value = {"x": True}
        out = await _call(mcp_with_tools, "check_permissions", permissions="cluster.admin!read")
        assert out["ok"] is True


# ── Cluster ──────────────────────────────────────────────────────────────────


class TestClusterRegistered:
    @pytest.mark.asyncio
    async def test_ping_cluster(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "ping_cluster")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_cluster_info(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_cluster_info.return_value = ClusterInfo(uuid="x")
        out = await _call(mcp_with_tools, "get_cluster_info")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_cluster_details(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_cluster_details.return_value = ClusterDetails()
        out = await _call(mcp_with_tools, "get_cluster_details")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_cluster_tasks(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_cluster_tasks.return_value = []
        out = await _call(mcp_with_tools, "get_cluster_tasks")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_rebalance_progress(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_rebalance_progress.return_value = RebalanceProgress(status="none")
        out = await _call(mcp_with_tools, "get_rebalance_progress")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_auto_failover_settings(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_auto_failover_settings.return_value = AutoFailoverSettings()
        out = await _call(mcp_with_tools, "get_auto_failover_settings")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_configure_auto_failover(self, mcp_with_tools: Any) -> None:
        out = await _call(mcp_with_tools, "configure_auto_failover", enabled=True)
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_system_events(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.get_system_events.return_value = []
        out = await _call(mcp_with_tools, "get_system_events")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_who_am_i(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.default().cluster.who_am_i.return_value = {"id": "x"}
        out = await _call(mcp_with_tools, "who_am_i")
        assert out["ok"] is True


# ── Capella ──────────────────────────────────────────────────────────────────


class TestCapellaRegistered:
    @pytest.mark.asyncio
    async def test_list_organizations(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.list_organizations.return_value = []
        out = await _call(mcp_with_tools, "capella_list_organizations")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_list_clusters(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.list_clusters.return_value = []
        out = await _call(mcp_with_tools, "capella_list_clusters", org_id="o", project_id="p")
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_get_cluster(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.get_cluster.return_value = {"id": "c"}
        out = await _call(
            mcp_with_tools,
            "capella_get_cluster",
            org_id="o",
            project_id="p",
            cluster_id="c",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_create_cluster(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.create_cluster.return_value = {"id": "new"}
        out = await _call(
            mcp_with_tools,
            "capella_create_cluster",
            org_id="o",
            project_id="p",
            cluster_spec={"name": "x"},
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_cluster(self, mcp_with_tools: Any) -> None:
        out = await _call(
            mcp_with_tools,
            "capella_delete_cluster",
            org_id="o",
            project_id="p",
            cluster_id="c",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_list_backups(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.list_backups.return_value = []
        out = await _call(
            mcp_with_tools,
            "capella_list_backups",
            org_id="o",
            project_id="p",
            cluster_id="c",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_create_backup(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.create_backup.return_value = {"id": "b"}
        out = await _call(
            mcp_with_tools,
            "capella_create_backup",
            org_id="o",
            project_id="p",
            cluster_id="c",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_restore_backup(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.restore_backup.return_value = {"status": "restoring"}
        out = await _call(
            mcp_with_tools,
            "capella_restore_backup",
            org_id="o",
            project_id="p",
            cluster_id="c",
            backup_id="b",
        )
        assert out["ok"] is True

    @pytest.mark.asyncio
    async def test_list_api_keys(self, mcp_with_tools: Any, fake_pool: FakePool) -> None:
        fake_pool.capella.list_api_keys.return_value = []
        out = await _call(mcp_with_tools, "capella_list_api_keys", org_id="o")
        assert out["ok"] is True

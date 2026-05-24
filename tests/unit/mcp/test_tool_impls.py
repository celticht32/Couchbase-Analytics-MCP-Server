# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Tests for tool _impl functions.

Each test calls the _impl directly with a FakePool and verifies:
- the correct client method was called with the expected args
- the response shape matches (ok=True/False, data, cluster, etc).
"""

from __future__ import annotations

from typing import Any

import pytest

from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsNotFoundError,
    AnalyticsQueryError,
    AnalyticsRequestError,
)
from cb_analytics_mcp.couchbase.models import (
    ActiveRequest,
    AnalyticsMetrics,
    AnalyticsQueryResponse,
    AnalyticsSettings,
    AutoFailoverSettings,
    ClusterDetails,
    ClusterInfo,
    ClusterTask,
    GroupInfo,
    IngestionStatus,
    LibraryInfo,
    LinkInfo,
    RebalanceProgress,
    ServiceConfig,
    ServiceStatus,
    SystemEvent,
    UserInfo,
)
from cb_analytics_mcp.tools.admin import (
    cancel_request_impl,
    get_active_requests_impl,
    get_completed_requests_impl,
    get_ingestion_status_impl,
    get_service_status_impl,
    restart_node_impl,
    restart_service_impl,
)
from cb_analytics_mcp.tools.capella import (
    capella_create_backup_impl,
    capella_create_cluster_impl,
    capella_delete_cluster_impl,
    capella_get_cluster_impl,
    capella_list_api_keys_impl,
    capella_list_backups_impl,
    capella_list_clusters_impl,
    capella_list_organizations_impl,
    capella_restore_backup_impl,
)
from cb_analytics_mcp.tools.cluster import (
    configure_auto_failover_impl,
    get_auto_failover_settings_impl,
    get_cluster_details_impl,
    get_cluster_info_impl,
    get_cluster_tasks_impl,
    get_rebalance_progress_impl,
    get_system_events_impl,
    ping_cluster_impl,
    who_am_i_impl,
)
from cb_analytics_mcp.tools.config_tools import (
    get_analytics_settings_impl,
    get_service_config_impl,
    update_analytics_settings_impl,
    update_service_config_impl,
)
from cb_analytics_mcp.tools.libraries import (
    delete_library_impl,
    list_libraries_impl,
)
from cb_analytics_mcp.tools.links import (
    create_link_impl,
    delete_link_impl,
    get_link_impl,
    list_links_impl,
    update_link_impl,
)
from cb_analytics_mcp.tools.meta import (
    get_capabilities_impl,
    list_clusters_impl,
)
from cb_analytics_mcp.tools.query import (
    execute_query_impl,
    execute_query_readonly_impl,
)
from cb_analytics_mcp.tools.schema import (
    _is_safe_identifier,
    infer_schema_impl,
    list_datasets_impl,
    list_dataverses_impl,
)
from cb_analytics_mcp.tools.security import (
    check_permissions_impl,
    delete_group_impl,
    delete_user_impl,
    get_user_impl,
    list_groups_impl,
    list_roles_impl,
    list_users_impl,
    upsert_group_impl,
    upsert_user_impl,
)
from tests.unit.mcp.conftest import FakeClient, FakePool


def _query_response(results: list[Any]) -> AnalyticsQueryResponse:
    return AnalyticsQueryResponse(
        requestID="r1",
        status="success",
        results=results,
        metrics=AnalyticsMetrics(resultCount=len(results)),
    )


# ── Meta ──────────────────────────────────────────────────────────────────────


class TestMetaTools:
    @pytest.mark.asyncio
    async def test_list_clusters(self, fake_pool: FakePool) -> None:
        out = await list_clusters_impl(fake_pool)
        assert out["ok"] is True
        assert out["data"]["clusters"] == ["default"]
        assert out["data"]["default"] == "default"
        assert out["data"]["count"] == 1
        assert out["data"]["capella_configured"] is False

    @pytest.mark.asyncio
    async def test_list_clusters_capella_enabled(self, fake_pool_capella: FakePool) -> None:
        out = await list_clusters_impl(fake_pool_capella)
        assert out["data"]["capella_configured"] is True

    @pytest.mark.asyncio
    async def test_get_capabilities(self, fake_pool: FakePool) -> None:
        out = await get_capabilities_impl(fake_pool)
        assert out["ok"] is True
        assert out["data"]["name"] == "cb-analytics-mcp"
        assert "version" in out["data"]
        assert "execute_query" not in out["data"]["tool_groups"]  # groups, not tools
        assert "query" in out["data"]["tool_groups"]


# ── Schema ────────────────────────────────────────────────────────────────────


class TestSchemaTools:
    @pytest.mark.asyncio
    async def test_list_dataverses(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response(["Default", "MyDV"])
        out = await list_dataverses_impl(fake_pool)
        assert out["ok"] is True
        assert out["data"] == ["Default", "MyDV"]
        assert out["cluster"] == "default"

        # Verify the right SQL was sent
        call = fake_client.analytics.execute.call_args[0][0]
        assert "Metadata.`Dataverse`" in call.statement

    @pytest.mark.asyncio
    async def test_list_datasets_unfiltered(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response(
            [{"name": "ds1", "dataverse": "Default"}]
        )
        out = await list_datasets_impl(fake_pool)
        assert out["ok"] is True
        assert out["data"][0]["name"] == "ds1"

        call = fake_client.analytics.execute.call_args[0][0]
        # Should not include WHERE clause
        assert "WHERE" not in call.statement.upper()

    @pytest.mark.asyncio
    async def test_list_datasets_filtered(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response([])
        await list_datasets_impl(fake_pool, dataverse="MyDV")

        call = fake_client.analytics.execute.call_args[0][0]
        assert "WHERE" in call.statement.upper()
        assert call.named_args == {"dv": "MyDV"}

    @pytest.mark.asyncio
    async def test_infer_schema_summarises_fields(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response(
            [
                {"name": "alice", "age": 30, "active": True},
                {"name": "bob", "age": 25, "active": False},
                {"name": "carol", "age": 40},  # no 'active'
            ]
        )
        out = await infer_schema_impl(fake_pool, dataset="users", sample_size=10)
        assert out["ok"] is True
        fields = out["data"]["fields"]
        assert fields["name"]["present_count"] == 3
        assert fields["name"]["presence_pct"] == 100.0
        assert fields["active"]["present_count"] == 2
        assert "str" in fields["name"]["types"]
        assert "int" in fields["age"]["types"]
        assert out["data"]["rows_sampled"] == 3

    @pytest.mark.asyncio
    async def test_infer_schema_rejects_invalid_dataset(self, fake_pool: FakePool) -> None:
        with pytest.raises(AnalyticsRequestError, match="Invalid dataset name"):
            await infer_schema_impl(fake_pool, dataset="users; DROP DATAVERSE Default")

    def test_is_safe_identifier(self) -> None:
        assert _is_safe_identifier("users")
        assert _is_safe_identifier("MyDataverse.MyDataset")
        assert _is_safe_identifier("`weird name`")
        assert _is_safe_identifier("Default.`my ds`.sub")
        # Negatives
        assert not _is_safe_identifier("")
        assert not _is_safe_identifier("users; DROP TABLE x")
        assert not _is_safe_identifier("users DROP")
        assert not _is_safe_identifier("a" * 257)
        assert not _is_safe_identifier("users'")


# ── Query ─────────────────────────────────────────────────────────────────────


class TestQueryTools:
    @pytest.mark.asyncio
    async def test_execute_query_success(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response([{"n": 1}])
        out = await execute_query_impl(fake_pool, "SELECT 1")
        assert out["ok"] is True
        assert out["data"]["results"] == [{"n": 1}]
        assert out["data"]["status"] == "success"
        assert out["cluster"] == "default"

    @pytest.mark.asyncio
    async def test_execute_query_with_named_args(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.return_value = _query_response([])
        await execute_query_impl(fake_pool, "SELECT $id", named_args={"id": 42})
        call = fake_client.analytics.execute.call_args[0][0]
        assert call.named_args == {"id": 42}

    @pytest.mark.asyncio
    async def test_execute_query_with_scan_consistency(
        self, fake_pool: FakePool, fake_client: FakeClient
    ) -> None:
        fake_client.analytics.execute.return_value = _query_response([])
        await execute_query_impl(fake_pool, "SELECT 1", scan_consistency="request_plus")
        call = fake_client.analytics.execute.call_args[0][0]
        assert call.scan_consistency.value == "request_plus"

    @pytest.mark.asyncio
    async def test_execute_query_error_propagates(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute.side_effect = AnalyticsQueryError("syntax error", code=24000)
        with pytest.raises(AnalyticsQueryError):
            await execute_query_impl(fake_pool, "BAD STATEMENT")

    @pytest.mark.asyncio
    async def test_execute_query_readonly(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.analytics.execute_readonly.return_value = _query_response([])
        await execute_query_readonly_impl(fake_pool, "SELECT 1")
        call = fake_client.analytics.execute_readonly.call_args[0][0]
        assert call.readonly is True


class TestQueryCaching:
    """execute_query_readonly should consult and populate the cache when given one."""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import execute_query_readonly_impl

        cache = ResultCache(default_ttl=60)
        fake_client.analytics.execute_readonly.return_value = _query_response([{"n": 1}])

        # First call → miss, populates cache, returns cached=False
        first = await execute_query_readonly_impl(fake_pool, "SELECT 1", cache=cache)
        assert first["data"]["cached"] is False
        assert fake_client.analytics.execute_readonly.call_count == 1

        # Second identical call → cache hit, no second network call
        second = await execute_query_readonly_impl(fake_pool, "SELECT 1", cache=cache)
        assert second["data"]["cached"] is True
        assert fake_client.analytics.execute_readonly.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_keyed_by_consistency(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        """Different scan_consistency = different cache entries."""
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import execute_query_readonly_impl

        cache = ResultCache(default_ttl=60)
        fake_client.analytics.execute_readonly.return_value = _query_response([])
        await execute_query_readonly_impl(fake_pool, "SELECT 1", cache=cache)
        await execute_query_readonly_impl(fake_pool, "SELECT 1", scan_consistency="request_plus", cache=cache)
        assert fake_client.analytics.execute_readonly.call_count == 2

    @pytest.mark.asyncio
    async def test_no_cache_falls_back_to_direct_call(
        self, fake_pool: FakePool, fake_client: FakeClient
    ) -> None:
        from cb_analytics_mcp.tools.query import execute_query_readonly_impl

        fake_client.analytics.execute_readonly.return_value = _query_response([])
        # cache parameter omitted → no caching, original behaviour
        out = await execute_query_readonly_impl(fake_pool, "SELECT 1")
        assert out["ok"] is True


class TestPaginatedQuery:
    @pytest.mark.asyncio
    async def test_first_page_returns_handle(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import execute_query_paginated_impl

        cache = ResultCache()
        fake_client.analytics.execute_readonly.return_value = _query_response([{"n": i} for i in range(10)])
        out = await execute_query_paginated_impl(fake_pool, "SELECT * FROM x", page_size=10, cache=cache)
        assert out["data"]["rows_returned"] == 10
        assert out["data"]["has_more"] is True
        assert out["data"]["pagination_handle"].startswith("p_")

    @pytest.mark.asyncio
    async def test_strips_trailing_limit(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        """User's LIMIT clause should be stripped so our pagination wins."""
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import execute_query_paginated_impl

        cache = ResultCache()
        fake_client.analytics.execute_readonly.return_value = _query_response([])
        await execute_query_paginated_impl(fake_pool, "SELECT * FROM x LIMIT 1000", page_size=50, cache=cache)
        call = fake_client.analytics.execute_readonly.call_args[0][0]
        # User's LIMIT 1000 should be gone, only our LIMIT 50 OFFSET 0 remains
        assert "LIMIT 50 OFFSET 0" in call.statement
        assert "1000" not in call.statement

    @pytest.mark.asyncio
    async def test_invalid_page_size_rejected(self, fake_pool: FakePool) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError
        from cb_analytics_mcp.tools.query import execute_query_paginated_impl

        cache = ResultCache()
        with pytest.raises(AnalyticsRequestError):
            await execute_query_paginated_impl(fake_pool, "SELECT 1", page_size=0, cache=cache)
        with pytest.raises(AnalyticsRequestError):
            await execute_query_paginated_impl(fake_pool, "SELECT 1", page_size=20000, cache=cache)

    @pytest.mark.asyncio
    async def test_requires_cache(self, fake_pool: FakePool) -> None:
        from cb_analytics_mcp.tools.query import execute_query_paginated_impl

        with pytest.raises(RuntimeError, match="cache"):
            await execute_query_paginated_impl(fake_pool, "SELECT 1", cache=None)


class TestFetchNextPage:
    @pytest.mark.asyncio
    async def test_fetches_next_offset(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import (
            execute_query_paginated_impl,
            fetch_next_page_impl,
        )

        cache = ResultCache()
        # First page: 100 rows (full page)
        fake_client.analytics.execute_readonly.return_value = _query_response([{"n": i} for i in range(100)])
        first = await execute_query_paginated_impl(fake_pool, "SELECT * FROM x", page_size=100, cache=cache)
        handle = first["data"]["pagination_handle"]

        # Second page: 50 rows (partial → has_more = False)
        fake_client.analytics.execute_readonly.return_value = _query_response(
            [{"n": i} for i in range(100, 150)]
        )
        second = await fetch_next_page_impl(fake_pool, handle, cache=cache)
        assert second["data"]["page_offset"] == 100
        assert second["data"]["rows_returned"] == 50
        assert second["data"]["has_more"] is False
        assert second["data"]["total_seen"] == 150
        # Statement should be the cleaned base + new offset
        call = fake_client.analytics.execute_readonly.call_args[0][0]
        assert "OFFSET 100" in call.statement

    @pytest.mark.asyncio
    async def test_exhausted_handle_is_dropped(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.tools.query import (
            execute_query_paginated_impl,
            fetch_next_page_impl,
        )

        cache = ResultCache()
        fake_client.analytics.execute_readonly.return_value = _query_response([{"n": i} for i in range(10)])
        first = await execute_query_paginated_impl(fake_pool, "SELECT 1", page_size=10, cache=cache)
        handle = first["data"]["pagination_handle"]

        # Next page returns 0 rows → has_more false, handle dropped
        fake_client.analytics.execute_readonly.return_value = _query_response([])
        await fetch_next_page_impl(fake_pool, handle, cache=cache)

        # Handle should no longer be valid
        assert await cache.get_pagination(handle) is None

    @pytest.mark.asyncio
    async def test_missing_handle_raises(self, fake_pool: FakePool) -> None:
        from cb_analytics_mcp.cache import ResultCache
        from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError
        from cb_analytics_mcp.tools.query import fetch_next_page_impl

        cache = ResultCache()
        with pytest.raises(AnalyticsRequestError, match="not found or expired"):
            await fetch_next_page_impl(fake_pool, "p_nope", cache=cache)


class TestExplainQuery:
    @pytest.mark.asyncio
    async def test_prepends_explain(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        from cb_analytics_mcp.tools.query import explain_query_impl

        fake_client.analytics.execute_readonly.return_value = _query_response([{"plan": "Scan(...)"}])
        out = await explain_query_impl(fake_pool, "SELECT * FROM x")
        call = fake_client.analytics.execute_readonly.call_args[0][0]
        assert call.statement.startswith("EXPLAIN ")
        assert out["data"]["plan"] == [{"plan": "Scan(...)"}]

    @pytest.mark.asyncio
    async def test_does_not_double_explain(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        """If user already wrote EXPLAIN, don't add another."""
        from cb_analytics_mcp.tools.query import explain_query_impl

        fake_client.analytics.execute_readonly.return_value = _query_response([])
        await explain_query_impl(fake_pool, "EXPLAIN SELECT * FROM x")
        call = fake_client.analytics.execute_readonly.call_args[0][0]
        # Should be exactly one EXPLAIN
        assert call.statement.upper().count("EXPLAIN") == 1

    @pytest.mark.asyncio
    async def test_empty_statement_rejected(self, fake_pool: FakePool) -> None:
        from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError
        from cb_analytics_mcp.tools.query import explain_query_impl

        with pytest.raises(AnalyticsRequestError):
            await explain_query_impl(fake_pool, "   ")


class TestStripTrailingLimit:
    """Unit tests for the LIMIT-stripping helper used by pagination."""

    def test_strips_simple_limit(self) -> None:
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        assert _strip_trailing_limit("SELECT * FROM x LIMIT 10") == "SELECT * FROM x"

    def test_strips_limit_with_offset(self) -> None:
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        assert _strip_trailing_limit("SELECT * FROM x LIMIT 10 OFFSET 5") == "SELECT * FROM x"

    def test_strips_with_trailing_semicolon(self) -> None:
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        assert _strip_trailing_limit("SELECT 1 LIMIT 100 ;") == "SELECT 1"

    def test_case_insensitive(self) -> None:
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        assert _strip_trailing_limit("SELECT 1 limit 5") == "SELECT 1"

    def test_no_limit_unchanged(self) -> None:
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        assert _strip_trailing_limit("SELECT * FROM x") == "SELECT * FROM x"

    def test_inline_limit_not_stripped(self) -> None:
        """A LIMIT inside a subquery (not trailing) shouldn't be touched."""
        from cb_analytics_mcp.tools.query import _strip_trailing_limit

        stmt = "SELECT x FROM (SELECT * FROM y LIMIT 10) sub"
        assert _strip_trailing_limit(stmt) == stmt


# ── Admin ─────────────────────────────────────────────────────────────────────


class TestAdminTools:
    @pytest.mark.asyncio
    async def test_get_service_status(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.admin.get_service_status.return_value = ServiceStatus(
            state="ACTIVE", ccRevLag=0, authorizedNodes=["n1"]
        )
        out = await get_service_status_impl(fake_pool)
        assert out["data"]["state"] == "ACTIVE"
        assert out["data"]["authorizedNodes"] == ["n1"]

    @pytest.mark.asyncio
    async def test_get_ingestion_status(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.admin.get_ingestion_status.return_value = IngestionStatus(links=[])
        out = await get_ingestion_status_impl(fake_pool)
        assert out["data"]["links"] == []

    @pytest.mark.asyncio
    async def test_get_active_requests(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.admin.get_active_requests.return_value = [
            ActiveRequest(requestID="r1", statement="SELECT 1", state="active"),
        ]
        out = await get_active_requests_impl(fake_pool)
        assert len(out["data"]) == 1
        assert out["data"][0]["requestID"] == "r1"

    @pytest.mark.asyncio
    async def test_get_completed_requests(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.admin.get_completed_requests.return_value = []
        out = await get_completed_requests_impl(fake_pool, "ctx-1")
        fake_client.admin.get_completed_requests.assert_called_once_with("ctx-1")
        assert out["data"] == []

    @pytest.mark.asyncio
    async def test_cancel_request(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await cancel_request_impl(fake_pool, "ctx-1")
        fake_client.admin.cancel_request.assert_called_once_with("ctx-1")
        assert out["data"]["cancelled"] == "ctx-1"

    @pytest.mark.asyncio
    async def test_restart_service(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await restart_service_impl(fake_pool)
        fake_client.admin.restart_service.assert_called_once()
        assert out["data"]["restarted"] == "service"

    @pytest.mark.asyncio
    async def test_restart_node(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await restart_node_impl(fake_pool)
        fake_client.admin.restart_node.assert_called_once()
        assert out["data"]["restarted"] == "node"


# ── Config & Settings ────────────────────────────────────────────────────────


class TestConfigTools:
    @pytest.mark.asyncio
    async def test_get_service_config(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.config.get_service_config.return_value = ServiceConfig(resultTtl=3600)
        out = await get_service_config_impl(fake_pool)
        assert out["data"]["resultTtl"] == 3600

    @pytest.mark.asyncio
    async def test_update_service_config(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.config.update_service_config.return_value = ServiceConfig(resultTtl=7200)
        out = await update_service_config_impl(fake_pool, {"resultTtl": 7200})
        assert out["data"]["resultTtl"] == 7200

    @pytest.mark.asyncio
    async def test_get_analytics_settings(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.settings.get_settings.return_value = AnalyticsSettings(numReplicas=2)
        out = await get_analytics_settings_impl(fake_pool)
        assert out["data"]["numReplicas"] == 2

    @pytest.mark.asyncio
    async def test_update_analytics_settings(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.settings.update_settings.return_value = AnalyticsSettings(numReplicas=3)
        out = await update_analytics_settings_impl(fake_pool, num_replicas=3)
        assert out["data"]["numReplicas"] == 3


# ── Links ────────────────────────────────────────────────────────────────────


class TestLinksTools:
    @pytest.mark.asyncio
    async def test_list_links(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.links.get_all_links.return_value = [
            LinkInfo(name="s3", type="s3", dataverse="Default", activeDatasets=[]),
        ]
        out = await list_links_impl(fake_pool)
        assert len(out["data"]) == 1
        assert out["data"][0]["name"] == "s3"

    @pytest.mark.asyncio
    async def test_list_links_with_filters(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.links.get_all_links.return_value = []
        await list_links_impl(fake_pool, dataverse="DV1", link_type="s3")
        fake_client.links.get_all_links.assert_called_once_with(dataverse="DV1", link_type="s3")

    @pytest.mark.asyncio
    async def test_get_link(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.links.get_link.return_value = LinkInfo(name="x", type="s3", dataverse="Default")
        out = await get_link_impl(fake_pool, "x")
        assert out["data"]["name"] == "x"

    @pytest.mark.asyncio
    async def test_create_link(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await create_link_impl(fake_pool, "ml", "Default", {"type": "s3", "region": "us-east-1"})
        fake_client.links.create_link.assert_called_once()
        assert out["data"]["created"] == "ml"

    @pytest.mark.asyncio
    async def test_update_link(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await update_link_impl(fake_pool, "ml", {"type": "s3"})
        fake_client.links.update_link.assert_called_once()
        assert out["data"]["updated"] == "ml"

    @pytest.mark.asyncio
    async def test_delete_link(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await delete_link_impl(fake_pool, "ml")
        fake_client.links.delete_link.assert_called_once_with("ml")
        assert out["data"]["deleted"] == "ml"


# ── Libraries ─────────────────────────────────────────────────────────────────


class TestLibraryTools:
    @pytest.mark.asyncio
    async def test_list_libraries(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.libraries.list_libraries.return_value = [
            LibraryInfo(name="mylib", scope="Default", functions=[]),
        ]
        out = await list_libraries_impl(fake_pool)
        assert len(out["data"]) == 1
        assert out["data"][0]["name"] == "mylib"

    @pytest.mark.asyncio
    async def test_delete_library(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await delete_library_impl(fake_pool, "Default", "mylib")
        fake_client.libraries.delete_library.assert_called_once_with("Default", "mylib")
        assert out["data"]["deleted"] == "mylib"


# ── Security ─────────────────────────────────────────────────────────────────


class TestSecurityTools:
    @pytest.mark.asyncio
    async def test_list_users(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.list_users.return_value = [
            UserInfo(id="alice", domain="local"),
        ]
        out = await list_users_impl(fake_pool)
        assert out["data"][0]["id"] == "alice"

    @pytest.mark.asyncio
    async def test_list_users_with_domain(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.list_users.return_value = []
        await list_users_impl(fake_pool, domain="external")
        # Verify domain was coerced and passed
        kwargs = fake_client.security.list_users.call_args.kwargs
        assert kwargs["domain"].value == "external"

    @pytest.mark.asyncio
    async def test_get_user(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.get_user.return_value = UserInfo(id="alice", domain="local")
        out = await get_user_impl(fake_pool, "local", "alice")
        assert out["data"]["id"] == "alice"

    @pytest.mark.asyncio
    async def test_upsert_user_with_password(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await upsert_user_impl(
            fake_pool, "local", "alice", roles="reader", password="newpass", full_name="Alice"
        )
        fake_client.security.upsert_user.assert_called_once()
        args = fake_client.security.upsert_user.call_args[0]
        assert args[1] == "alice"
        # The request includes the password wrapped in SecretStr
        req = args[2]
        assert req.password.get_secret_value() == "newpass"
        assert req.name == "Alice"
        assert out["data"]["upserted"] == "alice"

    @pytest.mark.asyncio
    async def test_upsert_user_without_password(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        await upsert_user_impl(fake_pool, "local", "alice", roles="reader")
        req = fake_client.security.upsert_user.call_args[0][2]
        assert req.password is None

    @pytest.mark.asyncio
    async def test_delete_user(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await delete_user_impl(fake_pool, "local", "alice")
        assert out["data"]["deleted"] == "alice"

    @pytest.mark.asyncio
    async def test_list_groups(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.list_groups.return_value = [
            GroupInfo(id="g1", description="team"),
        ]
        out = await list_groups_impl(fake_pool)
        assert out["data"][0]["id"] == "g1"

    @pytest.mark.asyncio
    async def test_upsert_group(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await upsert_group_impl(fake_pool, "g1", roles="reader", description="team")
        assert out["data"]["upserted"] == "g1"

    @pytest.mark.asyncio
    async def test_delete_group(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await delete_group_impl(fake_pool, "g1")
        assert out["data"]["deleted"] == "g1"

    @pytest.mark.asyncio
    async def test_list_roles(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.list_roles.return_value = [
            {"role": "admin", "desc": "Admin"},
        ]
        out = await list_roles_impl(fake_pool)
        assert len(out["data"]) == 1

    @pytest.mark.asyncio
    async def test_check_permissions(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.security.check_permissions.return_value = {"cluster.analytics!read": True}
        out = await check_permissions_impl(fake_pool, "cluster.analytics!read")
        assert out["data"]["cluster.analytics!read"] is True


# ── Cluster ──────────────────────────────────────────────────────────────────


class TestClusterTools:
    @pytest.mark.asyncio
    async def test_ping_cluster(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await ping_cluster_impl(fake_pool)
        assert out["data"]["reachable"] is True

    @pytest.mark.asyncio
    async def test_get_cluster_info(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_cluster_info.return_value = ClusterInfo(
            uuid="abc", implementationVersion="7.6"
        )
        out = await get_cluster_info_impl(fake_pool)
        assert out["data"]["uuid"] == "abc"

    @pytest.mark.asyncio
    async def test_get_cluster_details(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_cluster_details.return_value = ClusterDetails(
            clusterName="prod", nodes=[{"x": 1}], memoryQuota=4096
        )
        out = await get_cluster_details_impl(fake_pool)
        assert out["data"]["clusterName"] == "prod"
        assert out["data"]["memoryQuota"] == 4096

    @pytest.mark.asyncio
    async def test_get_cluster_tasks(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_cluster_tasks.return_value = [
            ClusterTask(type="rebalance", status="running"),
        ]
        out = await get_cluster_tasks_impl(fake_pool)
        assert out["data"][0]["type"] == "rebalance"

    @pytest.mark.asyncio
    async def test_get_rebalance_progress(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_rebalance_progress.return_value = RebalanceProgress(status="running")
        out = await get_rebalance_progress_impl(fake_pool)
        assert out["data"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_auto_failover_settings(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_auto_failover_settings.return_value = AutoFailoverSettings(
            enabled=True, timeout=120, maxCount=1
        )
        out = await get_auto_failover_settings_impl(fake_pool)
        assert out["data"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_configure_auto_failover(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        out = await configure_auto_failover_impl(fake_pool, enabled=True, timeout=60, max_count=2)
        fake_client.cluster.configure_auto_failover.assert_called_once()
        s = fake_client.cluster.configure_auto_failover.call_args[0][0]
        assert s.timeout == 60
        assert s.maxCount == 2
        assert out["data"]["timeout"] == 60

    @pytest.mark.asyncio
    async def test_get_system_events(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.get_system_events.return_value = [
            SystemEvent(timestamp="2026-05-24T00:00:00Z", severity="info"),
        ]
        out = await get_system_events_impl(fake_pool, since_time="2026-01-01T00:00:00Z")
        fake_client.cluster.get_system_events.assert_called_once_with("2026-01-01T00:00:00Z")
        assert len(out["data"]) == 1

    @pytest.mark.asyncio
    async def test_who_am_i(self, fake_pool: FakePool, fake_client: FakeClient) -> None:
        fake_client.cluster.who_am_i.return_value = {"id": "Administrator"}
        out = await who_am_i_impl(fake_pool)
        assert out["data"]["id"] == "Administrator"


# ── Capella ──────────────────────────────────────────────────────────────────


class TestCapellaTools:
    @pytest.mark.asyncio
    async def test_list_organizations(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.list_organizations.return_value = [{"id": "org-1", "name": "A"}]
        out = await capella_list_organizations_impl(fake_pool_capella)
        assert out["data"][0]["id"] == "org-1"

    @pytest.mark.asyncio
    async def test_capella_unavailable_raises(self, fake_pool: FakePool) -> None:
        # fake_pool has Capella disabled by default
        with pytest.raises(RuntimeError, match="Capella"):
            await capella_list_organizations_impl(fake_pool)

    @pytest.mark.asyncio
    async def test_list_clusters(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.list_clusters.return_value = [{"id": "c-1"}]
        out = await capella_list_clusters_impl(fake_pool_capella, "o", "p")
        fake_pool_capella.capella.list_clusters.assert_called_once_with("o", "p")
        assert out["data"][0]["id"] == "c-1"

    @pytest.mark.asyncio
    async def test_get_cluster(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.get_cluster.return_value = {"id": "c-1", "name": "x"}
        out = await capella_get_cluster_impl(fake_pool_capella, "o", "p", "c")
        assert out["data"]["id"] == "c-1"

    @pytest.mark.asyncio
    async def test_create_cluster(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.create_cluster.return_value = {"id": "new"}
        out = await capella_create_cluster_impl(fake_pool_capella, "o", "p", {"name": "n"})
        assert out["data"]["id"] == "new"

    @pytest.mark.asyncio
    async def test_delete_cluster(self, fake_pool_capella: FakePool) -> None:
        out = await capella_delete_cluster_impl(fake_pool_capella, "o", "p", "c")
        assert out["data"]["deleted"] == "c"

    @pytest.mark.asyncio
    async def test_list_backups(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.list_backups.return_value = [{"id": "b-1"}]
        out = await capella_list_backups_impl(fake_pool_capella, "o", "p", "c")
        assert len(out["data"]) == 1

    @pytest.mark.asyncio
    async def test_create_backup(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.create_backup.return_value = {"id": "b-1"}
        out = await capella_create_backup_impl(fake_pool_capella, "o", "p", "c")
        assert out["data"]["id"] == "b-1"

    @pytest.mark.asyncio
    async def test_restore_backup(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.restore_backup.return_value = {"status": "restoring"}
        out = await capella_restore_backup_impl(fake_pool_capella, "o", "p", "c", "b", target_cluster_id="t")
        fake_pool_capella.capella.restore_backup.assert_called_once_with(
            "o", "p", "c", "b", target_cluster_id="t"
        )
        assert out["data"]["status"] == "restoring"

    @pytest.mark.asyncio
    async def test_list_api_keys(self, fake_pool_capella: FakePool) -> None:
        fake_pool_capella.capella.list_api_keys.return_value = [{"id": "k-1"}]
        out = await capella_list_api_keys_impl(fake_pool_capella, "o")
        assert out["data"][0]["id"] == "k-1"


# ── Cluster resolution ───────────────────────────────────────────────────────


class TestClusterResolution:
    @pytest.mark.asyncio
    async def test_explicit_cluster_passed_to_pool(self) -> None:
        pool = FakePool(names=["c1", "c2"])
        pool.client_for("c2").admin.get_service_status.return_value = ServiceStatus(state="STATE_FROM_C2")
        out = await get_service_status_impl(pool, cluster="c2")
        assert out["data"]["state"] == "STATE_FROM_C2"
        assert out["cluster"] == "c2"

    @pytest.mark.asyncio
    async def test_unknown_cluster_raises(self) -> None:
        pool = FakePool(names=["c1"])
        with pytest.raises(ValueError, match="Unknown cluster"):
            await get_service_status_impl(pool, cluster="nope")

    @pytest.mark.asyncio
    async def test_auth_error_propagates(self) -> None:
        pool = FakePool()
        pool.default().admin.get_service_status.side_effect = AnalyticsAuthError("nope")
        with pytest.raises(AnalyticsAuthError):
            await get_service_status_impl(pool)

    @pytest.mark.asyncio
    async def test_not_found_propagates(self) -> None:
        pool = FakePool()
        pool.default().links.get_link.side_effect = AnalyticsNotFoundError("missing")
        with pytest.raises(AnalyticsNotFoundError):
            await get_link_impl(pool, "missing")

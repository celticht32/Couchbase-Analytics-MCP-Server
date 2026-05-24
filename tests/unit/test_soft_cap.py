# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the soft-cap behavior on execute_query / execute_query_readonly."""

from __future__ import annotations

from typing import Any

import pytest

from cb_analytics_mcp.couchbase.models import (
    AnalyticsMetrics,
    AnalyticsQueryResponse,
)
from cb_analytics_mcp.tools.query import (
    execute_query_impl,
    execute_query_readonly_impl,
)


def _qr(rows: list[Any]) -> AnalyticsQueryResponse:
    return AnalyticsQueryResponse(
        requestID="r1",
        status="success",
        results=rows,
        metrics=AnalyticsMetrics(),
        warnings=[],
    )


@pytest.fixture
def fake_pool_and_client():
    """Build a fake pool with a default client we can configure per-test."""
    from tests.unit.mcp.conftest import FakePool

    pool = FakePool()  # default: one cluster "default"
    client = pool.default()
    return pool, client


class TestExecuteQuerySoftCap:
    @pytest.mark.asyncio
    async def test_no_truncation_when_under_cap(self, fake_pool_and_client) -> None:
        pool, client = fake_pool_and_client
        client.analytics.execute.return_value = _qr([{"n": i} for i in range(5)])
        out = await execute_query_impl(pool, "SELECT 1", max_rows=1000)
        assert out["data"]["truncated"] is False
        assert len(out["data"]["results"]) == 5
        assert out["data"]["full_row_count"] == 5

    @pytest.mark.asyncio
    async def test_truncation_when_over_cap(self, fake_pool_and_client) -> None:
        pool, client = fake_pool_and_client
        # 1500 rows with a cap of 1000 → truncated to 1000
        client.analytics.execute.return_value = _qr([{"n": i} for i in range(1500)])
        out = await execute_query_impl(pool, "SELECT 1", max_rows=1000)
        assert out["data"]["truncated"] is True
        assert len(out["data"]["results"]) == 1000
        assert out["data"]["full_row_count"] == 1500
        assert out["data"]["row_cap"] == 1000

    @pytest.mark.asyncio
    async def test_zero_disables_cap(self, fake_pool_and_client) -> None:
        pool, client = fake_pool_and_client
        client.analytics.execute.return_value = _qr([{"n": i} for i in range(2500)])
        out = await execute_query_impl(pool, "SELECT 1", max_rows=0)
        assert out["data"]["truncated"] is False
        assert len(out["data"]["results"]) == 2500
        assert out["data"]["row_cap"] is None

    @pytest.mark.asyncio
    async def test_small_custom_cap(self, fake_pool_and_client) -> None:
        pool, client = fake_pool_and_client
        client.analytics.execute.return_value = _qr([{"n": i} for i in range(50)])
        out = await execute_query_impl(pool, "SELECT 1", max_rows=10)
        assert out["data"]["truncated"] is True
        assert len(out["data"]["results"]) == 10
        assert out["data"]["full_row_count"] == 50


class TestReadOnlySoftCap:
    @pytest.mark.asyncio
    async def test_readonly_truncation(self, fake_pool_and_client) -> None:
        pool, client = fake_pool_and_client
        client.analytics.execute_readonly.return_value = _qr([{"n": i} for i in range(1200)])
        out = await execute_query_readonly_impl(pool, "SELECT 1", max_rows=500)
        assert out["data"]["truncated"] is True
        assert len(out["data"]["results"]) == 500
        assert out["data"]["full_row_count"] == 1200

    @pytest.mark.asyncio
    async def test_readonly_cached_response_preserves_cap_marker(self, fake_pool_and_client) -> None:
        """A cache hit returns the previously-truncated payload as-is."""
        from cb_analytics_mcp.cache import ResultCache

        pool, client = fake_pool_and_client
        cache = ResultCache(default_ttl=60)
        client.analytics.execute_readonly.return_value = _qr([{"n": i} for i in range(2000)])
        # First call: populates cache with truncated=True
        first = await execute_query_readonly_impl(pool, "SELECT 1", cache=cache, max_rows=1000)
        assert first["data"]["truncated"] is True
        # Second call: cache hit, still truncated=True, but cached=True
        second = await execute_query_readonly_impl(pool, "SELECT 1", cache=cache, max_rows=1000)
        assert second["data"]["cached"] is True
        assert second["data"]["truncated"] is True
        assert second["data"]["full_row_count"] == 2000

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import asyncio

import pytest

from cb_analytics_mcp.config import LimitsConfig
from cb_analytics_mcp.rate_limit import (
    TOOL_CATEGORY,
    RateLimiter,
    RateLimitExceeded,
    category_for,
)


class TestRateLimitBasics:
    @pytest.mark.asyncio
    async def test_first_call_allowed(self) -> None:
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=5))
        # First call consumes one of five tokens — should pass
        remaining = await rl.check("token-1", "query")
        assert remaining == 4.0

    @pytest.mark.asyncio
    async def test_burst_then_exhaust(self) -> None:
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=3))
        # Consume all three tokens
        for _ in range(3):
            await rl.check("burst", "query")
        # Fourth call should raise
        with pytest.raises(RateLimitExceeded) as exc:
            await rl.check("burst", "query")
        assert exc.value.category == "query"
        assert exc.value.rate_per_sec == 3
        assert exc.value.retry_after_sec > 0

    @pytest.mark.asyncio
    async def test_refills_over_time(self) -> None:
        """After waiting, the bucket should accumulate tokens again."""
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=10))
        # Drain the bucket
        for _ in range(10):
            await rl.check("t", "query")
        with pytest.raises(RateLimitExceeded):
            await rl.check("t", "query")
        # Wait a moment for refill (10 tokens/sec → 0.15s should give us > 1 token)
        await asyncio.sleep(0.15)
        # This should now succeed
        await rl.check("t", "query")

    @pytest.mark.asyncio
    async def test_separate_buckets_per_token(self) -> None:
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=1))
        await rl.check("a", "query")
        # token "a" is now empty but "b" should still have a fresh bucket
        await rl.check("b", "query")

    @pytest.mark.asyncio
    async def test_separate_buckets_per_category(self) -> None:
        rl = RateLimiter(
            LimitsConfig(
                rate_limit_query_per_sec=1,
                rate_limit_read_per_sec=10,
            )
        )
        await rl.check("t", "query")
        # query is empty; read should still have its own bucket
        await rl.check("t", "read")
        await rl.check("t", "read")  # plenty of headroom


class TestRateLimitDisabled:
    @pytest.mark.asyncio
    async def test_zero_rate_disables(self) -> None:
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=0))
        # 100 calls should all pass since rate=0 means disabled
        for _ in range(100):
            result = await rl.check("t", "query")
            assert result == float("inf")


class TestRateLimitInternals:
    @pytest.mark.asyncio
    async def test_size_tracks_buckets(self) -> None:
        rl = RateLimiter(LimitsConfig())
        assert await rl.size() == 0
        await rl.check("a", "query")
        await rl.check("a", "read")
        await rl.check("b", "write")
        # 3 distinct (token, category) keys
        assert await rl.size() == 3

    @pytest.mark.asyncio
    async def test_reset_clears_buckets(self) -> None:
        rl = RateLimiter(LimitsConfig(rate_limit_query_per_sec=1))
        await rl.check("t", "query")
        assert await rl.size() == 1
        await rl.reset()
        assert await rl.size() == 0
        # Fresh bucket after reset
        await rl.check("t", "query")


class TestCategoryFor:
    def test_known_query_tools(self) -> None:
        for tool in [
            "execute_query",
            "execute_query_readonly",
            "execute_query_paginated",
            "fetch_next_page",
            "explain_query",
            "infer_schema",
        ]:
            assert category_for(tool) == "query"

    def test_known_write_tools(self) -> None:
        for tool in [
            "upsert_user",
            "delete_user",
            "create_link",
            "delete_link",
            "restart_service",
            "configure_auto_failover",
            "capella_create_cluster",
        ]:
            assert category_for(tool) == "write"

    def test_known_read_tools(self) -> None:
        for tool in [
            "list_users",
            "list_dataverses",
            "get_user",
            "who_am_i",
            "ping_cluster",
            "get_capabilities",
        ]:
            assert category_for(tool) == "read"

    def test_unknown_defaults_to_read(self) -> None:
        """Unknown tools shouldn't be silently allowed to bypass; default to 'read'."""
        assert category_for("future_tool_we_havent_invented_yet") == "read"

    def test_every_registered_tool_has_a_category(self) -> None:
        """Sanity: TOOL_CATEGORY should cover every actually-registered tool."""
        # We expect 55 tools total
        assert len(TOOL_CATEGORY) == 55


class TestRateLimitExceededAttributes:
    def test_exception_attrs(self) -> None:
        exc = RateLimitExceeded("query", 10, 0.5)
        assert exc.category == "query"
        assert exc.rate_per_sec == 10
        assert exc.retry_after_sec == 0.5
        # Message should be informative
        assert "rate limit" in str(exc).lower()
        assert "query" in str(exc)

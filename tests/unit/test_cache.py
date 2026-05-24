# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the in-process result cache and pagination state."""

from __future__ import annotations

import asyncio

import pytest

from cb_analytics_mcp.cache import PaginationState, ResultCache


class TestCacheBasics:
    @pytest.mark.asyncio
    async def test_set_and_get_round_trip(self) -> None:
        cache = ResultCache(default_ttl=60)
        await cache.set("k", {"data": 1})
        assert await cache.get("k") == {"data": 1}

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self) -> None:
        cache = ResultCache()
        assert await cache.get("nope") is None

    @pytest.mark.asyncio
    async def test_expiry_drops_entry(self) -> None:
        cache = ResultCache(default_ttl=60)
        # Insert with a TTL that's already past
        await cache.set("k", 1, ttl=-1)
        assert await cache.get("k") is None

    @pytest.mark.asyncio
    async def test_clear_removes_everything(self) -> None:
        cache = ResultCache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        assert await cache.size() == 2
        await cache.clear()
        assert await cache.size() == 0


class TestCacheKey:
    def test_deterministic(self) -> None:
        k1 = ResultCache.make_key("c1", "SELECT 1", {"a": 1}, [2], "request_plus")
        k2 = ResultCache.make_key("c1", "SELECT 1", {"a": 1}, [2], "request_plus")
        assert k1 == k2

    def test_different_clusters_differ(self) -> None:
        k1 = ResultCache.make_key("c1", "SELECT 1")
        k2 = ResultCache.make_key("c2", "SELECT 1")
        assert k1 != k2

    def test_dict_arg_ordering_is_normalised(self) -> None:
        k1 = ResultCache.make_key("c", "S", {"a": 1, "b": 2})
        k2 = ResultCache.make_key("c", "S", {"b": 2, "a": 1})
        assert k1 == k2

    def test_whitespace_around_statement_trimmed(self) -> None:
        k1 = ResultCache.make_key("c", "SELECT 1")
        k2 = ResultCache.make_key("c", "  SELECT 1  \n")
        assert k1 == k2


class TestEviction:
    @pytest.mark.asyncio
    async def test_eviction_when_over_capacity(self) -> None:
        cache = ResultCache(default_ttl=60, max_entries=3)
        # Insert in order so the soonest-expiring is "a"
        for i, key in enumerate(["a", "b", "c"]):
            await cache.set(key, i, ttl=10 + i)  # a expires first
        await cache.set("d", "new")  # should evict "a"
        assert await cache.size() == 3
        assert await cache.get("a") is None
        assert await cache.get("d") == "new"


class TestPagination:
    @pytest.mark.asyncio
    async def test_store_and_get(self) -> None:
        cache = ResultCache()
        handle = ResultCache.new_handle()
        state = PaginationState(
            cluster="default",
            statement="SELECT 1",
            named_args=None,
            positional_args=None,
            scan_consistency=None,
            timeout="60s",
            page_size=10,
        )
        await cache.store_pagination(handle, state)
        out = await cache.get_pagination(handle)
        assert out is state

    @pytest.mark.asyncio
    async def test_missing_handle_returns_none(self) -> None:
        cache = ResultCache()
        assert await cache.get_pagination("p_nope") is None

    @pytest.mark.asyncio
    async def test_drop_removes_state(self) -> None:
        cache = ResultCache()
        handle = ResultCache.new_handle()
        state = PaginationState(
            cluster="c",
            statement="S",
            named_args=None,
            positional_args=None,
            scan_consistency=None,
            timeout="60s",
            page_size=5,
        )
        await cache.store_pagination(handle, state)
        await cache.drop_pagination(handle)
        assert await cache.get_pagination(handle) is None

    def test_new_handles_unique(self) -> None:
        handles = {ResultCache.new_handle() for _ in range(100)}
        assert len(handles) == 100
        assert all(h.startswith("p_") for h in handles)


class TestConcurrentAccess:
    """Cache uses an asyncio lock — concurrent gets/sets should not corrupt state."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_do_not_lose_data(self) -> None:
        cache = ResultCache()

        async def writer(i: int) -> None:
            await cache.set(f"k{i}", i)

        await asyncio.gather(*(writer(i) for i in range(50)))
        for i in range(50):
            assert await cache.get(f"k{i}") == i

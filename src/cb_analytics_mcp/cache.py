# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
In-process result cache and pagination state.

Two purposes, one TTL store:

  - Caching: read-only query results are cached for `default_ttl` seconds
    keyed by (cluster, statement, args, scan_consistency). Saves the cluster
    from repeated identical queries during Claude's investigative loops.
  - Pagination: paginated queries store the *original* request alongside a
    growing offset so subsequent `fetch_next_page` calls can re-issue with
    LIMIT/OFFSET applied.

This is process-local and intentionally not Redis-backed. The MCP server
is a single process per deployment; the GUI shares it. If you scale out,
move pagination state to a real store, but cache invalidation across
processes for analytics workloads is rarely worth the complexity.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Entry:
    """One cache or pagination entry."""

    value: Any
    expires_at: float


@dataclass
class PaginationState:
    """Stored alongside a pagination handle to re-issue subsequent pages."""

    cluster: str
    statement: str
    named_args: dict[str, Any] | None
    positional_args: list[Any] | None
    scan_consistency: str | None
    timeout: str
    page_size: int
    next_offset: int = 0
    total_seen: int = 0
    # Cached page that the caller is currently looking at; lets fetch_more
    # be idempotent if called twice without a network round-trip.
    last_page: list[dict[str, Any]] = field(default_factory=list)
    last_page_offset: int = 0


class ResultCache:
    """
    TTL cache with explicit pagination handles.

    The cache is asyncio-aware (sweeps run in the event loop) and bounded
    in size — when the entry count exceeds `max_entries`, the oldest entry
    by expiry time is evicted.
    """

    def __init__(
        self,
        default_ttl: float = 60.0,
        max_entries: int = 256,
    ) -> None:
        self._cache: dict[str, _Entry] = {}
        self._pagination: dict[str, PaginationState] = {}
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl
        self.max_entries = max_entries

    # ── Query result caching ──────────────────────────────────────────────────

    @staticmethod
    def make_key(
        cluster: str,
        statement: str,
        named_args: dict[str, Any] | None = None,
        positional_args: list[Any] | None = None,
        scan_consistency: str | None = None,
    ) -> str:
        """Deterministic cache key for an identical-query lookup."""
        payload = {
            "c": cluster,
            "s": statement.strip(),
            "n": named_args or {},
            "p": positional_args or [],
            "sc": scan_consistency or "",
        }
        # Sort keys so dict order doesn't matter
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                self._cache.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        async with self._lock:
            expires_at = time.monotonic() + (ttl if ttl is not None else self.default_ttl)
            self._cache[key] = _Entry(value=value, expires_at=expires_at)
            self._evict_if_full()

    def _evict_if_full(self) -> None:
        """Drop the soonest-expiring entry when the cache overflows."""
        if len(self._cache) <= self.max_entries:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k].expires_at)
        self._cache.pop(oldest_key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._pagination.clear()

    async def size(self) -> int:
        async with self._lock:
            return len(self._cache)

    # ── Pagination state ──────────────────────────────────────────────────────

    @staticmethod
    def new_handle() -> str:
        """Return a unique, opaque pagination handle."""
        return "p_" + secrets.token_urlsafe(16)

    async def store_pagination(self, handle: str, state: PaginationState) -> None:
        async with self._lock:
            self._pagination[handle] = state
            # Pagination state is held longer than cache — 30 minutes
            # so a long analyst session doesn't lose its place.
            self._cache[f"_paginate:{handle}"] = _Entry(value=state, expires_at=time.monotonic() + 1800)
            self._evict_if_full()

    async def get_pagination(self, handle: str) -> PaginationState | None:
        async with self._lock:
            entry = self._cache.get(f"_paginate:{handle}")
            if entry is None or entry.expires_at < time.monotonic():
                self._cache.pop(f"_paginate:{handle}", None)
                self._pagination.pop(handle, None)
                return None
            state = self._pagination.get(handle)
            return state

    async def drop_pagination(self, handle: str) -> None:
        async with self._lock:
            self._pagination.pop(handle, None)
            self._cache.pop(f"_paginate:{handle}", None)

    async def pagination_count(self) -> int:
        async with self._lock:
            return len(self._pagination)

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Token-bucket rate limiter, asyncio-safe, in-process.

Buckets are keyed by `(token, category)` where category is one of:
  - "query"   : execute_query, execute_query_readonly, execute_query_paginated,
                fetch_next_page, explain_query
  - "read"    : any other read-only tool (list/get/who_am_i/etc.)
  - "write"   : tools that mutate cluster state (upsert/delete user, links,
                groups, cluster config, restart, capella mutations, etc.)

Rates are configurable via LimitsConfig. A rate of 0 disables the bucket
for that category. The bucket size equals the rate (i.e. 1-second burst).

Single-process design — if you scale this server horizontally you'll want
a shared store (Redis), but that's not in scope for v1.x.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal

from cb_analytics_mcp.config import LimitsConfig

Category = Literal["query", "read", "write"]


@dataclass
class _Bucket:
    """One token bucket. Tokens regenerate at `rate` per second up to `capacity`."""

    rate: float
    capacity: float
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class RateLimiter:
    """
    Token-bucket limiter, per (token, category).

    The token is a short string identifier — typically the MCP API key (or a
    derived prefix of it so we don't keep the full secret in memory). For the
    GUI's own calls we use "gui:<username>".

    `check(token, category)` raises RateLimitExceeded if no token is
    available; otherwise it consumes one and returns the bucket's current
    token count (useful for telemetry).
    """

    def __init__(self, limits: LimitsConfig) -> None:
        self._limits = limits
        self._buckets: dict[tuple[str, Category], _Bucket] = {}
        self._lock = asyncio.Lock()

    def _rate_for(self, category: Category) -> int:
        if category == "query":
            return self._limits.rate_limit_query_per_sec
        if category == "read":
            return self._limits.rate_limit_read_per_sec
        if category == "write":
            return self._limits.rate_limit_write_per_sec
        return 0

    async def check(self, token: str, category: Category) -> float:
        """
        Consume one token from the bucket for (token, category).

        Returns the remaining token count.
        Raises RateLimitExceeded if the bucket is empty.
        """
        rate = self._rate_for(category)
        if rate <= 0:
            return float("inf")  # disabled — always allow

        async with self._lock:
            key = (token, category)
            bucket = self._buckets.get(key)
            now = time.monotonic()
            if bucket is None:
                # First call from this key: fresh bucket, full
                bucket = _Bucket(rate=float(rate), capacity=float(rate), tokens=float(rate), last_refill=now)
                self._buckets[key] = bucket
            else:
                # Refill based on elapsed time
                elapsed = now - bucket.last_refill
                bucket.tokens = min(
                    bucket.capacity,
                    bucket.tokens + elapsed * bucket.rate,
                )
                bucket.last_refill = now

            if bucket.tokens < 1.0:
                # Compute when next token becomes available, for the error message
                wait = (1.0 - bucket.tokens) / bucket.rate
                raise RateLimitExceeded(
                    category=category,
                    rate_per_sec=rate,
                    retry_after_sec=round(wait, 3),
                )

            bucket.tokens -= 1.0
            return bucket.tokens

    async def reset(self) -> None:
        """Clear all bucket state. Mostly for tests."""
        async with self._lock:
            self._buckets.clear()

    async def size(self) -> int:
        """Number of active buckets."""
        async with self._lock:
            return len(self._buckets)


class RateLimitExceeded(Exception):
    """Raised when a token bucket is empty."""

    def __init__(self, category: Category, rate_per_sec: int, retry_after_sec: float) -> None:
        self.category = category
        self.rate_per_sec = rate_per_sec
        self.retry_after_sec = retry_after_sec
        super().__init__(
            f"Rate limit exceeded for category '{category}' "
            f"(limit {rate_per_sec}/sec). Retry in {retry_after_sec:.2f}s."
        )


# ── Tool-to-category map ─────────────────────────────────────────────────────


# Read-only tools that don't run a query are in "read". Tools that mutate
# anything are in "write". Anything in tools/query.py is "query".
TOOL_CATEGORY: dict[str, Category] = {
    # Meta — pure local lookups
    "list_clusters": "read",
    "get_capabilities": "read",
    # Schema — read-only
    "list_dataverses": "read",
    "list_datasets": "read",
    "infer_schema": "query",  # runs a SELECT, count it against query budget
    # Query
    "execute_query": "query",
    "execute_query_readonly": "query",
    "execute_query_paginated": "query",
    "fetch_next_page": "query",
    "explain_query": "query",
    # Admin — mix; status reads are "read", restarts/cancels are "write"
    "get_service_status": "read",
    "get_ingestion_status": "read",
    "get_active_requests": "read",
    "get_completed_requests": "read",
    "cancel_request": "write",
    "restart_service": "write",
    "restart_node": "write",
    # Config
    "get_service_config": "read",
    "update_service_config": "write",
    "get_analytics_settings": "read",
    "update_analytics_settings": "write",
    # Links
    "list_links": "read",
    "get_link": "read",
    "create_link": "write",
    "update_link": "write",
    "delete_link": "write",
    # Libraries
    "list_libraries": "read",
    "delete_library": "write",
    # Security
    "list_users": "read",
    "get_user": "read",
    "upsert_user": "write",
    "delete_user": "write",
    "list_groups": "read",
    "upsert_group": "write",
    "delete_group": "write",
    "list_roles": "read",
    "check_permissions": "read",
    # Cluster
    "ping_cluster": "read",
    "get_cluster_info": "read",
    "get_cluster_details": "read",
    "get_cluster_tasks": "read",
    "get_rebalance_progress": "read",
    "get_auto_failover_settings": "read",
    "configure_auto_failover": "write",
    "get_system_events": "read",
    "who_am_i": "read",
    # Capella
    "capella_list_organizations": "read",
    "capella_list_clusters": "read",
    "capella_get_cluster": "read",
    "capella_create_cluster": "write",
    "capella_delete_cluster": "write",
    "capella_list_backups": "read",
    "capella_create_backup": "write",
    "capella_restore_backup": "write",
    "capella_list_api_keys": "read",
}


def category_for(tool_name: str) -> Category:
    """Look up the rate-limit category for a tool. Defaults to 'read' for unknown."""
    return TOOL_CATEGORY.get(tool_name, "read")

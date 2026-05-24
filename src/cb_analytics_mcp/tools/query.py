# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""SQL++ query execution tools."""

from __future__ import annotations

import re
from typing import Any

from cb_analytics_mcp.cache import PaginationState, ResultCache
from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError
from cb_analytics_mcp.couchbase.models import AnalyticsQueryRequest, ScanConsistency
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_ok


def _coerce_scan_consistency(value: str | None) -> ScanConsistency:
    if not value:
        return ScanConsistency.NOT_BOUNDED
    return ScanConsistency(value.lower())


# Match a trailing LIMIT clause (with optional OFFSET) in case-insensitive form,
# allowing whitespace and the SQL++ semicolon terminator. We strip these out
# before injecting our own LIMIT/OFFSET for pagination.
_TRAILING_LIMIT_RE = re.compile(
    r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*;?\s*$",
    re.IGNORECASE,
)


def _strip_trailing_limit(statement: str) -> str:
    """Remove a trailing LIMIT/OFFSET clause so pagination can re-inject one."""
    return _TRAILING_LIMIT_RE.sub("", statement).rstrip().rstrip(";").rstrip()


async def execute_query_impl(
    pool: ClientPool,
    statement: str,
    named_args: dict[str, Any] | None = None,
    positional_args: list[Any] | None = None,
    scan_consistency: str | None = None,
    timeout: str = "120s",
    cluster: str | None = None,
    max_rows: int = 1000,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)
    req = AnalyticsQueryRequest(
        statement=statement,
        named_args=named_args,
        args=positional_args,
        scan_consistency=_coerce_scan_consistency(scan_consistency),
        timeout=timeout,
    )
    result = await client.analytics.execute(req)
    rows = result.results
    truncated = False
    full_count = len(rows)
    if max_rows > 0 and len(rows) > max_rows:
        rows = rows[:max_rows]
        truncated = True
    return fmt_ok(
        {
            "results": rows,
            "metrics": result.metrics.model_dump() if result.metrics else None,
            "warnings": [w.model_dump() for w in result.warnings],
            "request_id": result.requestID,
            "status": result.status,
            "truncated": truncated,
            "row_cap": max_rows if max_rows > 0 else None,
            "full_row_count": full_count,
        },
        cluster=name,
    )


async def execute_query_readonly_impl(
    pool: ClientPool,
    statement: str,
    scan_consistency: str | None = None,
    timeout: str = "120s",
    cluster: str | None = None,
    cache: ResultCache | None = None,
    max_rows: int = 1000,
) -> dict[str, Any]:
    name, client = pool.resolve(cluster)

    # Try cache first
    cache_key = None
    if cache is not None:
        cache_key = ResultCache.make_key(name, statement, None, None, scan_consistency)
        cached = await cache.get(cache_key)
        if cached is not None:
            # Deep-mark this as a cache hit. The original cached payload
            # has data.cached=False; flip it on the copy we return without
            # mutating the cached entry.
            cached_copy = dict(cached)
            cached_copy["data"] = dict(cached_copy.get("data", {}))
            cached_copy["data"]["cached"] = True
            return cached_copy

    req = AnalyticsQueryRequest(
        statement=statement,
        scan_consistency=_coerce_scan_consistency(scan_consistency),
        timeout=timeout,
        readonly=True,
    )
    result = await client.analytics.execute_readonly(req)
    rows = result.results
    truncated = False
    full_count = len(rows)
    if max_rows > 0 and len(rows) > max_rows:
        rows = rows[:max_rows]
        truncated = True
    payload = fmt_ok(
        {
            "results": rows,
            "metrics": result.metrics.model_dump() if result.metrics else None,
            "warnings": [w.model_dump() for w in result.warnings],
            "request_id": result.requestID,
            "status": result.status,
            "cached": False,
            "truncated": truncated,
            "row_cap": max_rows if max_rows > 0 else None,
            "full_row_count": full_count,
        },
        cluster=name,
    )
    if cache is not None and cache_key is not None:
        await cache.set(cache_key, payload)
    return payload


async def execute_query_paginated_impl(
    pool: ClientPool,
    statement: str,
    page_size: int = 100,
    named_args: dict[str, Any] | None = None,
    positional_args: list[Any] | None = None,
    scan_consistency: str | None = None,
    timeout: str = "120s",
    cluster: str | None = None,
    cache: ResultCache | None = None,
) -> dict[str, Any]:
    """
    Run a SELECT and return the first page plus a handle for subsequent pages.

    Pagination is server-side LIMIT/OFFSET rewriting — we strip any trailing
    LIMIT clause from the user's statement so our own pagination doesn't double
    up. The handle stores the original query parameters so fetch_next_page can
    re-issue with the next offset.
    """
    if page_size < 1 or page_size > 10_000:
        raise AnalyticsRequestError(
            f"page_size must be between 1 and 10000 (got {page_size})",
            status_code=400,
        )
    if cache is None:
        raise RuntimeError("execute_query_paginated requires a cache")

    name, client = pool.resolve(cluster)
    base_statement = _strip_trailing_limit(statement)
    paginated_stmt = f"{base_statement} LIMIT {page_size} OFFSET 0"

    req = AnalyticsQueryRequest(
        statement=paginated_stmt,
        named_args=named_args,
        args=positional_args,
        scan_consistency=_coerce_scan_consistency(scan_consistency),
        timeout=timeout,
        readonly=True,
    )
    result = await client.analytics.execute_readonly(req)

    handle = ResultCache.new_handle()
    state = PaginationState(
        cluster=name,
        statement=base_statement,
        named_args=named_args,
        positional_args=positional_args,
        scan_consistency=scan_consistency,
        timeout=timeout,
        page_size=page_size,
        next_offset=len(result.results),
        total_seen=len(result.results),
        last_page=list(result.results),
        last_page_offset=0,
    )
    await cache.store_pagination(handle, state)

    return fmt_ok(
        {
            "results": result.results,
            "metrics": result.metrics.model_dump() if result.metrics else None,
            "warnings": [w.model_dump() for w in result.warnings],
            "request_id": result.requestID,
            "status": result.status,
            "pagination_handle": handle,
            "page_size": page_size,
            "page_offset": 0,
            "rows_returned": len(result.results),
            "has_more": len(result.results) == page_size,
        },
        cluster=name,
    )


async def fetch_next_page_impl(
    pool: ClientPool,
    pagination_handle: str,
    cache: ResultCache | None = None,
) -> dict[str, Any]:
    """Fetch the next page for a handle returned by execute_query_paginated."""
    if cache is None:
        raise RuntimeError("fetch_next_page requires a cache")

    state = await cache.get_pagination(pagination_handle)
    if state is None:
        raise AnalyticsRequestError(
            f"Pagination handle '{pagination_handle}' not found or expired. "
            f"Call execute_query_paginated again to get a fresh handle.",
            status_code=404,
        )

    _name, client = pool.resolve(state.cluster)
    paginated_stmt = f"{state.statement} LIMIT {state.page_size} OFFSET {state.next_offset}"
    req = AnalyticsQueryRequest(
        statement=paginated_stmt,
        named_args=state.named_args,
        args=state.positional_args,
        scan_consistency=_coerce_scan_consistency(state.scan_consistency),
        timeout=state.timeout,
        readonly=True,
    )
    result = await client.analytics.execute_readonly(req)

    # Update state for the next call
    page_offset = state.next_offset
    rows_returned = len(result.results)
    state.last_page_offset = page_offset
    state.last_page = list(result.results)
    state.next_offset += rows_returned
    state.total_seen += rows_returned
    await cache.store_pagination(pagination_handle, state)

    has_more = rows_returned == state.page_size

    # When exhausted, drop the handle so the cache doesn't accumulate dead state
    if not has_more:
        await cache.drop_pagination(pagination_handle)

    return fmt_ok(
        {
            "results": result.results,
            "metrics": result.metrics.model_dump() if result.metrics else None,
            "warnings": [w.model_dump() for w in result.warnings],
            "request_id": result.requestID,
            "status": result.status,
            "pagination_handle": pagination_handle if has_more else None,
            "page_size": state.page_size,
            "page_offset": page_offset,
            "rows_returned": rows_returned,
            "total_seen": state.total_seen,
            "has_more": has_more,
        },
        cluster=state.cluster,
    )


async def explain_query_impl(
    pool: ClientPool,
    statement: str,
    cluster: str | None = None,
) -> dict[str, Any]:
    """
    Return the Couchbase Analytics query plan for the given statement.

    Uses the standard SQL++ EXPLAIN form. The plan is service-internal JSON;
    callers (or Claude) typically want it for cost analysis or to confirm
    that an index is being used.
    """
    name, client = pool.resolve(cluster)
    stripped = statement.strip().rstrip(";").rstrip()
    if not stripped:
        raise AnalyticsRequestError("statement is empty", status_code=400)

    # Avoid double-EXPLAIN if the user already wrote one
    if not stripped.upper().startswith("EXPLAIN "):
        stripped = "EXPLAIN " + stripped

    req = AnalyticsQueryRequest(statement=stripped, readonly=True)
    result = await client.analytics.execute_readonly(req)
    return fmt_ok(
        {
            "plan": result.results,
            "request_id": result.requestID,
            "status": result.status,
        },
        cluster=name,
    )


def register(
    mcp: Any,
    pool: ClientPool,
    audit: AuditLog,
    metrics: Metrics,
    cache: ResultCache | None = None,
    max_rows: int = 1000,
    rate_limiter: RateLimiter | None = None,
) -> None:
    @mcp.tool()
    async def execute_query(
        statement: str,
        named_args: dict[str, Any] | None = None,
        positional_args: list[Any] | None = None,
        scan_consistency: str | None = None,
        timeout: str = "120s",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a SQL++ statement on the Analytics service.

        Supports DML and DDL. For read-only queries that the service can
        optimise more aggressively, prefer execute_query_readonly. For
        large SELECTs, prefer execute_query_paginated.

        Responses include `truncated: true` and `full_row_count` if more
        rows were available than the server-side cap (default 1000 rows,
        tuned via MAX_QUERY_ROWS). When truncated, re-issue as paginated.
        """
        return await call_tool_observed(
            "execute_query",
            execute_query_impl,
            pool,
            statement,
            named_args,
            positional_args,
            scan_consistency,
            timeout,
            cluster,
            max_rows,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "statement": statement,
                "scan_consistency": scan_consistency,
                "timeout": timeout,
                "cluster": cluster,
            },
        )

    @mcp.tool()
    async def execute_query_readonly(
        statement: str,
        scan_consistency: str | None = None,
        timeout: str = "120s",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a read-only SQL++ SELECT.

        Cannot modify data; the service can apply additional optimisations.
        Results are cached for ~60 seconds keyed by (cluster, statement,
        scan_consistency), so repeated identical reads return immediately.
        Response includes a `cached` boolean.

        Responses also include `truncated: true` and `full_row_count` if more
        rows were available than the server-side cap (default 1000 rows,
        tuned via MAX_QUERY_ROWS). When truncated, re-issue as paginated.
        """
        return await call_tool_observed(
            "execute_query_readonly",
            execute_query_readonly_impl,
            pool,
            statement,
            scan_consistency,
            timeout,
            cluster,
            cache,
            max_rows,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "statement": statement,
                "scan_consistency": scan_consistency,
                "timeout": timeout,
                "cluster": cluster,
            },
        )

    @mcp.tool()
    async def execute_query_paginated(
        statement: str,
        page_size: int = 100,
        named_args: dict[str, Any] | None = None,
        positional_args: list[Any] | None = None,
        scan_consistency: str | None = None,
        timeout: str = "120s",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Run a SELECT and return the first page (default 100 rows) plus a
        pagination handle.

        Use fetch_next_page(handle) to retrieve subsequent pages. The handle
        expires after 30 minutes of inactivity. Use for any SELECT that might
        return more than a few thousand rows — sending the full result through
        the MCP boundary is expensive and the LLM doesn't benefit from seeing
        more than the first few hundred anyway.

        Pagination is implemented via server-side LIMIT/OFFSET. A trailing
        LIMIT/OFFSET clause on your statement will be stripped so the
        pagination is applied cleanly.
        """
        return await call_tool_observed(
            "execute_query_paginated",
            execute_query_paginated_impl,
            pool,
            statement,
            page_size,
            named_args,
            positional_args,
            scan_consistency,
            timeout,
            cluster,
            cache,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={
                "statement": statement,
                "page_size": page_size,
                "scan_consistency": scan_consistency,
                "timeout": timeout,
                "cluster": cluster,
            },
        )

    @mcp.tool()
    async def fetch_next_page(pagination_handle: str) -> dict[str, Any]:
        """
        Fetch the next page of a previously paginated query.

        Returns rows plus a new `has_more` flag. When `has_more` is false the
        handle is dropped automatically.
        """
        return await call_tool_observed(
            "fetch_next_page",
            fetch_next_page_impl,
            pool,
            pagination_handle,
            cache,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"pagination_handle": pagination_handle},
        )

    @mcp.tool()
    async def explain_query(
        statement: str,
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """
        Return the query plan (EXPLAIN output) for a SQL++ statement.

        Use this to investigate slow queries: the plan shows scan/filter/join
        order and confirms whether an index is being used. The plan format
        is service-internal but generally readable. Pass either a plain SELECT
        (Claude will prepend EXPLAIN) or a statement already starting with
        EXPLAIN.
        """
        return await call_tool_observed(
            "explain_query",
            explain_query_impl,
            pool,
            statement,
            cluster,
            audit=audit,
            metrics=metrics,
            rate_limiter=rate_limiter,
            tool_args={"statement": statement, "cluster": cluster},
        )

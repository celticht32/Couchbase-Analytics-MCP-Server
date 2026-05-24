# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Shared helpers used by every tool module.

The general pattern:

- A tool function is wrapped to format any AnalyticsError consistently as
  a dict the model can read. Any other exception is converted to the same
  shape so the conversation never crashes.
- Every tool invocation gets timed, audited, and counted.
- Optional rate-limiting per (client_id, tool category).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from cb_analytics_mcp.couchbase import AnalyticsError
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.rate_limit import RateLimiter, RateLimitExceeded, category_for

log = structlog.get_logger(__name__)


def fmt_error(exc: Exception) -> dict[str, Any]:
    """Convert an exception to a uniform error dict for MCP responses."""
    err_type = type(exc).__name__
    payload: dict[str, Any] = {
        "ok": False,
        "error": err_type,
        "message": str(exc),
    }
    # Surface status_code / code when present
    for attr in ("status_code", "code", "line", "column", "retry_after_sec", "category", "rate_per_sec"):
        value = getattr(exc, attr, None)
        if value is not None:
            payload[attr] = value
    return payload


def fmt_ok(data: Any, **extra: Any) -> dict[str, Any]:
    """Format a successful tool result with `ok: True`."""
    out: dict[str, Any] = {"ok": True, "data": data}
    out.update(extra)
    return out


async def call_tool_observed(
    name: str,
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    audit: AuditLog | None = None,
    metrics: Metrics | None = None,
    client_id: str | None = None,
    tool_args: dict[str, Any] | None = None,
    rate_limiter: RateLimiter | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Run a tool implementation with logging, audit, metrics, and (optional)
    rate-limiting.

    Returns the formatted result dict (success or error), never raises.
    Rate-limit errors are surfaced as fmt_error with a `retry_after_sec`
    field so callers (and Claude) can back off.
    """
    log.debug("tool_invoke", tool=name, args=tool_args or {})
    start = time.monotonic()

    summary: dict[str, Any] = {}
    error_str: str | None = None
    success = True

    # ── Rate limit check (cheap, in-memory token bucket) ────────────────────
    if rate_limiter is not None:
        try:
            token = client_id or "anonymous"
            await rate_limiter.check(token, category_for(name))
        except RateLimitExceeded as e:
            log.warning(
                "tool_rate_limited",
                tool=name,
                category=e.category,
                rate_per_sec=e.rate_per_sec,
                client_id=client_id,
            )
            if metrics:
                metrics.tool_invocations.labels(tool=name, outcome="rate_limited").inc()
            if audit:
                audit.record(
                    tool_name=name,
                    args=tool_args,
                    result_summary={"rate_limited": True},
                    duration_ms=0.0,
                    client_id=client_id,
                    success=False,
                    error="RateLimitExceeded",
                )
            return fmt_error(e)

    try:
        result = await func(*args, **kwargs)
        if isinstance(result, dict) and result.get("ok") is False:
            success = False
            error_str = str(result.get("error"))
        if isinstance(result, dict) and "data" in result:
            data_part = result["data"]
            if isinstance(data_part, list):
                summary["result_count"] = len(data_part)
            elif isinstance(data_part, dict):
                summary["result_keys"] = list(data_part.keys())[:8]
        return result if isinstance(result, dict) else fmt_ok(result)
    except AnalyticsError as e:
        success = False
        error_str = type(e).__name__
        return fmt_error(e)
    except Exception as e:
        success = False
        error_str = type(e).__name__
        log.exception("tool_unexpected_error", tool=name)
        return fmt_error(e)
    finally:
        duration_s = time.monotonic() - start
        if metrics:
            outcome = "success" if success else "error"
            metrics.tool_invocations.labels(tool=name, outcome=outcome).inc()
            metrics.tool_duration.labels(tool=name).observe(duration_s)
        if audit:
            audit.record(
                tool_name=name,
                args=tool_args,
                result_summary=summary,
                duration_ms=duration_s * 1000.0,
                client_id=client_id,
                success=success,
                error=error_str,
            )

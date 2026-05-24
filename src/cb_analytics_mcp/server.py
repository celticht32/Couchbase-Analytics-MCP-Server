# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
The MCP server itself.

Wires the configuration, client pool, observability stack, and all tool
modules into a single FastMCP instance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from cb_analytics_mcp.auth import ApiKeyVerifier
from cb_analytics_mcp.cache import ResultCache
from cb_analytics_mcp.config import AppConfig, config_summary
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.logging import configure_logging
from cb_analytics_mcp.observability.metrics import Metrics, start_metrics_server
from cb_analytics_mcp.observability.tracing import configure_tracing
from cb_analytics_mcp.pool import ClientPool
from cb_analytics_mcp.rate_limit import RateLimiter
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

log = structlog.get_logger(__name__)


def build_server(cfg: AppConfig) -> tuple[FastMCP[Any], ClientPool, Metrics, AuditLog]:
    """
    Build a fully wired-up MCP server.

    Returns (mcp, pool, metrics, audit) so the caller can run the server
    and shut down cleanly.
    """
    # Observability ──────────────────────────────────────────────────────────
    configure_logging(
        level=cfg.observability.log_level,
        fmt=cfg.observability.log_format,
        log_file=cfg.observability.log_file,
    )
    configure_tracing(
        enabled=cfg.observability.otel_enabled,
        endpoint=cfg.observability.otel_endpoint,
        service_name=cfg.observability.otel_service_name,
    )
    metrics = Metrics()
    audit = AuditLog(
        enabled=cfg.observability.audit_log_enabled,
        log_file=cfg.observability.audit_log_file,
        rotate_bytes=cfg.limits.audit_rotate_bytes,
        rotate_keep=cfg.limits.audit_rotate_keep,
    )

    if cfg.observability.metrics_enabled:
        start_metrics_server(cfg.observability.metrics_port, metrics.registry)

    log.info("server_starting", config=config_summary(cfg))

    # Pool, cache, rate limiter ─────────────────────────────────────────────
    pool = ClientPool()
    cache = ResultCache()
    rate_limiter = RateLimiter(cfg.limits)

    # Lifespan ───────────────────────────────────────────────────────────────
    @asynccontextmanager
    async def lifespan(_: FastMCP[Any]) -> AsyncIterator[None]:
        await pool.startup(cfg)
        metrics.clusters_configured.set(len(pool.cluster_names))
        log.info("server_ready", clusters=pool.cluster_names)
        try:
            yield
        finally:
            log.info("server_shutting_down")
            await pool.shutdown()

    # Build the FastMCP instance ─────────────────────────────────────────────
    verifier = ApiKeyVerifier(api_key=cfg.mcp_api_key)
    from pydantic import AnyHttpUrl, TypeAdapter

    _url = TypeAdapter(AnyHttpUrl)
    auth_settings = AuthSettings(
        issuer_url=_url.validate_python(cfg.mcp_issuer_url),
        resource_server_url=_url.validate_python(cfg.mcp_server_url),
    )

    mcp: FastMCP[Any] = FastMCP(
        name="cb-analytics-mcp",
        instructions="MCP server for Couchbase Enterprise Analytics and Capella Analytics.",
        host=cfg.mcp_host,
        port=cfg.mcp_port,
        token_verifier=verifier,
        auth=auth_settings,
        lifespan=lifespan,
        log_level=cfg.observability.log_level,  # type: ignore[arg-type]
    )

    # Register all tool groups ───────────────────────────────────────────────
    meta.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    schema.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    query.register(
        mcp,
        pool,
        audit,
        metrics,
        cache=cache,
        max_rows=cfg.limits.max_query_rows,
        rate_limiter=rate_limiter,
    )
    admin.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    config_tools.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    links.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    libraries.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    security.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    cluster.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)
    capella.register(mcp, pool, audit, metrics, rate_limiter=rate_limiter)

    return mcp, pool, metrics, audit

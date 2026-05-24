# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
FastAPI app for the GUI.

This module creates a FastAPI app, mounts static files, configures session
middleware, and registers the per-page routes. The app can run standalone
(via `run_gui_blocking`) or alongside the MCP server (via `run_gui`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from cb_analytics_mcp.config import AppConfig
from cb_analytics_mcp.gui.routes import admin, auth, dashboard, health, logs, query
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.pool import ClientPool

log = structlog.get_logger(__name__)

GUI_ROOT = Path(__file__).parent
TEMPLATES_DIR = GUI_ROOT / "templates"
STATIC_DIR = GUI_ROOT / "static"


def build_app(
    cfg: AppConfig,
    pool: ClientPool | None = None,
    audit: AuditLog | None = None,
    metrics: Metrics | None = None,
) -> FastAPI:
    """
    Build the FastAPI app.

    If pool/audit/metrics are not supplied, a new ClientPool is created in
    the app's lifespan (standalone GUI mode).
    """
    owns_pool = pool is None
    if pool is None:
        pool = ClientPool()
    if audit is None:
        audit = AuditLog(
            enabled=cfg.observability.audit_log_enabled,
            log_file=cfg.observability.audit_log_file,
        )
    if metrics is None:
        metrics = Metrics()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if owns_pool:
            await pool.startup(cfg)
        try:
            yield
        finally:
            if owns_pool:
                await pool.shutdown()

    app = FastAPI(
        title="cb-analytics-mcp GUI",
        version="1.0.0",
        docs_url=None,  # disable Swagger UI — this is an admin app, not an API
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=cfg.gui.session_secret.get_secret_value(),
        session_cookie="cb_analytics_session",
        max_age=60 * 60 * 8,  # 8 hours
        same_site="lax",
        https_only=False,  # set True when behind TLS reverse proxy
    )

    # Mount static files (Tailwind via CDN; htmx via CDN; minimal local CSS/JS)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    # Pass things every template needs
    templates.env.globals["app_version"] = "1.0.0"
    templates.env.globals["app_title"] = "cb-analytics-mcp"

    # Attach shared state to app.state so route handlers can access it
    app.state.cfg = cfg
    app.state.pool = pool
    app.state.audit = audit
    app.state.metrics = metrics
    app.state.templates = templates

    # Register route groups
    app.include_router(health.router)  # /healthz and /readyz — unauthenticated
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(query.router)
    app.include_router(admin.router)
    app.include_router(logs.router)

    log.info(
        "gui_app_built",
        templates=str(TEMPLATES_DIR),
        static=str(STATIC_DIR),
    )
    return app


# ── Runners ────────────────────────────────────────────────────────────────────


async def run_gui(cfg: AppConfig) -> None:
    """Run the GUI in the current asyncio event loop (alongside the MCP server)."""
    import uvicorn

    app = build_app(cfg)
    config = uvicorn.Config(
        app,
        host=cfg.gui.host,
        port=cfg.gui.port,
        log_level=cfg.observability.log_level.lower(),
        log_config=None,  # don't fight our structlog setup
    )
    server = uvicorn.Server(config)
    await server.serve()


def run_gui_blocking(cfg: AppConfig) -> None:
    """Run the GUI in the foreground (no MCP server)."""
    import uvicorn

    from cb_analytics_mcp.observability.logging import configure_logging

    configure_logging(
        level=cfg.observability.log_level,
        fmt=cfg.observability.log_format,
        log_file=cfg.observability.log_file,
    )

    app = build_app(cfg)
    uvicorn.run(
        app,
        host=cfg.gui.host,
        port=cfg.gui.port,
        log_config=None,
    )

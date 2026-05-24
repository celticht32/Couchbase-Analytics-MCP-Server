# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Dashboard route — server health, cluster overview, recent activity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from cb_analytics_mcp.gui.routes.auth import require_session

log = structlog.get_logger(__name__)
router = APIRouter()


def _read_recent_audit_records(path: Path, n: int = 10) -> list[dict[str, Any]]:
    """Read the last n audit records. Best-effort, never raises."""
    if not path.is_file():
        return []
    try:
        # Read whole file (audit log shouldn't be huge in dev; rotation handles prod)
        lines = path.read_text().splitlines()[-n:]
        out: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(out))  # newest first
    except OSError:
        return []


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    _user: str = Depends(require_session),
) -> Response:
    cfg = request.app.state.cfg
    pool = request.app.state.pool
    templates = request.app.state.templates

    # Cluster reachability snapshot (parallel pings would be nicer; keep it simple)
    clusters: list[dict[str, Any]] = []
    for name in pool.cluster_names:
        try:
            client = pool.get(name)
            reachable = await client.ping()
        except Exception as e:
            reachable = False
            log.warning("dashboard_ping_failed", cluster=name, error=str(e))
        clusters.append(
            {
                "name": name,
                "host": client.cfg.host if reachable else getattr(client.cfg, "host", "?"),
                "reachable": reachable,
                "tls": client.cfg.tls,
            }
        )

    audit_records = _read_recent_audit_records(Path(cfg.observability.audit_log_file))

    context = {
        "user": _user,
        "clusters": clusters,
        "capella_enabled": pool.has_capella,
        "audit_records": audit_records,
        "audit_enabled": cfg.observability.audit_log_enabled,
        "log_level": cfg.observability.log_level,
        "metrics_enabled": cfg.observability.metrics_enabled,
        "metrics_port": cfg.observability.metrics_port,
        "otel_enabled": cfg.observability.otel_enabled,
        "mcp_port": cfg.mcp_port,
        "gui_port": cfg.gui.port,
    }
    return cast(Response, templates.TemplateResponse(request, "dashboard.html", context))


@router.post("/cluster/{name}/test", response_class=HTMLResponse)
async def cluster_test(
    request: Request,
    name: str,
    _user: str = Depends(require_session),
) -> Response:
    """
    HTMX endpoint: ping the cluster and return an inline result fragment.

    Used by the Test button on each cluster row. Returns an HTML span that
    the row swaps in place of the button.
    """
    pool = request.app.state.pool
    try:
        client = pool.get(name)
    except (KeyError, ValueError):
        return HTMLResponse(
            f'<span class="text-xs text-red-600">unknown cluster: {name}</span>',
            status_code=404,
        )

    import time

    start = time.monotonic()
    try:
        ok = await client.ping()
        elapsed_ms = (time.monotonic() - start) * 1000
        if ok:
            return HTMLResponse(
                f'<span class="inline-flex items-center gap-1 text-xs text-green-700">'
                f'<span class="h-1.5 w-1.5 rounded-full bg-green-500"></span> '
                f"reachable in {elapsed_ms:.0f} ms</span>"
            )
        return HTMLResponse(
            '<span class="inline-flex items-center gap-1 text-xs text-red-700">'
            '<span class="h-1.5 w-1.5 rounded-full bg-red-500"></span> '
            "ping returned false</span>"
        )
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        log.warning("cluster_test_failed", cluster=name, error=str(e))
        # Truncate long errors so the row layout doesn't break
        err = str(e)[:80]
        return HTMLResponse(
            f'<span class="inline-flex items-center gap-1 text-xs text-red-700">'
            f'<span class="h-1.5 w-1.5 rounded-full bg-red-500"></span> '
            f"failed after {elapsed_ms:.0f} ms: {err}</span>"
        )

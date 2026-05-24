# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Health endpoints — unauthenticated, lightweight, suitable for
load balancers, Docker HEALTHCHECK, and Kubernetes probes.

  /healthz   liveness: server is responsive (always 200 if the process is up)
  /readyz    readiness: at least one configured cluster pings successfully

Both endpoints return a small JSON body so curl + jq style probes work.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/healthz")
async def healthz() -> Response:
    """Liveness probe — fast, never touches the cluster."""
    return JSONResponse({"status": "ok"})


@router.get("/readyz")
async def readyz(request: Request) -> Response:
    """
    Readiness probe — returns 200 only if at least one configured cluster is
    reachable (or if no clusters are configured but the process is otherwise
    healthy).

    The response body lists every cluster's reachability so operators can
    diagnose without checking the dashboard.
    """
    pool = request.app.state.pool

    if pool.is_empty:
        return JSONResponse({"status": "ok", "clusters": [], "note": "no clusters configured"})

    cluster_states: list[dict[str, Any]] = []
    any_reachable = False
    for name in pool.cluster_names:
        try:
            client = pool.get(name)
            reachable = await client.ping()
        except Exception as exc:
            reachable = False
            log.warning("readyz_ping_failed", cluster=name, error=str(exc))
        cluster_states.append({"name": name, "reachable": reachable})
        any_reachable = any_reachable or reachable

    status_code = status.HTTP_200_OK if any_reachable else status.HTTP_503_SERVICE_UNAVAILABLE
    overall = "ok" if any_reachable else "unavailable"
    return JSONResponse(
        {"status": overall, "clusters": cluster_states},
        status_code=status_code,
    )

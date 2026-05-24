# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""SQL++ query editor route."""

from __future__ import annotations

import json
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from cb_analytics_mcp.couchbase import AnalyticsError
from cb_analytics_mcp.couchbase.models import AnalyticsQueryRequest, ScanConsistency
from cb_analytics_mcp.gui.routes.auth import require_session

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/query", response_class=HTMLResponse)
async def query_page(
    request: Request,
    _user: str = Depends(require_session),
) -> Response:
    templates = request.app.state.templates
    pool = request.app.state.pool
    return cast(
        Response,
        templates.TemplateResponse(
            request,
            "query.html",
            {
                "user": _user,
                "clusters": pool.cluster_names,
                "default_cluster": pool.default_name() if not pool.is_empty else None,
            },
        ),
    )


@router.post("/query/run", response_class=HTMLResponse)
async def query_run(
    request: Request,
    _user: str = Depends(require_session),
    statement: str = Form(...),
    cluster: str = Form(""),
    scan_consistency: str = Form("not_bounded"),
    timeout: str = Form("120s"),
) -> Response:
    """
    Execute a SQL++ statement and return an HTMX fragment with the results.
    """
    templates = request.app.state.templates
    pool = request.app.state.pool

    cluster_name = cluster or (pool.default_name() if not pool.is_empty else "")
    if not cluster_name:
        return cast(
            Response,
            templates.TemplateResponse(
                request,
                "_query_result.html",
                {
                    "ok": False,
                    "error": "No clusters configured",
                    "message": "Configure a Couchbase cluster before running queries.",
                    "cluster": "",
                    "statement": statement,
                },
            ),
        )

    try:
        client = pool.get(cluster_name)
    except ValueError as e:
        return cast(
            Response,
            templates.TemplateResponse(
                request,
                "_query_result.html",
                {
                    "ok": False,
                    "error": "UnknownCluster",
                    "message": str(e),
                    "cluster": cluster_name,
                    "statement": statement,
                },
            ),
        )

    req = AnalyticsQueryRequest(
        statement=statement,
        scan_consistency=ScanConsistency(scan_consistency),
        timeout=timeout,
    )
    try:
        response = await client.analytics.execute(req)
        context: dict[str, Any] = {
            "ok": True,
            "cluster": cluster_name,
            "statement": statement,
            "request_id": response.requestID,
            "status": response.status,
            "results_json": json.dumps(response.results, indent=2, default=str),
            "result_count": len(response.results),
            "metrics": response.metrics.model_dump() if response.metrics else None,
            "warnings": [w.model_dump() for w in response.warnings],
        }
    except AnalyticsError as e:
        log.info("query_failed", error=type(e).__name__, message=str(e))
        context = {
            "ok": False,
            "cluster": cluster_name,
            "statement": statement,
            "error": type(e).__name__,
            "message": str(e),
        }

    return cast(
        Response,
        templates.TemplateResponse(request, "_query_result.html", context),
    )

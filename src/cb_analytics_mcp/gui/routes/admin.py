# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Admin route — audit log viewer and config summary."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from cb_analytics_mcp.config import config_summary
from cb_analytics_mcp.gui.routes.auth import require_session
from cb_analytics_mcp.rate_limit import TOOL_CATEGORY

log = structlog.get_logger(__name__)
router = APIRouter()


def _parse_filter_date(s: str | None, end_of_day: bool = False) -> datetime | None:
    """Parse a date string from the GUI filter form (YYYY-MM-DD or ISO datetime).

    When `end_of_day` is True and the input is date-only (no time component
    supplied by the user), returns the very last moment of that day so the
    filter is inclusive — a user entering "to_date=2026-05-22" expects
    records from all of that day, not only midnight.
    """
    if not s:
        return None
    s = s.strip()
    if not s:
        return None

    # date-only input: 10 chars matching YYYY-MM-DD
    date_only = len(s) == 10 and s[4] == "-" and s[7] == "-"

    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None

    if dt is not None and date_only and end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def _record_in_range(
    rec: dict[str, Any],
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> bool:
    """Return True iff rec.timestamp falls in [from_dt, to_dt] (both inclusive)."""
    if from_dt is None and to_dt is None:
        return True
    ts = rec.get("timestamp")
    if not isinstance(ts, str):
        return False
    try:
        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    # Audit timestamps are timezone-aware (UTC); make filter bounds match.
    if from_dt is not None and from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=rec_dt.tzinfo)
    if to_dt is not None and to_dt.tzinfo is None:
        to_dt = to_dt.replace(tzinfo=rec_dt.tzinfo)
    if from_dt is not None and rec_dt < from_dt:
        return False
    if to_dt is not None and rec_dt > to_dt:
        return False
    return True


def _read_audit_records(
    path: Path,
    limit: int = 200,
    tool_filter: str | None = None,
    only_failures: bool = False,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []

    records: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if tool_filter and rec.get("tool") != tool_filter:
            continue
        if only_failures and rec.get("success", True):
            continue
        if not _record_in_range(rec, from_dt, to_dt):
            continue
        records.append(rec)
        if len(records) >= limit:
            break
    return records


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    _user: str = Depends(require_session),
    tool: str | None = None,
    failures_only: bool = False,
    from_date: str | None = None,
    to_date: str | None = None,
) -> Response:
    cfg = request.app.state.cfg
    templates = request.app.state.templates

    summary = config_summary(cfg)
    from_dt = _parse_filter_date(from_date)
    to_dt = _parse_filter_date(to_date, end_of_day=True)
    records = _read_audit_records(
        Path(cfg.observability.audit_log_file),
        limit=200,
        tool_filter=tool,
        only_failures=failures_only,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    # Build a master list of tools known to the server (all tools registered,
    # not just those that appear in the audit log so far). Sorted for a stable
    # dropdown.
    all_tools = sorted(TOOL_CATEGORY.keys())

    return cast(
        Response,
        templates.TemplateResponse(
            request,
            "admin.html",
            {
                "user": _user,
                "config_summary": json.dumps(summary, indent=2, default=str),
                "audit_records": records,
                "audit_enabled": cfg.observability.audit_log_enabled,
                "audit_file": cfg.observability.audit_log_file,
                "tool_names": all_tools,
                "current_tool_filter": tool,
                "current_failures_only": failures_only,
                "current_from_date": from_date or "",
                "current_to_date": to_date or "",
            },
        ),
    )


@router.get("/admin/audit-fragment", response_class=HTMLResponse)
async def admin_audit_fragment(
    request: Request,
    _user: str = Depends(require_session),
    tool: str | None = None,
    failures_only: bool = False,
    from_date: str | None = None,
    to_date: str | None = None,
) -> Response:
    """
    HTMX endpoint: returns just the audit-table fragment.

    Used by the filter form so updating the search doesn't reload the whole
    admin page. Identical filter semantics to the full admin page.
    """
    cfg = request.app.state.cfg
    templates = request.app.state.templates

    from_dt = _parse_filter_date(from_date)
    to_dt = _parse_filter_date(to_date, end_of_day=True)
    records = _read_audit_records(
        Path(cfg.observability.audit_log_file),
        limit=200,
        tool_filter=tool,
        only_failures=failures_only,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    return cast(
        Response,
        templates.TemplateResponse(
            request,
            "_audit_table.html",
            {"audit_records": records},
        ),
    )

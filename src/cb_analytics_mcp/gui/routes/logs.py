# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Live log tail — HTMX polling endpoint plus WebSocket push."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from cb_analytics_mcp.gui.routes.auth import require_session, require_session_ws

log = structlog.get_logger(__name__)
router = APIRouter()

# Reading more than this risks blocking the loop on big files; the tail
# endpoint reads only the tail of the file via seek.
_TAIL_BYTES = 64 * 1024

# WebSocket settings
_WS_POLL_INTERVAL = 0.5  # seconds between file-size polls
_WS_MAX_LINES_PER_TICK = 100  # safety cap so a log flood doesn't OOM the WS


def _read_tail_lines(path: Path, max_lines: int = 100) -> list[str]:
    """Read the last `max_lines` lines from the tail of a (possibly large) file."""
    if not path.is_file():
        return []
    try:
        size = path.stat().st_size
        start = max(0, size - _TAIL_BYTES)
        with path.open("rb") as fh:
            fh.seek(start)
            data = fh.read()
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if start > 0 and lines:
            lines = lines[1:]  # drop possibly-truncated first line
        return lines[-max_lines:]
    except OSError:
        return []


def _parse_records(lines: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
            if isinstance(rec, dict):
                out.append(rec)
                continue
        except json.JSONDecodeError:
            pass
        # Console-format line — store as plain text
        out.append({"event": raw, "level": "info", "timestamp": ""})
    return list(reversed(out))  # newest first


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    _user: str = Depends(require_session),
) -> Response:
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    log_file = cfg.observability.log_file or ""
    return cast(
        Response,
        templates.TemplateResponse(
            request,
            "logs.html",
            {"user": _user, "log_file": log_file, "log_file_set": bool(log_file)},
        ),
    )


@router.get("/logs/tail", response_class=HTMLResponse)
async def logs_tail(
    request: Request,
    _user: str = Depends(require_session),
    lines: int = 100,
) -> Response:
    """HTMX-polled endpoint that returns the most recent N lines."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    path = Path(cfg.observability.log_file) if cfg.observability.log_file else None

    if path is None:
        return cast(
            Response,
            templates.TemplateResponse(
                request,
                "_log_lines.html",
                {
                    "records": [],
                    "note": (
                        "LOG_FILE is not configured. Set the env var to a writable "
                        "path to enable live log tailing in the GUI."
                    ),
                },
            ),
        )

    raw_lines = _read_tail_lines(path, max_lines=max(10, min(lines, 500)))
    return cast(
        Response,
        templates.TemplateResponse(
            request,
            "_log_lines.html",
            {"records": _parse_records(raw_lines), "note": None, "pid": os.getpid()},
        ),
    )


# ── WebSocket live tail ───────────────────────────────────────────────────────


async def _tail_file_to_websocket(websocket: WebSocket, path: Path) -> None:
    """
    Open `path`, send the current tail, then poll for new bytes and send them
    as they arrive. Closes cleanly when the client disconnects or the file
    becomes unreadable.

    Uses simple size-based polling rather than inotify so the code is portable
    across Linux/macOS/Windows. Polling interval is `_WS_POLL_INTERVAL` which
    is fast enough to feel live but slow enough not to burn CPU.
    """
    try:
        # Send the existing tail first so the client has context
        initial = _read_tail_lines(path, max_lines=50)
        for line in initial:
            await _send_line(websocket, line)

        # Now follow the file
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            while True:
                # Detect truncation (log rotation): if file is smaller than
                # our position, seek to the start.
                try:
                    current_size = path.stat().st_size
                except FileNotFoundError:
                    await asyncio.sleep(_WS_POLL_INTERVAL)
                    continue

                pos = fh.tell()
                if current_size < pos:
                    # File was rotated/truncated — restart at top of new file
                    fh.close()
                    fh = path.open("rb")
                    pos = 0

                new_bytes = fh.read()
                if new_bytes:
                    text = new_bytes.decode("utf-8", errors="replace")
                    # Don't drown the socket — cap per-tick output
                    new_lines = [line for line in text.splitlines() if line.strip()][:_WS_MAX_LINES_PER_TICK]
                    for line in new_lines:
                        await _send_line(websocket, line)
                else:
                    await asyncio.sleep(_WS_POLL_INTERVAL)

    except WebSocketDisconnect:
        log.debug("logs_ws_client_disconnected")
    except Exception as exc:
        log.warning("logs_ws_error", error=str(exc))
        # Best-effort error notification — if even this fails, log and give up.
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"log stream ended: {exc}",
                }
            )
        except Exception as send_exc:
            log.debug("logs_ws_send_error_failed", error=str(send_exc))


async def _send_line(websocket: WebSocket, raw_line: str) -> None:
    """Parse one log line and send as a JSON record on the socket."""
    raw_line = raw_line.strip()
    if not raw_line:
        return
    try:
        rec = json.loads(raw_line)
        if not isinstance(rec, dict):
            rec = {"event": raw_line, "level": "info", "timestamp": ""}
    except json.JSONDecodeError:
        # Console-format line — wrap it as a record so the client can render it
        rec = {"event": raw_line, "level": "info", "timestamp": ""}
    await websocket.send_json({"type": "log", "record": rec})


@router.websocket("/logs/ws")
async def logs_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint that streams new log lines as they're written.

    Auth is enforced via the same session cookie the rest of the GUI uses.
    Falls back gracefully if no LOG_FILE is configured (sends an error frame
    and closes).
    """
    # Accept BEFORE auth check so we can use send_json/close cleanly
    await websocket.accept()

    user = await require_session_ws(websocket)
    if user is None:
        return

    cfg = websocket.app.state.cfg
    log_file = cfg.observability.log_file
    if not log_file:
        await websocket.send_json(
            {
                "type": "error",
                "message": (
                    "LOG_FILE is not configured. WebSocket tail requires writing "
                    "logs to a file. The HTMX-polling /logs/tail endpoint also "
                    "needs this."
                ),
            }
        )
        await websocket.close()
        return

    path = Path(log_file)
    if not path.is_file():
        await websocket.send_json(
            {
                "type": "error",
                "message": f"LOG_FILE does not exist: {log_file}",
            }
        )
        await websocket.close()
        return

    log.info("logs_ws_connected", user=user, path=str(path))
    await websocket.send_json({"type": "hello", "pid": os.getpid(), "path": str(path)})
    await _tail_file_to_websocket(websocket, path)

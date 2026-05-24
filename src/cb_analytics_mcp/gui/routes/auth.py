# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Login, logout, and session helpers."""

from __future__ import annotations

import hmac
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response

log = structlog.get_logger(__name__)

router = APIRouter()


# ── Dependency: require an authenticated session ──────────────────────────────


def require_session(request: Request) -> str:
    """Raise 303 redirect to /login if not authenticated; return username otherwise."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return cast(str, user)


async def require_session_ws(websocket: Any) -> str | None:
    """
    Authenticate a WebSocket using the session cookie.

    Returns the username if the session is valid; otherwise closes the socket
    with code 1008 (policy violation) and returns None. The caller should
    `return` immediately if this returns None.
    """
    user = websocket.session.get("user")
    if not user:
        # 1008 = policy violation; browsers surface this as a clean close
        await websocket.close(code=1008, reason="unauthenticated")
        return None
    return cast(str, user)


def get_templates(request: Request) -> Any:
    return request.app.state.templates


def get_cfg(request: Request) -> Any:
    return request.app.state.cfg


# ── Login form ────────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_get(
    request: Request,
    templates: Any = Depends(get_templates),
) -> Response:
    # Already logged in? → home
    if request.session.get("user"):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return cast(
        Response,
        templates.TemplateResponse(request, "login.html", {"error": None, "username": ""}),
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    templates: Any = Depends(get_templates),
    cfg: Any = Depends(get_cfg),
) -> Response:
    expected_user = cfg.gui.username
    expected_pass = cfg.gui.password.get_secret_value()

    # Constant-time comparison
    user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
    pass_ok = hmac.compare_digest(password.encode(), expected_pass.encode())

    if not (user_ok and pass_ok):
        log.warning("gui_login_failed", username=username)
        return cast(
            Response,
            templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid username or password", "username": username},
                status_code=status.HTTP_401_UNAUTHORIZED,
            ),
        )

    request.session["user"] = username
    log.info("gui_login_success", username=username)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request) -> Response:
    user = request.session.pop("user", None)
    log.info("gui_logout", username=user)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

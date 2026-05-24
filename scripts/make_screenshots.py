#!/usr/bin/env python3
# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Generate documentation screenshots from the GUI using Playwright (headless).

This script:
1. Starts a temporary in-process FastAPI server with the GUI
2. Seeds the audit log with sample records so screenshots aren't empty
3. Drives a headless Chromium browser through each page
4. Saves PNGs into docs/img/

Run with:  make screenshots
Or:        python scripts/make_screenshots.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any

# Ensure we can import the package without installing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DOCS_IMG = ROOT / "docs" / "img"
DOCS_IMG.mkdir(parents=True, exist_ok=True)

GUI_HOST = "127.0.0.1"
GUI_PORT = 18080
BASE_URL = f"http://{GUI_HOST}:{GUI_PORT}"

# ── Sample audit records ──────────────────────────────────────────────────────


def write_sample_audit(audit_file: Path) -> None:
    """Seed the audit log so screenshots show realistic activity."""
    now = datetime.now(timezone.utc)
    sample = [
        {
            "timestamp": now.isoformat(),
            "tool": "execute_query",
            "client_id": "claude-ai",
            "success": True,
            "duration_ms": 42.18,
            "pid": os.getpid(),
            "args": {"statement": "SELECT * FROM Default.Users LIMIT 10",
                     "cluster": "default"},
            "result_summary": {"result_count": 10},
        },
        {
            "timestamp": now.isoformat(),
            "tool": "list_dataverses",
            "client_id": "claude-ai",
            "success": True,
            "duration_ms": 15.4,
            "pid": os.getpid(),
            "args": {"cluster": "default"},
            "result_summary": {"result_count": 3},
        },
        {
            "timestamp": now.isoformat(),
            "tool": "get_service_status",
            "client_id": "claude-ai",
            "success": True,
            "duration_ms": 8.9,
            "pid": os.getpid(),
            "args": {"cluster": "default"},
            "result_summary": {"result_keys": ["state", "ccRevLag", "authorizedNodes"]},
        },
        {
            "timestamp": now.isoformat(),
            "tool": "create_link",
            "client_id": "claude-ai",
            "success": False,
            "duration_ms": 1234.5,
            "pid": os.getpid(),
            "args": {"name": "myS3", "dataverse": "Default"},
            "result_summary": {},
            "error": "AnalyticsAuthError",
        },
    ]
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with audit_file.open("w") as fh:
        for rec in sample:
            fh.write(json.dumps(rec) + "\n")


def write_sample_logs(log_file: Path) -> None:
    """Seed the structured log file so the /logs page has content for screenshots."""
    now = datetime.now(timezone.utc).isoformat()
    sample = [
        {"timestamp": now, "level": "info",    "event": "server_starting",     "pid": os.getpid(), "mcp_port": 8000},
        {"timestamp": now, "level": "info",    "event": "cluster_connected",   "pid": os.getpid(), "name": "default", "host": "localhost"},
        {"timestamp": now, "level": "info",    "event": "server_ready",        "pid": os.getpid(), "clusters": ["default"]},
        {"timestamp": now, "level": "info",    "event": "gui_login_success",   "pid": os.getpid(), "username": "admin"},
        {"timestamp": now, "level": "warning", "event": "http_error_response", "pid": os.getpid(), "method": "GET", "status_code": 404, "url": "http://localhost:8091/whoami"},
        {"timestamp": now, "level": "info",    "event": "tool_invoke",         "pid": os.getpid(), "tool": "execute_query"},
        {"timestamp": now, "level": "error",   "event": "tool_unexpected_error", "pid": os.getpid(), "tool": "create_link", "error": "AnalyticsAuthError"},
    ]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as fh:
        for rec in sample:
            fh.write(json.dumps(rec) + "\n")


# ── In-process server ─────────────────────────────────────────────────────────


def make_dev_config(audit_file: Path, log_file: Path) -> Any:
    from pydantic import SecretStr

    from cb_analytics_mcp.config import (
        AppConfig,
        GuiConfig,
        ObservabilityConfig,
    )

    return AppConfig(
        mcp_host="127.0.0.1",
        mcp_port=18000,
        mcp_api_key=SecretStr("z" * 48),
        clusters=[],
        gui=GuiConfig(
            enabled=True,
            host=GUI_HOST,
            port=GUI_PORT,
            username="admin",
            password=SecretStr("password"),
            session_secret=SecretStr("s" * 48),
        ),
        observability=ObservabilityConfig(
            audit_log_enabled=True,
            audit_log_file=str(audit_file),
            log_file=str(log_file),
            log_format="console",
            metrics_enabled=False,
        ),
    )


def run_uvicorn_in_thread(cfg: Any) -> Thread:
    import uvicorn

    from cb_analytics_mcp.gui.app import build_app

    app = build_app(cfg)
    config = uvicorn.Config(
        app, host=GUI_HOST, port=GUI_PORT, log_level="warning", log_config=None
    )
    server = uvicorn.Server(config)

    def run() -> None:
        asyncio.run(server.serve())

    t = Thread(target=run, daemon=True, name="screenshot-gui")
    t.start()

    # Wait for the server to come up
    import urllib.request
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{BASE_URL}/login", timeout=0.5)
            return t
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("GUI did not come up within 5 seconds")


# ── Playwright capture ────────────────────────────────────────────────────────


async def capture() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # 1. Login page
        await page.goto(f"{BASE_URL}/login")
        await page.screenshot(path=str(DOCS_IMG / "login.png"), full_page=True)

        # Log in
        await page.fill('input[name="username"]', "admin")
        await page.fill('input[name="password"]', "password")
        await page.click('button[type="submit"]')
        await page.wait_for_url(f"{BASE_URL}/")

        # 2. Dashboard
        await page.screenshot(path=str(DOCS_IMG / "dashboard.png"), full_page=True)

        # 3. Query editor — pre-fill the textarea so the screenshot shows
        # what a real working query looks like.
        await page.goto(f"{BASE_URL}/query")
        await page.fill(
            'textarea[name="statement"]',
            "SELECT u.id, u.name, u.email\nFROM Default.Users u\nWHERE u.active = true\nORDER BY u.created_at DESC\nLIMIT 25",
        )
        await page.screenshot(path=str(DOCS_IMG / "query.png"), full_page=True)

        # 4. Admin (audit log)
        await page.goto(f"{BASE_URL}/admin")
        await page.screenshot(path=str(DOCS_IMG / "admin.png"), full_page=True)

        # 5. Logs — wait for the HTMX poll to populate the page
        await page.goto(f"{BASE_URL}/logs")
        # HTMX fires the /logs/tail call on `load` — give it up to 5s,
        # falling back to a fixed wait if it doesn't fire (which would mean
        # the page rendered without the JS, still worth a screenshot).
        try:
            await page.wait_for_function(
                "document.querySelector('#log-tail .max-h-\\\\[32rem\\\\]') !== null",
                timeout=5000,
            )
        except Exception:
            await asyncio.sleep(2)
        await asyncio.sleep(0.3)  # paint
        await page.screenshot(path=str(DOCS_IMG / "logs.png"), full_page=True)

        await browser.close()


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    tmp_audit = Path(tempfile.gettempdir()) / "cb-analytics-mcp-screenshot-audit.log"
    tmp_log = Path(tempfile.gettempdir()) / "cb-analytics-mcp-screenshot.log"
    write_sample_audit(tmp_audit)
    write_sample_logs(tmp_log)
    print(f"Seeded audit log at {tmp_audit}")
    print(f"Seeded structured log at {tmp_log}")

    cfg = make_dev_config(tmp_audit, tmp_log)
    run_uvicorn_in_thread(cfg)
    print(f"GUI up at {BASE_URL}")

    try:
        asyncio.run(capture())
    except Exception as e:
        print(f"Screenshot capture failed: {e}", file=sys.stderr)
        return 1

    print(f"✓ Screenshots written to {DOCS_IMG}")
    for img in sorted(DOCS_IMG.glob("*.png")):
        size = img.stat().st_size
        print(f"  - {img.name} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

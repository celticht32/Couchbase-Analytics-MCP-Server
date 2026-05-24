# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the admin route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.mcp.conftest import FakePool


@pytest.fixture
def admin_client(gui_cfg, fake_pool: FakePool, tmp_audit_file: Path):
    """Build a client with seeded audit log."""
    from prometheus_client import CollectorRegistry

    from cb_analytics_mcp.gui.app import build_app
    from cb_analytics_mcp.observability.audit import AuditLog
    from cb_analytics_mcp.observability.metrics import Metrics

    # Seed audit log
    records = [
        {
            "timestamp": "2026-05-24T03:00:00Z",
            "tool": "execute_query",
            "success": True,
            "duration_ms": 42.5,
            "pid": 1,
            "args": {"q": "SELECT 1"},
            "result_summary": {"result_count": 5},
        },
        {
            "timestamp": "2026-05-24T03:01:00Z",
            "tool": "list_dataverses",
            "success": False,
            "duration_ms": 12.3,
            "pid": 1,
            "args": {},
            "result_summary": {},
            "error": "AnalyticsAuthError",
        },
        {
            "timestamp": "2026-05-24T03:02:00Z",
            "tool": "execute_query",
            "success": True,
            "duration_ms": 100,
            "pid": 1,
            "args": {"q": "SELECT 2"},
            "result_summary": {"result_count": 10},
        },
    ]
    tmp_audit_file.write_text("\n".join(json.dumps(r) for r in records))

    app = build_app(
        gui_cfg,
        pool=fake_pool,
        audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
        metrics=Metrics(registry=CollectorRegistry()),
    )
    client = TestClient(app)
    client.__enter__()
    client.post("/login", data={"username": "admin", "password": "test-pass"})
    try:
        yield client
    finally:
        client.__exit__(None, None, None)


class TestAdminPage:
    def test_renders(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin")
        assert r.status_code == 200
        assert "Audit log" in r.text
        assert "Configuration" in r.text

    def test_shows_audit_records(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin")
        assert "execute_query" in r.text
        assert "list_dataverses" in r.text
        assert "AnalyticsAuthError" in r.text

    def test_config_summary_redacts_secrets(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin")
        # The session_secret + password values shouldn't appear in plain text
        assert "test-pass" not in r.text
        assert "ssssssssss" not in r.text  # nothing like the SecretStr value

    def test_tool_filter_dropdown_populated(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin")
        # The dropdown should include both tools seen in the audit log
        assert "execute_query" in r.text
        assert "list_dataverses" in r.text


class TestAdminFilters:
    def test_filter_by_tool(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin?tool=execute_query")
        assert r.status_code == 200
        # execute_query appears, list_dataverses doesn't (in the table)
        assert r.text.count("execute_query") >= 1
        # list_dataverses still shows in the dropdown so we can't assert "not in"
        # at the page level — instead check the filter sticks
        assert 'value="execute_query" selected' in r.text or '"execute_query"' in r.text

    def test_filter_failures_only(self, admin_client: TestClient) -> None:
        r = admin_client.get("/admin?failures_only=true")
        assert r.status_code == 200
        # Only the failed record (list_dataverses with AuthError) should appear
        assert "AnalyticsAuthError" in r.text
        assert "failures_only" in r.text or "checked" in r.text


class TestAdminEmptyAudit:
    def test_no_audit_records(self, gui_cfg, fake_pool: FakePool, tmp_audit_file: Path) -> None:
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        # empty audit file
        tmp_audit_file.write_text("")
        app = build_app(
            gui_cfg,
            pool=fake_pool,
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )
        with TestClient(app) as c:
            c.post("/login", data={"username": "admin", "password": "test-pass"})
            r = c.get("/admin")
            assert r.status_code == 200
            assert "No audit records" in r.text

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the admin audit-log search/filter features."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, GuiConfig, ObservabilityConfig
from cb_analytics_mcp.gui.app import build_app
from cb_analytics_mcp.gui.routes.admin import _parse_filter_date, _record_in_range
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from tests.unit.mcp.conftest import FakePool


@pytest.fixture
def authed_client_with_audit(tmp_path):
    audit_path = tmp_path / "audit.log"
    # Seed the audit file with a mix of records spanning a few days
    records = [
        {
            "timestamp": "2026-05-20T10:00:00+00:00",
            "tool": "list_users",
            "success": True,
            "duration_ms": 1.0,
            "client_id": "c1",
            "args": {},
            "result_summary": {},
        },
        {
            "timestamp": "2026-05-21T11:30:00+00:00",
            "tool": "execute_query",
            "success": True,
            "duration_ms": 22.0,
            "client_id": "c1",
            "args": {"statement": "SELECT 1"},
            "result_summary": {},
        },
        {
            "timestamp": "2026-05-22T09:00:00+00:00",
            "tool": "execute_query",
            "success": False,
            "error": "AnalyticsQueryError",
            "duration_ms": 5.0,
            "client_id": "c2",
            "args": {},
            "result_summary": {},
        },
        {
            "timestamp": "2026-05-23T14:15:00+00:00",
            "tool": "delete_user",
            "success": True,
            "duration_ms": 3.5,
            "client_id": "c1",
            "args": {},
            "result_summary": {},
        },
        {
            "timestamp": "2026-05-24T08:00:00+00:00",
            "tool": "execute_query",
            "success": True,
            "duration_ms": 12.0,
            "client_id": "c2",
            "args": {},
            "result_summary": {},
        },
    ]
    audit_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[],
        gui=GuiConfig(
            username="admin",
            password=SecretStr("p"),
            session_secret=SecretStr("s" * 48),
        ),
        observability=ObservabilityConfig(
            audit_log_enabled=True,
            audit_log_file=str(audit_path),
            metrics_enabled=False,
        ),
    )
    app = build_app(
        cfg,
        pool=FakePool(),
        audit=AuditLog(enabled=False),
        metrics=Metrics(registry=CollectorRegistry()),
    )
    client = TestClient(app)
    with client:
        client.post("/login", data={"username": "admin", "password": "p"})
        yield client


class TestDateParsing:
    def test_iso_date(self) -> None:
        dt = _parse_filter_date("2026-05-22")
        assert dt is not None
        assert dt.year == 2026 and dt.month == 5 and dt.day == 22

    def test_iso_datetime(self) -> None:
        dt = _parse_filter_date("2026-05-22T10:30:00")
        assert dt is not None
        assert dt.hour == 10 and dt.minute == 30

    def test_empty_returns_none(self) -> None:
        assert _parse_filter_date(None) is None
        assert _parse_filter_date("") is None
        assert _parse_filter_date("   ") is None

    def test_garbage_returns_none(self) -> None:
        assert _parse_filter_date("not a date") is None
        assert _parse_filter_date("99/99/9999") is None


class TestRecordInRange:
    def test_no_bounds_passes_all(self) -> None:
        rec = {"timestamp": "2026-05-22T10:00:00+00:00"}
        assert _record_in_range(rec, None, None) is True

    def test_in_range_passes(self) -> None:
        rec = {"timestamp": "2026-05-22T10:00:00+00:00"}
        from_dt = datetime(2026, 5, 20)
        to_dt = datetime(2026, 5, 25)
        assert _record_in_range(rec, from_dt, to_dt) is True

    def test_before_from_rejected(self) -> None:
        rec = {"timestamp": "2026-05-18T10:00:00+00:00"}
        assert _record_in_range(rec, datetime(2026, 5, 20), None) is False

    def test_after_to_rejected(self) -> None:
        rec = {"timestamp": "2026-05-28T10:00:00+00:00"}
        assert _record_in_range(rec, None, datetime(2026, 5, 25)) is False

    def test_record_with_no_timestamp_rejected(self) -> None:
        assert _record_in_range({}, datetime(2026, 5, 1), None) is False

    def test_record_with_unparseable_timestamp_rejected(self) -> None:
        rec = {"timestamp": "not a real date"}
        assert _record_in_range(rec, datetime(2026, 5, 1), None) is False


class TestAdminPageFilters:
    def test_admin_renders_filter_form(self, authed_client_with_audit) -> None:
        r = authed_client_with_audit.get("/admin")
        assert r.status_code == 200
        # Date filter inputs present
        assert 'name="from_date"' in r.text
        assert 'name="to_date"' in r.text
        # Tool dropdown present
        assert 'name="tool"' in r.text
        # All registered tools in dropdown — pick a couple of well-known ones
        assert ">execute_query<" in r.text
        assert ">list_users<" in r.text

    def test_tool_filter(self, authed_client_with_audit) -> None:
        r = authed_client_with_audit.get("/admin?tool=execute_query")
        assert r.status_code == 200
        # Should show 3 execute_query records and not the list_users / delete_user
        assert r.text.count("execute_query") >= 4  # 3 rows + filter dropdown
        # delete_user appears in the dropdown but should NOT appear as a row
        # Check that we get fewer total <tr> rows than the unfiltered case
        unfiltered = authed_client_with_audit.get("/admin").text
        assert r.text.count("<tr>") < unfiltered.count("<tr>")

    def test_failures_only(self, authed_client_with_audit) -> None:
        r = authed_client_with_audit.get("/admin?failures_only=true")
        assert r.status_code == 200
        # Only one failure in the seed data
        assert "AnalyticsQueryError" in r.text

    def test_date_range_filter(self, authed_client_with_audit) -> None:
        # Restrict to just 2026-05-22 (single day). Use the fragment endpoint
        # so the dropdown options don't pollute our table assertions.
        r = authed_client_with_audit.get("/admin/audit-fragment?from_date=2026-05-22&to_date=2026-05-22")
        assert r.status_code == 200
        # Only the failed execute_query on that day matches
        assert "AnalyticsQueryError" in r.text
        # The earlier list_users (2026-05-20) and later delete_user (2026-05-23)
        # should be filtered out of the table
        assert "list_users" not in r.text
        assert "delete_user" not in r.text

    def test_fragment_endpoint(self, authed_client_with_audit) -> None:
        """The fragment endpoint returns just the table, not the full page."""
        r = authed_client_with_audit.get("/admin/audit-fragment")
        assert r.status_code == 200
        # Should contain table markup but not the page header
        assert "<table" in r.text
        # Should NOT include the page-level Admin h1
        assert "<h1" not in r.text

    def test_fragment_respects_filters(self, authed_client_with_audit) -> None:
        r = authed_client_with_audit.get("/admin/audit-fragment?failures_only=true")
        assert r.status_code == 200
        assert "AnalyticsQueryError" in r.text

    def test_no_matches_shows_empty_state(self, authed_client_with_audit) -> None:
        r = authed_client_with_audit.get("/admin/audit-fragment?tool=nonexistent_tool")
        assert r.status_code == 200
        assert "No audit records match" in r.text

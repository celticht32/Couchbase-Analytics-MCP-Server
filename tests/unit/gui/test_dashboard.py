# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the dashboard route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.mcp.conftest import FakePool


class TestDashboardEmptyState:
    def test_renders_with_no_clusters(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/")
        assert r.status_code == 200
        assert "Dashboard" in r.text
        assert "Clusters" in r.text
        # No clusters → empty-state row
        assert "No clusters configured" in r.text

    def test_no_activity_state(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/")
        assert "No tool activity yet" in r.text

    def test_capella_disabled(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/")
        assert "Disabled" in r.text  # capella card


class TestDashboardWithClusters:
    @pytest.fixture
    def populated_pool(self) -> FakePool:
        pool = FakePool(names=["prod", "stage"])
        # Make prod reachable, stage unreachable
        pool.client_for("prod").ping.return_value = True
        pool.client_for("stage").ping.return_value = False
        # set .cfg on each fake client so the dashboard can read host
        pool.client_for("prod").cfg = _StubCfg(host="prod.example.com", tls=True)
        pool.client_for("stage").cfg = _StubCfg(host="stage.example.com", tls=False)
        return pool

    def test_clusters_rendered(
        self,
        gui_cfg,
        populated_pool: FakePool,
        tmp_audit_file: Path,
    ) -> None:
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        app = build_app(
            gui_cfg,
            pool=populated_pool,
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )

        with TestClient(app) as c:
            # Log in
            c.post("/login", data={"username": "admin", "password": "test-pass"})
            r = c.get("/")
            assert r.status_code == 200
            assert "prod" in r.text
            assert "stage" in r.text
            assert "prod.example.com" in r.text
            assert "Reachable" in r.text
            assert "Unreachable" in r.text


class TestDashboardWithAuditRecords:
    def test_renders_recent_activity(
        self,
        gui_cfg,
        fake_pool: FakePool,
        tmp_audit_file: Path,
    ) -> None:
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        # Seed the audit log directly
        records = [
            {
                "timestamp": "2026-05-24T03:00:00Z",
                "tool": "execute_query",
                "success": True,
                "duration_ms": 42.5,
                "pid": 1,
                "args": {"q": "SELECT 1"},
                "result_summary": {"result_count": 1},
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
        ]
        tmp_audit_file.write_text("\n".join(json.dumps(r) for r in records))

        audit = AuditLog(enabled=True, log_file=str(tmp_audit_file))
        app = build_app(
            gui_cfg,
            pool=fake_pool,
            audit=audit,
            metrics=Metrics(registry=CollectorRegistry()),
        )
        with TestClient(app) as c:
            c.post("/login", data={"username": "admin", "password": "test-pass"})
            r = c.get("/")
            assert r.status_code == 200
            assert "execute_query" in r.text
            assert "list_dataverses" in r.text
            assert "AnalyticsAuthError" in r.text


# ── Helpers ──────────────────────────────────────────────────────────────────


class _StubCfg:
    def __init__(self, host: str, tls: bool) -> None:
        self.host = host
        self.tls = tls


# ── Runner functions (mocked uvicorn) ────────────────────────────────────────


class TestRunners:
    """run_gui and run_gui_blocking each call uvicorn — patch it out."""

    @pytest.mark.asyncio
    async def test_run_gui_calls_uvicorn(self, monkeypatch, gui_cfg) -> None:
        import sys
        from unittest.mock import AsyncMock, MagicMock

        from cb_analytics_mcp.gui import app as app_module

        fake_server = MagicMock()
        fake_server.serve = AsyncMock(return_value=None)
        fake_uvicorn = MagicMock()
        fake_uvicorn.Server.return_value = fake_server
        fake_uvicorn.Config.return_value = MagicMock()

        monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
        await app_module.run_gui(gui_cfg)
        fake_uvicorn.Server.assert_called_once()
        fake_server.serve.assert_awaited_once()

    def test_run_gui_blocking_calls_uvicorn_run(self, monkeypatch, gui_cfg) -> None:
        import sys
        from unittest.mock import MagicMock

        from cb_analytics_mcp.gui import app as app_module

        fake_uvicorn = MagicMock()
        monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

        app_module.run_gui_blocking(gui_cfg)
        fake_uvicorn.run.assert_called_once()


class TestDashboardErrorHandling:
    def test_blank_lines_and_garbage_in_audit_log_are_skipped(
        self, gui_cfg, fake_pool, tmp_audit_file
    ) -> None:
        """The dashboard reader tolerates blank lines and malformed JSON."""
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        tmp_audit_file.write_text(
            "\n"  # blank
            "not-valid-json{\n"  # garbage
            '{"timestamp":"2026-05-24T00:00:00Z","tool":"valid_tool","success":true,"duration_ms":1,"pid":1,"args":{},"result_summary":{}}\n'
            "\n"
        )
        app = build_app(
            gui_cfg,
            pool=fake_pool,
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )
        with TestClient(app) as c:
            c.post("/login", data={"username": "admin", "password": "test-pass"})
            r = c.get("/")
            assert r.status_code == 200
            assert "valid_tool" in r.text
            # Garbage didn't crash anything

    def test_dashboard_ping_exception_marks_unreachable(self, gui_cfg, tmp_audit_file) -> None:
        """If client.ping() raises, the dashboard catches it and shows unreachable."""
        from unittest.mock import AsyncMock

        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        pool = FakePool(names=["c1"])
        pool.client_for("c1").ping = AsyncMock(side_effect=RuntimeError("network"))
        # Set a stub cfg so the dashboard can read .host even on failure
        pool.client_for("c1").cfg = _StubCfg(host="c1.example.com", tls=False)

        app = build_app(
            gui_cfg,
            pool=pool,
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )
        with TestClient(app) as c:
            c.post("/login", data={"username": "admin", "password": "test-pass"})
            r = c.get("/")
            assert r.status_code == 200
            assert "Unreachable" in r.text
            assert "c1" in r.text

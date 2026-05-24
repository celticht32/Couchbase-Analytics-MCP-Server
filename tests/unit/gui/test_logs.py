# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the logs route."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, GuiConfig, ObservabilityConfig
from tests.unit.mcp.conftest import FakePool


class TestLogsPageNoFile:
    def test_logs_page_renders_with_no_log_file(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/logs")
        assert r.status_code == 200
        assert "Live logs" in r.text
        # When LOG_FILE not set, page mentions stdout
        assert "stdout" in r.text.lower() or "not set" in r.text.lower()

    def test_logs_tail_returns_note_when_no_file(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/logs/tail")
        assert r.status_code == 200
        assert "LOG_FILE is not configured" in r.text


class TestLogsTailWithFile:
    @pytest.fixture
    def log_file(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    @pytest.fixture
    def logs_client(self, log_file: Path, tmp_audit_file: Path):
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        cfg = AppConfig(
            mcp_api_key=SecretStr("z" * 48),
            clusters=[],
            gui=GuiConfig(
                username="admin",
                password=SecretStr("test-pass"),
                session_secret=SecretStr("s" * 48),
            ),
            observability=ObservabilityConfig(
                log_level="WARNING",
                log_file=str(log_file),
                audit_log_enabled=True,
                audit_log_file=str(tmp_audit_file),
                metrics_enabled=False,
            ),
        )
        app = build_app(
            cfg,
            pool=FakePool(),
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )
        client = TestClient(app)
        client.__enter__()
        client.post("/login", data={"username": "admin", "password": "test-pass"})
        try:
            yield client, log_file
        finally:
            client.__exit__(None, None, None)

    def test_json_log_lines_rendered(self, logs_client) -> None:
        client, log_file = logs_client
        records = [
            {"timestamp": "2026-05-24T03:00:00Z", "level": "info", "event": "boot"},
            {"timestamp": "2026-05-24T03:00:01Z", "level": "warning", "event": "slow_query"},
            {"timestamp": "2026-05-24T03:00:02Z", "level": "error", "event": "auth_failed"},
        ]
        log_file.write_text("\n".join(json.dumps(r) for r in records))

        r = client.get("/logs/tail")
        assert r.status_code == 200
        assert "boot" in r.text
        assert "slow_query" in r.text
        assert "auth_failed" in r.text
        # Level styling differentiates them
        assert "warning" in r.text
        assert "error" in r.text

    def test_non_json_log_lines_handled(self, logs_client) -> None:
        client, log_file = logs_client
        # plain console-format lines, not JSON
        log_file.write_text("2026-05-24 03:00:00 INFO server starting\n2026-05-24 03:00:01 ERROR refused\n")
        r = client.get("/logs/tail")
        assert r.status_code == 200
        assert "server starting" in r.text
        assert "refused" in r.text

    def test_empty_log_file(self, logs_client) -> None:
        client, log_file = logs_client
        log_file.write_text("")
        r = client.get("/logs/tail")
        assert r.status_code == 200
        # No records — empty-state row
        assert "No log lines" in r.text

    def test_lines_param_clamped(self, logs_client) -> None:
        client, log_file = logs_client
        # write 50 lines
        log_file.write_text(
            "\n".join(
                json.dumps({"timestamp": f"t{i}", "level": "info", "event": f"e{i}"}) for i in range(50)
            )
        )
        # request 999 lines — clamped to 500
        r = client.get("/logs/tail?lines=999")
        assert r.status_code == 200
        # All 50 lines fit
        assert "e0" in r.text
        assert "e49" in r.text

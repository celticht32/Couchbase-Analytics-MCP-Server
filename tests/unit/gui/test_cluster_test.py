# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the dashboard cluster Test button endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, GuiConfig, ObservabilityConfig
from cb_analytics_mcp.gui.app import build_app
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from tests.unit.mcp.conftest import FakePool


@pytest.fixture
def authed_client(tmp_path):
    audit_path = tmp_path / "audit.log"
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
            audit_log_enabled=False,
            audit_log_file=str(audit_path),
            metrics_enabled=False,
        ),
    )
    pool = FakePool()  # has a default cluster with a happy-path mock client
    app = build_app(
        cfg,
        pool=pool,
        audit=AuditLog(enabled=False),
        metrics=Metrics(registry=CollectorRegistry()),
    )
    client = TestClient(app)
    with client:
        client.post("/login", data={"username": "admin", "password": "test-pass"})
        yield client, pool


class TestClusterTestEndpoint:
    def test_ping_success_returns_reachable(self, authed_client) -> None:
        client, pool = authed_client
        # FakePool's default client is ping-True by default
        pool.default().ping.return_value = True
        r = client.post("/cluster/default/test")
        assert r.status_code == 200
        assert "reachable" in r.text.lower()
        assert "ms" in r.text  # elapsed-time annotation

    def test_ping_false_returns_unreachable(self, authed_client) -> None:
        client, pool = authed_client
        pool.default().ping.return_value = False
        r = client.post("/cluster/default/test")
        assert r.status_code == 200
        assert "returned false" in r.text.lower()

    def test_ping_raises_returns_failed(self, authed_client) -> None:
        client, pool = authed_client
        pool.default().ping.side_effect = ConnectionError("network unreachable")
        r = client.post("/cluster/default/test")
        assert r.status_code == 200
        assert "failed" in r.text.lower()
        assert "network unreachable" in r.text

    def test_unknown_cluster_returns_404(self, authed_client) -> None:
        client, _pool = authed_client
        r = client.post("/cluster/does-not-exist/test")
        assert r.status_code == 404
        assert "unknown cluster" in r.text.lower()

    def test_unauthenticated_redirects(self, tmp_path) -> None:
        """Without a session, the test endpoint should redirect to /login."""
        audit_path = tmp_path / "audit.log"
        cfg = AppConfig(
            mcp_api_key=SecretStr("z" * 48),
            clusters=[],
            gui=GuiConfig(
                username="admin",
                password=SecretStr("p"),
                session_secret=SecretStr("s" * 48),
            ),
            observability=ObservabilityConfig(
                audit_log_enabled=False,
                audit_log_file=str(audit_path),
                metrics_enabled=False,
            ),
        )
        app = build_app(
            cfg, pool=FakePool(), audit=AuditLog(enabled=False), metrics=Metrics(registry=CollectorRegistry())
        )
        with TestClient(app) as anon:
            r = anon.post("/cluster/default/test", follow_redirects=False)
            # 303 redirect raised by require_session
            assert r.status_code in (303, 307)


class TestDashboardShowsTestButton:
    def test_dashboard_renders_test_buttons(self, authed_client) -> None:
        """The dashboard cluster table should include Test buttons."""
        client, _pool = authed_client
        r = client.get("/")
        assert r.status_code == 200
        # Each cluster row gets a Test button posting to /cluster/{name}/test
        assert 'hx-post="/cluster/default/test"' in r.text
        # Header should include the new "Test" column
        assert ">Test<" in r.text

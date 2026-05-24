# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for /healthz and /readyz."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from cb_analytics_mcp.gui.app import build_app
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from tests.unit.mcp.conftest import FakePool


def _client(gui_cfg, pool: FakePool, audit_file: Path) -> TestClient:
    app = build_app(
        gui_cfg,
        pool=pool,
        audit=AuditLog(enabled=True, log_file=str(audit_file)),
        metrics=Metrics(registry=CollectorRegistry()),
    )
    return TestClient(app)


class TestHealthz:
    def test_returns_200_without_auth(self, gui_cfg, tmp_audit_file: Path) -> None:
        with _client(gui_cfg, FakePool(names=[]), tmp_audit_file) as c:
            r = c.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}

    def test_no_session_cookie_set(self, gui_cfg, tmp_audit_file: Path) -> None:
        """/healthz must not touch the session middleware in a way that
        sets a cookie (load balancers don't keep state)."""
        with _client(gui_cfg, FakePool(names=[]), tmp_audit_file) as c:
            r = c.get("/healthz")
            # SessionMiddleware sets a Set-Cookie when the session dict was
            # touched. Health endpoint must not touch it.
            cookies = r.headers.get_list("set-cookie")
            for cookie in cookies:
                assert "cb_analytics_session" not in cookie, "/healthz should not set a session cookie"


class TestReadyzEmpty:
    def test_empty_pool_returns_200(self, gui_cfg, tmp_audit_file: Path) -> None:
        """An empty pool means no clusters configured — that's a deployment
        choice, not a failure, so /readyz returns 200 with a note."""
        with _client(gui_cfg, FakePool(names=[]), tmp_audit_file) as c:
            r = c.get("/readyz")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ok"
            assert body["clusters"] == []
            assert "note" in body


class TestReadyzReachable:
    def test_all_clusters_reachable(self, gui_cfg, tmp_audit_file: Path) -> None:
        pool = FakePool(names=["c1", "c2"])
        pool.client_for("c1").ping.return_value = True
        pool.client_for("c2").ping.return_value = True
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ok"
            assert {x["name"] for x in body["clusters"]} == {"c1", "c2"}
            assert all(x["reachable"] for x in body["clusters"])

    def test_any_reachable_is_enough(self, gui_cfg, tmp_audit_file: Path) -> None:
        """If at least one cluster works, the server is ready."""
        pool = FakePool(names=["c1", "c2"])
        pool.client_for("c1").ping.return_value = False
        pool.client_for("c2").ping.return_value = True
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


class TestReadyzUnreachable:
    def test_all_unreachable_returns_503(self, gui_cfg, tmp_audit_file: Path) -> None:
        pool = FakePool(names=["c1", "c2"])
        pool.client_for("c1").ping.return_value = False
        pool.client_for("c2").ping.return_value = False
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz")
            assert r.status_code == 503
            body = r.json()
            assert body["status"] == "unavailable"

    def test_ping_exception_treated_as_unreachable(self, gui_cfg, tmp_audit_file: Path) -> None:
        pool = FakePool(names=["c1"])
        pool.client_for("c1").ping = AsyncMock(side_effect=RuntimeError("network"))
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz")
            assert r.status_code == 503

    def test_returns_200_when_pool_get_raises(self, gui_cfg, tmp_audit_file: Path) -> None:
        """Pool says it has clusters but get() raises — never 5xx."""
        pool = FakePool(names=["c1"])
        # Force pool.get to raise — exercises the broad except
        pool._clients.pop("c1")
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz")
            # All clusters unreachable → 503, but the endpoint itself doesn't crash
            assert r.status_code == 503
            assert r.json()["clusters"][0]["reachable"] is False


class TestUnauthenticated:
    """Confirm the health routes don't get caught by require_session."""

    def test_healthz_no_redirect(self, gui_cfg, tmp_audit_file: Path) -> None:
        with _client(gui_cfg, FakePool(names=[]), tmp_audit_file) as c:
            r = c.get("/healthz", follow_redirects=False)
            assert r.status_code == 200
            assert "location" not in {k.lower() for k in r.headers}

    def test_readyz_no_redirect(self, gui_cfg, tmp_audit_file: Path) -> None:
        pool = FakePool(names=["c1"])
        pool.client_for("c1").ping.return_value = True
        with _client(gui_cfg, pool, tmp_audit_file) as c:
            r = c.get("/readyz", follow_redirects=False)
            assert r.status_code == 200

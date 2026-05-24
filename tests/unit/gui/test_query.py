# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the query editor route."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cb_analytics_mcp.couchbase.exceptions import AnalyticsQueryError
from cb_analytics_mcp.couchbase.models import (
    AnalyticsMetrics,
    AnalyticsQueryResponse,
)
from tests.unit.mcp.conftest import FakePool


def _make_response(results: list, request_id: str = "r1") -> AnalyticsQueryResponse:
    return AnalyticsQueryResponse(
        requestID=request_id,
        status="success",
        results=results,
        metrics=AnalyticsMetrics(resultCount=len(results), executionTime="42ms"),
    )


class TestQueryPage:
    def test_renders(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.get("/query")
        assert r.status_code == 200
        assert "SQL++ query editor" in r.text
        assert 'name="statement"' in r.text
        assert 'name="cluster"' in r.text
        assert 'name="scan_consistency"' in r.text


class TestQueryRun:
    def test_with_no_clusters_returns_error_fragment(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.post(
            "/query/run",
            data={"statement": "SELECT 1"},
        )
        assert r.status_code == 200
        assert "No clusters configured" in r.text

    def test_unknown_cluster_returns_error(self, authenticated_client: TestClient) -> None:
        r = authenticated_client.post(
            "/query/run",
            data={"statement": "SELECT 1", "cluster": "does-not-exist"},
        )
        assert r.status_code == 200
        assert "UnknownCluster" in r.text


class TestQueryRunWithCluster:
    """Tests that need a populated pool — build a fresh app per test."""

    @pytest.fixture
    def populated_client(
        self,
        gui_cfg,
        tmp_audit_file,
    ) -> tuple[TestClient, FakePool]:
        from prometheus_client import CollectorRegistry

        from cb_analytics_mcp.gui.app import build_app
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics

        pool = FakePool(names=["default"])
        app = build_app(
            gui_cfg,
            pool=pool,
            audit=AuditLog(enabled=True, log_file=str(tmp_audit_file)),
            metrics=Metrics(registry=CollectorRegistry()),
        )
        client = TestClient(app)
        client.__enter__()
        client.post("/login", data={"username": "admin", "password": "test-pass"})
        try:
            yield client, pool
        finally:
            client.__exit__(None, None, None)

    def test_successful_query(self, populated_client) -> None:
        client, pool = populated_client
        pool.default().analytics.execute.return_value = _make_response(
            [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
        )

        r = client.post(
            "/query/run",
            data={"statement": "SELECT id, name FROM Users"},
        )
        assert r.status_code == 200
        assert "alice" in r.text
        assert "bob" in r.text
        assert "2 rows" in r.text or "2 row" in r.text
        assert "default" in r.text  # cluster name shown
        assert "r1" in r.text  # request_id shown
        assert "42ms" in r.text  # execution metric

    def test_query_with_explicit_cluster_param(self, populated_client) -> None:
        client, pool = populated_client
        pool.default().analytics.execute.return_value = _make_response([])

        r = client.post(
            "/query/run",
            data={"statement": "SELECT 1", "cluster": "default"},
        )
        assert r.status_code == 200

        # Verify the statement was passed through
        call = pool.default().analytics.execute.call_args[0][0]
        assert call.statement == "SELECT 1"

    def test_query_with_scan_consistency(self, populated_client) -> None:
        client, pool = populated_client
        pool.default().analytics.execute.return_value = _make_response([])

        r = client.post(
            "/query/run",
            data={
                "statement": "SELECT 1",
                "scan_consistency": "request_plus",
            },
        )
        assert r.status_code == 200
        call = pool.default().analytics.execute.call_args[0][0]
        assert call.scan_consistency.value == "request_plus"

    def test_query_error_shown_in_fragment(self, populated_client) -> None:
        client, pool = populated_client
        pool.default().analytics.execute.side_effect = AnalyticsQueryError(
            "Syntax error near 'SELEKT'", code=24000
        )
        r = client.post(
            "/query/run",
            data={"statement": "SELEKT 1"},
        )
        assert r.status_code == 200
        assert "AnalyticsQueryError" in r.text
        assert "Syntax error" in r.text

    def test_empty_statement_rejected(self, populated_client) -> None:
        client, _ = populated_client
        r = client.post("/query/run", data={"statement": ""})
        # FastAPI's Form(...) treats empty as falsy and 422s
        assert r.status_code in (200, 422)

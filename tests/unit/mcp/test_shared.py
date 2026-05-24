# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the shared call_tool_observed helper."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry

from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsQueryError,
)
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from cb_analytics_mcp.tools.shared import call_tool_observed, fmt_error, fmt_ok


class TestFmtOk:
    def test_basic(self) -> None:
        out = fmt_ok({"x": 1})
        assert out == {"ok": True, "data": {"x": 1}}

    def test_with_extra(self) -> None:
        out = fmt_ok([1, 2], cluster="prod", request_id="r1")
        assert out["ok"] is True
        assert out["data"] == [1, 2]
        assert out["cluster"] == "prod"
        assert out["request_id"] == "r1"


class TestFmtError:
    def test_query_error_includes_code(self) -> None:
        err = AnalyticsQueryError("Syntax error", code=24000, line=1, column=5)
        out = fmt_error(err)
        assert out["ok"] is False
        assert out["error"] == "AnalyticsQueryError"
        assert out["message"] == "Syntax error"
        assert out["code"] == 24000
        assert out["line"] == 1
        assert out["column"] == 5

    def test_auth_error(self) -> None:
        err = AnalyticsAuthError("Unauthorized")
        out = fmt_error(err)
        assert out["error"] == "AnalyticsAuthError"
        assert out["message"] == "Unauthorized"

    def test_generic_exception(self) -> None:
        out = fmt_error(ValueError("nope"))
        assert out["error"] == "ValueError"
        assert out["message"] == "nope"


@pytest.fixture
def audit_and_metrics():
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        path = Path(f.name)
    audit = AuditLog(enabled=True, log_file=str(path))
    metrics = Metrics(registry=CollectorRegistry())
    yield audit, metrics, path
    # cleanup
    import logging

    logger = logging.getLogger("cb_analytics_mcp.audit")
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    if path.exists():
        path.unlink()


class TestCallToolObserved:
    @pytest.mark.asyncio
    async def test_success_path(self, audit_and_metrics) -> None:
        audit, metrics, _ = audit_and_metrics

        async def my_func() -> dict:
            return fmt_ok([1, 2, 3])

        result = await call_tool_observed(
            "test_tool", my_func, audit=audit, metrics=metrics, tool_args={"k": "v"}
        )
        assert result == {"ok": True, "data": [1, 2, 3]}

        # Metric incremented
        out = metrics.latest_bytes().decode()
        assert 'outcome="success",tool="test_tool"' in out

    @pytest.mark.asyncio
    async def test_analytics_error_returned_as_dict(self, audit_and_metrics) -> None:
        audit, metrics, _ = audit_and_metrics

        async def failing_func() -> dict:
            raise AnalyticsAuthError("nope")

        result = await call_tool_observed("auth_tool", failing_func, audit=audit, metrics=metrics)
        assert result["ok"] is False
        assert result["error"] == "AnalyticsAuthError"

        out = metrics.latest_bytes().decode()
        assert 'outcome="error",tool="auth_tool"' in out

    @pytest.mark.asyncio
    async def test_unexpected_error_does_not_crash(self, audit_and_metrics) -> None:
        audit, metrics, _ = audit_and_metrics

        async def crashy() -> dict:
            raise RuntimeError("boom")

        result = await call_tool_observed("crashy", crashy, audit=audit, metrics=metrics)
        assert result["ok"] is False
        assert result["error"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_summary_extracted_from_list_data(self, audit_and_metrics) -> None:
        audit, metrics, audit_path = audit_and_metrics

        async def list_data() -> dict:
            return fmt_ok([1, 2, 3, 4, 5])

        await call_tool_observed("list_tool", list_data, audit=audit, metrics=metrics)

        import json

        rec = json.loads(audit_path.read_text().splitlines()[-1])
        assert rec["result_summary"]["result_count"] == 5

    @pytest.mark.asyncio
    async def test_summary_extracted_from_dict_data(self, audit_and_metrics) -> None:
        audit, metrics, audit_path = audit_and_metrics

        async def dict_data() -> dict:
            return fmt_ok({"a": 1, "b": 2, "c": 3})

        await call_tool_observed("dict_tool", dict_data, audit=audit, metrics=metrics)

        import json

        rec = json.loads(audit_path.read_text().splitlines()[-1])
        assert set(rec["result_summary"]["result_keys"]) == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_tool_args_in_audit(self, audit_and_metrics) -> None:
        audit, metrics, audit_path = audit_and_metrics

        async def my_func(_a: int, _b: str) -> dict:
            return fmt_ok({})

        await call_tool_observed(
            "argy",
            my_func,
            42,
            "hi",
            audit=audit,
            metrics=metrics,
            tool_args={"a": 42, "b": "hi"},
        )

        import json

        rec = json.loads(audit_path.read_text().splitlines()[-1])
        assert rec["args"] == {"a": 42, "b": "hi"}

    @pytest.mark.asyncio
    async def test_args_redacted_in_audit(self, audit_and_metrics) -> None:
        audit, metrics, audit_path = audit_and_metrics

        async def my_func() -> dict:
            return fmt_ok({})

        await call_tool_observed(
            "credy",
            my_func,
            audit=audit,
            metrics=metrics,
            tool_args={"username": "alice", "password": "real-secret-1234"},
        )

        text = audit_path.read_text()
        assert "real-secret-1234" not in text
        assert "alice" in text  # username not redacted

    @pytest.mark.asyncio
    async def test_works_without_audit_or_metrics(self) -> None:
        async def my_func() -> dict:
            return fmt_ok({"x": 1})

        # No audit, no metrics — should still work
        result = await call_tool_observed("t", my_func)
        assert result == {"ok": True, "data": {"x": 1}}


class TestCallToolObservedOkFalseReturn:
    """An impl that returns {"ok": False, ...} directly (without raising)
    should still be recorded as an audit failure."""

    @pytest.mark.asyncio
    async def test_returns_ok_false(self, audit_and_metrics) -> None:
        audit, metrics, audit_path = audit_and_metrics

        async def softfail() -> dict:
            return {"ok": False, "error": "MySoftError", "message": "calmly handled"}

        result = await call_tool_observed("softfail", softfail, audit=audit, metrics=metrics)
        assert result["ok"] is False
        assert result["error"] == "MySoftError"

        # Audit log should reflect failure
        import json

        rec = json.loads(audit_path.read_text().splitlines()[-1])
        assert rec["success"] is False
        assert rec["error"] == "MySoftError"

        # Metric label should be "error"
        out = metrics.latest_bytes().decode()
        assert 'outcome="error",tool="softfail"' in out

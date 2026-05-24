# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the audit log."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.redact import REDACTED


@pytest.fixture
def audit_file() -> Path:
    """Yield a temp audit file path; clean up after."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()
    # Drop the cached handlers so the next test gets a fresh logger
    logger = logging.getLogger("cb_analytics_mcp.audit")
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)


def _read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TestAuditLogRecord:
    def test_writes_one_record_per_call(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record("test_tool", args={"x": 1}, result_summary={"rows": 5})

        records = _read_records(audit_file)
        assert len(records) == 1
        assert records[0]["tool"] == "test_tool"
        assert records[0]["args"] == {"x": 1}
        assert records[0]["result_summary"] == {"rows": 5}
        assert records[0]["success"] is True

    def test_record_contains_timestamp_and_pid(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record("t1")

        rec = _read_records(audit_file)[0]
        assert "timestamp" in rec
        assert "T" in rec["timestamp"]  # ISO 8601 separator
        assert isinstance(rec["pid"], int)

    def test_args_redacted(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record(
            "create_link",
            args={
                "name": "myS3",
                "config": {"region": "us-east-1", "secret_access_key": "real-secret"},
            },
        )
        rec = _read_records(audit_file)[0]
        text = json.dumps(rec)
        assert "real-secret" not in text
        assert REDACTED in text

    def test_failure_recorded(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record("t1", success=False, error="AnalyticsAuthError")

        rec = _read_records(audit_file)[0]
        assert rec["success"] is False
        assert rec["error"] == "AnalyticsAuthError"

    def test_disabled_no_writes(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=False, log_file=str(audit_file))
        audit.record("t1")
        assert _read_records(audit_file) == []

    def test_client_id_included(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record("t1", client_id="claude-ai")
        assert _read_records(audit_file)[0]["client_id"] == "claude-ai"

    def test_duration_rounded(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        audit.record("t1", duration_ms=12.34567)
        assert _read_records(audit_file)[0]["duration_ms"] == 12.35

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "audit.log"
            audit = AuditLog(enabled=True, log_file=str(nested))
            audit.record("t1")
            assert nested.exists()
            # cleanup handler
            logger = logging.getLogger("cb_analytics_mcp.audit")
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)


class TestAuditSpan:
    def test_span_records_on_success(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        with audit.span("test_tool", args={"q": "SELECT 1"}) as span:
            span.set_summary({"rows": 10})

        rec = _read_records(audit_file)[0]
        assert rec["tool"] == "test_tool"
        assert rec["success"] is True
        assert rec["result_summary"] == {"rows": 10}
        assert rec["duration_ms"] is not None
        assert rec["duration_ms"] >= 0

    def test_span_records_on_exception(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        with pytest.raises(ValueError):
            with audit.span("test_tool") as _span:
                raise ValueError("boom")

        rec = _read_records(audit_file)[0]
        assert rec["success"] is False
        assert "boom" in rec["error"]

    def test_set_summary_accumulates(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        with audit.span("t") as span:
            span.set_summary({"a": 1})
            span.set_summary({"b": 2})

        rec = _read_records(audit_file)[0]
        assert rec["result_summary"] == {"a": 1, "b": 2}

    def test_span_close_is_idempotent(self, audit_file: Path) -> None:
        audit = AuditLog(enabled=True, log_file=str(audit_file))
        with audit.span("t") as span:
            span.close()
        # Even though close was called manually, only one record written
        assert len(_read_records(audit_file)) == 1

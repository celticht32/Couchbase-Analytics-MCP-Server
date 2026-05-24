# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for audit log rotation behavior."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest

from cb_analytics_mcp.observability.audit import AuditLog


@pytest.fixture
def tmp_audit_dir():
    """Fresh temp directory + reset audit logger between tests."""
    audit_logger = logging.getLogger("cb_analytics_mcp.audit")
    # Detach any handlers left by prior tests
    for h in list(audit_logger.handlers):
        audit_logger.removeHandler(h)
        h.close()
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)
    # Clean up after
    for h in list(audit_logger.handlers):
        audit_logger.removeHandler(h)
        h.close()


class TestAuditRotation:
    def test_rotates_when_file_exceeds_size(self, tmp_audit_dir) -> None:
        """Forcing many writes should rotate the file."""
        audit_file = tmp_audit_dir / "audit.log"
        # Tiny cap so we trigger rotation quickly
        audit = AuditLog(
            enabled=True,
            log_file=str(audit_file),
            rotate_bytes=1024,  # 1 KB
            rotate_keep=3,
        )

        # Write enough records to exceed the cap several times
        for i in range(200):
            audit.record(
                tool_name="test_tool",
                args={"i": i, "payload": "x" * 50},  # ~50-byte payload
                duration_ms=1.0,
                success=True,
            )

        # The main audit.log should still exist
        assert audit_file.exists()
        # At least one rotated backup should exist
        backups = sorted(tmp_audit_dir.glob("audit.log.*"))
        assert len(backups) >= 1
        # Backup count should not exceed rotate_keep
        assert len(backups) <= 3

    def test_no_rotation_when_under_limit(self, tmp_audit_dir) -> None:
        audit_file = tmp_audit_dir / "audit.log"
        audit = AuditLog(
            enabled=True,
            log_file=str(audit_file),
            rotate_bytes=10 * 1024 * 1024,
            rotate_keep=5,
        )
        # Few small records — should not rotate
        for i in range(5):
            audit.record(tool_name="x", duration_ms=1.0)
        assert audit_file.exists()
        assert sorted(tmp_audit_dir.glob("audit.log.*")) == []

    def test_disable_rotation_with_zero(self, tmp_audit_dir) -> None:
        """rotate_bytes=0 means use a plain FileHandler (no rotation)."""
        audit_file = tmp_audit_dir / "audit.log"
        audit = AuditLog(
            enabled=True,
            log_file=str(audit_file),
            rotate_bytes=0,
        )
        # Even writing many records, no rotation files should appear
        for i in range(100):
            audit.record(tool_name="x", args={"i": i, "pad": "y" * 200})
        assert audit_file.exists()
        # Crucially no .1 / .2 backups
        assert sorted(tmp_audit_dir.glob("audit.log.*")) == []

    def test_disabled_audit_writes_nothing(self, tmp_audit_dir) -> None:
        """enabled=False should produce no file at all."""
        audit_file = tmp_audit_dir / "audit.log"
        audit = AuditLog(
            enabled=False,
            log_file=str(audit_file),
        )
        for i in range(10):
            audit.record(tool_name="x")
        # File should never be created
        assert not audit_file.exists()

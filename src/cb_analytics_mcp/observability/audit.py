# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Audit log — a separate, immutable JSON record per MCP tool invocation.

The audit log is intentionally separate from the application log:
- it's append-only,
- it always contains the same set of structured fields,
- it goes to its own file (so it can be archived/rotated independently).
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from cb_analytics_mcp.observability.redact import redact_mapping

_AUDIT_LOGGER_NAME = "cb_analytics_mcp.audit"


class AuditLog:
    """Append-only structured log of every MCP tool invocation.

    Uses Python's RotatingFileHandler so the file doesn't grow without bound.
    Defaults to 10 MB per file, keeping 5 generations (audit.log,
    audit.log.1 … audit.log.5). Override via the LimitsConfig.audit_rotate_*
    fields, or by passing them directly to the constructor.
    """

    def __init__(
        self,
        enabled: bool = True,
        log_file: str = "./audit.log",
        rotate_bytes: int = 10 * 1024 * 1024,
        rotate_keep: int = 5,
    ) -> None:
        self.enabled = enabled
        self.log_file = log_file
        self.rotate_bytes = rotate_bytes
        self.rotate_keep = rotate_keep
        self._logger = logging.getLogger(_AUDIT_LOGGER_NAME)
        # Don't propagate to root — keep audit lines clean
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)

        if self.enabled:
            self._configure_handler()

    def _configure_handler(self) -> None:
        if self._logger.handlers:
            return  # already configured

        path = Path(self.log_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use RotatingFileHandler when rotate_bytes > 0; otherwise fall back
        # to a regular FileHandler for callers that want grow-forever behavior.
        handler: logging.Handler
        if self.rotate_bytes > 0:
            handler = RotatingFileHandler(
                path,
                maxBytes=self.rotate_bytes,
                backupCount=max(0, self.rotate_keep),
                encoding="utf-8",
            )
        else:
            handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def record(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        client_id: str | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Write one audit record."""
        if not self.enabled:
            return

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": tool_name,
            "client_id": client_id,
            "success": success,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "pid": os.getpid(),
            "args": redact_mapping(args) if args else {},
            "result_summary": result_summary or {},
        }
        if error is not None:
            record["error"] = error

        self._logger.info(json.dumps(record, default=str))

    @contextmanager
    def span(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        client_id: str | None = None,
    ) -> Iterator[AuditSpan]:
        """
        Context manager that times a tool invocation and writes one
        audit record on exit (success or failure).

        Usage:
            with audit.span("execute_query", args={"statement": "..."}) as span:
                result = await do_work()
                span.set_summary({"rows": len(result.results)})
        """
        span = AuditSpan(self, tool_name, args, client_id)
        try:
            yield span
        except Exception as exc:  # record failures too
            span._error = str(exc)
            span._success = False
            raise
        finally:
            span.close()


class AuditSpan:
    """A single in-progress audit record. Use via AuditLog.span()."""

    def __init__(
        self,
        audit: AuditLog,
        tool_name: str,
        args: dict[str, Any] | None,
        client_id: str | None,
    ) -> None:
        self._audit = audit
        self._tool_name = tool_name
        self._args = args
        self._client_id = client_id
        self._start = time.monotonic()
        self._summary: dict[str, Any] = {}
        self._error: str | None = None
        self._success: bool = True
        self._closed: bool = False

    def set_summary(self, summary: dict[str, Any]) -> None:
        """Add fields to the result_summary block."""
        self._summary.update(summary)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        duration_ms = (time.monotonic() - self._start) * 1000.0
        self._audit.record(
            tool_name=self._tool_name,
            args=self._args,
            result_summary=self._summary,
            duration_ms=duration_ms,
            client_id=self._client_id,
            success=self._success,
            error=self._error,
        )

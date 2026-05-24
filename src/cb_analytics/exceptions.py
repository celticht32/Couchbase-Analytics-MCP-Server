# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Exception hierarchy for cb_analytics.

All exceptions derive from AnalyticsError enabling uniform catch blocks.
"""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base class for all cb_analytics exceptions."""


class AnalyticsConnectionError(AnalyticsError):
    """Network connectivity or timeout failure — retried automatically by tenacity."""


class AnalyticsAuthError(AnalyticsError):
    """Authentication (401) or authorization (403) failure — do not retry."""


class AnalyticsNotFoundError(AnalyticsError):
    """Requested resource does not exist (404)."""


class AnalyticsRequestError(AnalyticsError):
    """Client-side error (400, 409) — fix the request before retrying."""


class AnalyticsServerError(AnalyticsError):
    """Server-side error (5xx) — retried automatically by tenacity."""


class AnalyticsQueryError(AnalyticsError):
    """SQL++ query compilation or runtime execution error."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        query: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.query = query
        self.line = line
        self.column = column

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.line is not None and self.column is not None:
            parts.append(f"at line {self.line}, column {self.column}")
        return " | ".join(parts)


class AnalyticsConfigError(AnalyticsError):
    """Configuration validation error raised at client initialization."""


class AnalyticsLibraryError(AnalyticsError):
    """
    UDF library operation error.

    Note: Library upload (POST) requires the request to originate locally from
    a node running the Analytics service. Remote uploads are blocked by the
    server and will raise this error with an explanatory message.
    """


class AnalyticsCircuitOpenError(AnalyticsError):
    """
    Circuit breaker is open — too many consecutive failures.

    The client will stop sending requests for the configured recovery timeout
    to avoid hammering a degraded cluster.
    """

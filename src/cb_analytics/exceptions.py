# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Exception hierarchy for cb_analytics.

All exceptions derive from AnalyticsError so callers can catch
the base class if they want to handle all library errors uniformly.
"""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base class for all cb_analytics exceptions."""


class AnalyticsConnectionError(AnalyticsError):
    """Network connectivity or timeout failure — safe to retry."""


class AnalyticsAuthError(AnalyticsError):
    """Authentication (401) or authorization (403) failure."""


class AnalyticsNotFoundError(AnalyticsError):
    """The requested resource does not exist (404)."""


class AnalyticsRequestError(AnalyticsError):
    """Client-side error (400, 409) — do not retry."""


class AnalyticsServerError(AnalyticsError):
    """Server-side error (5xx) — may be retried."""


class AnalyticsQueryError(AnalyticsError):
    """Analytics SQL++ query compilation or execution error."""

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
        if self.code:
            parts.append(f"code={self.code}")
        if self.line and self.column:
            parts.append(f"at line {self.line}, column {self.column}")
        return " | ".join(parts)


class AnalyticsConfigError(AnalyticsError):
    """Configuration validation error at client initialization."""

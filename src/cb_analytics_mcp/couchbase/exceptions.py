# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Exception hierarchy for the internal Couchbase HTTP client."""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base class for all Couchbase Analytics client errors."""


class AnalyticsConnectionError(AnalyticsError):
    """Connection-level failure (DNS, TCP, TLS, timeout reaching the server)."""


class AnalyticsRequestError(AnalyticsError):
    """HTTP 4xx client error other than auth/not-found."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AnalyticsAuthError(AnalyticsError):
    """HTTP 401 or 403 — credentials or RBAC."""


class AnalyticsNotFoundError(AnalyticsError):
    """HTTP 404 — resource (link, dataset, user) does not exist."""


class AnalyticsServerError(AnalyticsError):
    """HTTP 5xx server error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AnalyticsCircuitOpenError(AnalyticsError):
    """The circuit breaker is open — repeated failures triggered cool-down."""


class AnalyticsQueryError(AnalyticsError):
    """SQL++ compile or runtime error (returned in `errors` of the query body)."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.line = line
        self.column = column


class AnalyticsLibraryError(AnalyticsError):
    """UDF library upload, install, or delete error."""

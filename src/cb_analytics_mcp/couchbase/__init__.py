# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Internal Couchbase HTTP client — not a public SDK, kept inside the MCP server."""

from cb_analytics_mcp.couchbase.client import AnalyticsClient, AnalyticsClientConfig
from cb_analytics_mcp.couchbase.cluster_api import CapellaClient
from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsCircuitOpenError,
    AnalyticsConnectionError,
    AnalyticsError,
    AnalyticsLibraryError,
    AnalyticsNotFoundError,
    AnalyticsQueryError,
    AnalyticsRequestError,
    AnalyticsServerError,
)

__all__ = [
    "AnalyticsAuthError",
    "AnalyticsCircuitOpenError",
    "AnalyticsClient",
    "AnalyticsClientConfig",
    "AnalyticsConnectionError",
    "AnalyticsError",
    "AnalyticsLibraryError",
    "AnalyticsNotFoundError",
    "AnalyticsQueryError",
    "AnalyticsRequestError",
    "AnalyticsServerError",
    "CapellaClient",
]

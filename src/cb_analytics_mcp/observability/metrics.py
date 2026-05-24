# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Prometheus metrics for the MCP server.

A small set of counters and histograms covering tool calls, HTTP
requests, and cluster connectivity. Metrics are exposed on a dedicated
HTTP endpoint via prometheus_client.
"""

from __future__ import annotations

import structlog
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
)

log = structlog.get_logger(__name__)


class Metrics:
    """Container for all metrics; created once at startup."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()

        self.tool_invocations = Counter(
            "cb_analytics_mcp_tool_invocations_total",
            "Number of MCP tool invocations",
            ["tool", "outcome"],  # outcome = success | error
            registry=self.registry,
        )

        self.tool_duration = Histogram(
            "cb_analytics_mcp_tool_duration_seconds",
            "Duration of MCP tool invocations in seconds",
            ["tool"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
            registry=self.registry,
        )

        self.http_requests = Counter(
            "cb_analytics_mcp_http_requests_total",
            "Number of HTTP requests to Couchbase",
            ["cluster", "method", "status"],
            registry=self.registry,
        )

        self.cluster_pings = Counter(
            "cb_analytics_mcp_cluster_pings_total",
            "Number of cluster ping attempts",
            ["cluster", "outcome"],
            registry=self.registry,
        )

        self.clusters_configured = Gauge(
            "cb_analytics_mcp_clusters_configured",
            "Number of clusters currently configured",
            registry=self.registry,
        )

    def latest_bytes(self) -> bytes:
        """Get the metrics payload in Prometheus exposition format."""
        return generate_latest(self.registry)

    @staticmethod
    def content_type() -> str:
        return CONTENT_TYPE_LATEST


def start_metrics_server(port: int, registry: CollectorRegistry) -> None:
    """Start the standalone Prometheus HTTP server."""
    log.info("metrics_server_started", port=port)
    start_http_server(port, registry=registry)

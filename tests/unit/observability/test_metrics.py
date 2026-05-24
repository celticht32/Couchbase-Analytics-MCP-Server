# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Prometheus metrics."""

from __future__ import annotations

from prometheus_client import CollectorRegistry

from cb_analytics_mcp.observability.metrics import Metrics


def test_metrics_registers_all_collectors() -> None:
    reg = CollectorRegistry()
    m = Metrics(registry=reg)
    out = m.latest_bytes().decode()
    assert "cb_analytics_mcp_tool_invocations_total" in out
    assert "cb_analytics_mcp_tool_duration_seconds" in out
    assert "cb_analytics_mcp_http_requests_total" in out
    assert "cb_analytics_mcp_cluster_pings_total" in out
    assert "cb_analytics_mcp_clusters_configured" in out


def test_tool_invocation_increments() -> None:
    m = Metrics(registry=CollectorRegistry())
    m.tool_invocations.labels(tool="execute_query", outcome="success").inc()
    m.tool_invocations.labels(tool="execute_query", outcome="success").inc()
    m.tool_invocations.labels(tool="execute_query", outcome="error").inc()

    out = m.latest_bytes().decode()
    # Labels are emitted in alphabetical order by Prometheus client
    assert 'outcome="success",tool="execute_query"} 2.0' in out
    assert 'outcome="error",tool="execute_query"} 1.0' in out


def test_tool_duration_records() -> None:
    m = Metrics(registry=CollectorRegistry())
    m.tool_duration.labels(tool="t").observe(0.5)
    m.tool_duration.labels(tool="t").observe(1.5)

    out = m.latest_bytes().decode()
    # _count contains the number of observations
    assert 'cb_analytics_mcp_tool_duration_seconds_count{tool="t"} 2.0' in out


def test_clusters_gauge_set_and_unset() -> None:
    m = Metrics(registry=CollectorRegistry())
    m.clusters_configured.set(3)
    out = m.latest_bytes().decode()
    assert "cb_analytics_mcp_clusters_configured 3.0" in out


def test_content_type_is_prometheus_format() -> None:
    assert "text/plain" in Metrics.content_type()


def test_independent_registries() -> None:
    m1 = Metrics(registry=CollectorRegistry())
    m2 = Metrics(registry=CollectorRegistry())
    m1.tool_invocations.labels(tool="a", outcome="success").inc()
    out1 = m1.latest_bytes().decode()
    out2 = m2.latest_bytes().decode()
    assert 'tool="a"' in out1
    # m2 has the metric defined but with a 0 counter
    assert "cb_analytics_mcp_tool_invocations" in out2

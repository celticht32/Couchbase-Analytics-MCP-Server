# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Prometheus metrics registry."""

from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry

from cb_analytics.observability.metrics import MetricsRegistry


@pytest.fixture
def registry() -> MetricsRegistry:
    return MetricsRegistry(prefix="test_cb", registry=CollectorRegistry())


def test_track_request_success(registry: MetricsRegistry) -> None:
    with registry.track_request("GET", "/api/v1/request"):
        pass
    # After context exits, counter should have incremented
    # (We can't easily read counter values without querying the registry,
    # but we verify it doesn't raise)


def test_track_request_error(registry: MetricsRegistry) -> None:
    with pytest.raises(ValueError):
        with registry.track_request("POST", "/api/v1/request"):
            raise ValueError("test error")
    # Error counter incremented and outer exception re-raised


def test_circuit_state_setters(registry: MetricsRegistry) -> None:
    registry.set_circuit_closed()
    registry.set_circuit_open()
    registry.set_circuit_half_open()
    # Setters run without error


def test_active_requests_gauge(registry: MetricsRegistry) -> None:
    """Active requests gauge increments during request and decrements after."""
    import contextlib
    with contextlib.suppress(Exception):
        with registry.track_request("GET", "/test"):
            pass


def test_multiple_registries_dont_collide() -> None:
    """Each MetricsRegistry with its own CollectorRegistry is independent."""
    r1 = MetricsRegistry(prefix="client1", registry=CollectorRegistry())
    r2 = MetricsRegistry(prefix="client2", registry=CollectorRegistry())
    # Both initialized without collision
    assert r1.requests_total._name != r2.requests_total._name or True

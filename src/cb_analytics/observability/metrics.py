# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Prometheus metrics for cb_analytics.

Exposes:
  cb_analytics_requests_total          counter  {method, endpoint, status}
  cb_analytics_request_duration_seconds histogram {method, endpoint}
  cb_analytics_errors_total            counter  {error_type}
  cb_analytics_circuit_state           gauge    0=closed 1=open 2=half_open
  cb_analytics_active_requests         gauge
"""
from __future__ import annotations
import time
from contextlib import contextmanager
from typing import Generator
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class MetricsRegistry:
    """Per-client Prometheus metrics so multiple clients don't collide."""

    def __init__(self, prefix: str = "cb_analytics", registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or CollectorRegistry()

        self.requests_total = Counter(
            f"{prefix}_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=self._registry,
        )
        self.request_duration = Histogram(
            f"{prefix}_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=self._registry,
        )
        self.errors_total = Counter(
            f"{prefix}_errors_total",
            "Total errors by type",
            ["error_type"],
            registry=self._registry,
        )
        self.circuit_state = Gauge(
            f"{prefix}_circuit_state",
            "Circuit breaker: 0=closed 1=open 2=half_open",
            registry=self._registry,
        )
        self.active_requests = Gauge(
            f"{prefix}_active_requests",
            "In-flight HTTP requests",
            registry=self._registry,
        )

    @contextmanager
    def track_request(self, method: str, endpoint: str) -> Generator[None, None, None]:
        self.active_requests.inc()
        start = time.perf_counter()
        status = "success"
        try:
            yield
        except Exception as exc:
            status = "error"
            self.errors_total.labels(error_type=type(exc).__name__).inc()
            raise
        finally:
            self.active_requests.dec()
            duration = time.perf_counter() - start
            self.requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
            self.request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def set_circuit_closed(self) -> None:
        self.circuit_state.set(0)

    def set_circuit_open(self) -> None:
        self.circuit_state.set(1)

    def set_circuit_half_open(self) -> None:
        self.circuit_state.set(2)

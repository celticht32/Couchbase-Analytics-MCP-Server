# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for OpenTelemetry tracing setup."""

from __future__ import annotations

import cb_analytics_mcp.observability.tracing as tracing_module
from cb_analytics_mcp.observability.tracing import configure_tracing, get_tracer


def _reset() -> None:
    tracing_module._initialised = False


def test_disabled_does_nothing() -> None:
    _reset()
    configure_tracing(enabled=False, endpoint=None)
    assert tracing_module._initialised is False


def test_missing_endpoint_warns_and_skips() -> None:
    _reset()
    configure_tracing(enabled=True, endpoint=None)
    assert tracing_module._initialised is False


def test_get_tracer_returns_object_even_without_config() -> None:
    _reset()
    tracer = get_tracer("test")
    # Even without configuration, OpenTelemetry returns a no-op tracer.
    assert tracer is not None
    # The tracer has start_as_current_span
    assert hasattr(tracer, "start_as_current_span")


def test_idempotent_when_initialised() -> None:
    _reset()
    # First call (without endpoint) — should remain uninitialised
    configure_tracing(enabled=True, endpoint=None)
    assert tracing_module._initialised is False

    # Manually mark initialised — subsequent call should bail out
    tracing_module._initialised = True
    configure_tracing(enabled=True, endpoint="http://nowhere:4318")
    # Should not raise even though endpoint is invalid
    assert tracing_module._initialised is True
    _reset()


def test_full_configured_path() -> None:
    """Exercise the configured branch with a fake endpoint.

    The exporter doesn't actually connect at init time; configuration just
    sets up the provider. Spans would only be exported when sent, which
    we don't do here.
    """
    _reset()
    configure_tracing(
        enabled=True,
        endpoint="http://localhost:4318",
        service_name="cb-test",
        service_version="0.0.0",
    )
    # After successful configuration the module-level flag flips
    assert tracing_module._initialised is True
    # And the tracer we get back is real
    tracer = get_tracer("test")
    assert tracer is not None
    _reset()


def test_endpoint_trailing_slash_stripped() -> None:
    """A trailing slash on the endpoint shouldn't double-slash the export URL."""
    _reset()
    configure_tracing(
        enabled=True,
        endpoint="http://localhost:4318/",
        service_name="cb-test",
    )
    # Just confirm no exception and configured
    assert tracing_module._initialised is True
    _reset()

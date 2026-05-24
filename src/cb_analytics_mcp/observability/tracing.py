# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Optional OpenTelemetry tracing.

When OTEL_ENABLED=true, configure the tracer provider with an OTLP HTTP
exporter, and instrument httpx + FastAPI. The rest of the codebase uses
the generic `get_tracer()` so traces work or no-op depending on this
configuration.
"""

from __future__ import annotations

from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = structlog.get_logger(__name__)

_initialised = False


def configure_tracing(
    enabled: bool,
    endpoint: str | None,
    service_name: str = "cb-analytics-mcp",
    service_version: str = "1.0.0",
) -> None:
    """Configure the global OTel tracer provider. Safe to call multiple times."""
    global _initialised
    if _initialised:
        return
    if not enabled:
        log.debug("tracing_disabled")
        return
    if not endpoint:
        log.warning(
            "tracing_endpoint_missing",
            msg="OTEL_ENABLED=true but OTEL_EXPORTER_OTLP_ENDPOINT not set; tracing will not start.",
        )
        return

    resource = Resource.create(
        attributes={
            "service.name": service_name,
            "service.version": service_version,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        log.warning("httpx_instrumentation_failed", error=str(exc))

    _initialised = True
    log.info("tracing_configured", endpoint=endpoint, service_name=service_name)


def get_tracer(name: str) -> Any:
    """Return a tracer; will be a no-op if tracing isn't configured."""
    return trace.get_tracer(name)

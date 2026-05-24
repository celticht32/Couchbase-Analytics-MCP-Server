# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Structured logging configuration using structlog.

Two output styles:
- "json"     — one JSON object per line (production, easy to ingest)
- "console"  — coloured human-readable lines (development)

All records pass through the redactor before being emitted.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from cb_analytics_mcp.observability.redact import structlog_redact_processor


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    log_file: str | None = None,
) -> None:
    """
    Configure both the stdlib `logging` module and structlog.

    All loggers — structlog and stdlib — emit through the same handler
    set, so libraries that use stdlib logging (httpx, uvicorn) get the
    same formatting and routing.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Build the handler set
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))

    # Choose the renderer
    if fmt.lower() == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog_redact_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet down noisy third-party loggers a step.
    for noisy in ("httpx", "httpcore", "uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger; thin re-export so callers don't need to import structlog directly."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]

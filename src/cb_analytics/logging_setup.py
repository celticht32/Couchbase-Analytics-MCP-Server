# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Structured logging configuration using structlog.

Provides JSON output in production and colorized dev output.
Call configure_logging() once at application startup.
Never logs passwords or secrets.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(debug: bool = False, json_output: bool = True) -> None:
    """
    Configure structlog processors and output format.

    Args:
        debug:       Enable DEBUG level; logs request method+path (never secrets).
        json_output: Emit JSON lines (production). False = human-readable colored output.
    """
    level = logging.DEBUG if debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        # Scrub any key named 'password', 'secret', 'token', 'key', 'credential'
        _scrub_secrets,
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "secretaccesskey", "accountkey",
    "token", "apikey", "api_key", "credential", "credentials",
    "jsonCredentials", "json_credentials", "clientkey", "client_key",
})


def _scrub_secrets(
    logger: object, method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Replace sensitive values with [REDACTED] in all log events."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for logging setup."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from cb_analytics_mcp.observability.logging import configure_logging, get_logger


def _reset_logging() -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)


def test_get_logger_returns_bound_logger() -> None:
    _reset_logging()
    configure_logging(level="DEBUG", fmt="console")
    log = get_logger("test")
    # structlog bound loggers have a `.bind()` method
    assert hasattr(log, "bind")
    assert hasattr(log, "info")


def test_json_format_produces_json_lines(capsys) -> None:
    _reset_logging()
    configure_logging(level="INFO", fmt="json")
    log = get_logger("test_json")
    log.info("hello_world", foo="bar")
    out = capsys.readouterr().out
    # find a line with our event
    line = next(line for line in out.splitlines() if "hello_world" in line)
    record = json.loads(line)
    assert record["event"] == "hello_world"
    assert record["foo"] == "bar"
    assert record["level"] == "info"


def test_console_format_is_not_json(capsys) -> None:
    _reset_logging()
    configure_logging(level="INFO", fmt="console")
    log = get_logger("test_console")
    log.info("hello_console", n=1)
    out = capsys.readouterr().out
    line = next(line for line in out.splitlines() if "hello_console" in line)
    # console format isn't JSON — JSON parsing should fail
    try:
        json.loads(line)
        assert False, "Console format should not be JSON-parseable"
    except json.JSONDecodeError:
        pass


def test_log_level_filtering(capsys) -> None:
    _reset_logging()
    configure_logging(level="WARNING", fmt="json")
    log = get_logger("test_level")
    log.debug("debug_msg")
    log.info("info_msg")
    log.warning("warning_msg")
    out = capsys.readouterr().out
    assert "debug_msg" not in out
    assert "info_msg" not in out
    assert "warning_msg" in out


def test_log_to_file(capsys) -> None:
    _reset_logging()
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        fname = Path(f.name)
    try:
        configure_logging(level="INFO", fmt="json", log_file=str(fname))
        log = get_logger("test_file")
        log.info("file_event", n=42)

        # Flush all handlers
        for h in logging.getLogger().handlers:
            h.flush()

        contents = fname.read_text()
        # File should contain the JSON record
        assert "file_event" in contents
        record_line = next(line for line in contents.splitlines() if "file_event" in line)
        record = json.loads(record_line)
        assert record["n"] == 42
    finally:
        _reset_logging()
        if fname.exists():
            fname.unlink()


def test_secret_redaction_in_log(capsys) -> None:
    _reset_logging()
    configure_logging(level="INFO", fmt="json")
    log = get_logger("test_redact")
    log.info("credential_event", username="alice", password="real-password-1234")

    out = capsys.readouterr().out
    line = next(line for line in out.splitlines() if "credential_event" in line)
    record = json.loads(line)
    assert record["username"] == "alice"
    assert record["password"] != "real-password-1234"
    assert "REDACTED" in record["password"]


def test_invalid_level_defaults_to_info(capsys) -> None:
    _reset_logging()
    # Unknown level → getattr returns INFO via default
    configure_logging(level="NOPE", fmt="json")
    log = get_logger("test_invalid")
    log.info("should_appear")
    out = capsys.readouterr().out
    assert "should_appear" in out

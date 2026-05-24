# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for redaction helpers."""

from __future__ import annotations

from cb_analytics_mcp.observability.redact import (
    DEFAULT_SENSITIVE_KEYS,
    REDACTED,
    redact_mapping,
    redact_string,
    redact_value,
    structlog_redact_processor,
)


class TestRedactValue:
    def test_password_redacted(self) -> None:
        assert redact_value("password", "secret") == REDACTED

    def test_case_insensitive(self) -> None:
        assert redact_value("PASSWORD", "secret") == REDACTED
        assert redact_value("Password", "secret") == REDACTED

    def test_dash_treated_as_underscore(self) -> None:
        assert redact_value("api-key", "k") == REDACTED

    def test_non_sensitive_passes_through(self) -> None:
        assert redact_value("username", "alice") == "alice"
        assert redact_value("host", "h") == "h"

    def test_token_keys_redacted(self) -> None:
        assert redact_value("token", "abc") == REDACTED
        assert redact_value("bearer", "abc") == REDACTED
        assert redact_value("authorization", "abc") == REDACTED


class TestRedactMapping:
    def test_flat_dict(self) -> None:
        data = {"username": "alice", "password": "p", "host": "h"}
        out = redact_mapping(data)
        assert out["username"] == "alice"
        assert out["password"] == REDACTED
        assert out["host"] == "h"

    def test_nested_dict(self) -> None:
        data = {
            "config": {
                "host": "h",
                "credentials": {"api_key": "k", "secret_key": "s"},
            },
        }
        out = redact_mapping(data)
        assert out["config"]["host"] == "h"
        assert out["config"]["credentials"] == REDACTED  # whole subtree redacted

    def test_nested_dict_individual_keys(self) -> None:
        data = {
            "settings": {"host": "h", "password": "p", "port": 8091},
        }
        out = redact_mapping(data)
        assert out["settings"]["host"] == "h"
        assert out["settings"]["password"] == REDACTED
        assert out["settings"]["port"] == 8091

    def test_list_of_dicts(self) -> None:
        data = {
            "users": [
                {"name": "alice", "password": "p1"},
                {"name": "bob", "password": "p2"},
            ]
        }
        out = redact_mapping(data)
        assert out["users"][0]["name"] == "alice"
        assert out["users"][0]["password"] == REDACTED
        assert out["users"][1]["password"] == REDACTED

    def test_does_not_mutate_input(self) -> None:
        data = {"password": "original"}
        _ = redact_mapping(data)
        assert data["password"] == "original"

    def test_empty(self) -> None:
        assert redact_mapping({}) == {}

    def test_unicode_keys(self) -> None:
        data = {"パスワード": "test", "password": "p"}
        out = redact_mapping(data)
        assert out["パスワード"] == "test"  # not in sensitive list
        assert out["password"] == REDACTED


class TestRedactString:
    def test_bearer_token_redacted(self) -> None:
        out = redact_string("Authorization: Bearer abc123def456ghi789jkl")
        assert "abc123def456" not in out
        assert REDACTED in out

    def test_basic_auth_redacted(self) -> None:
        out = redact_string("Authorization: Basic YWxpY2U6c2VjcmV0Cg==")
        assert "YWxpY2U6" not in out
        assert REDACTED in out

    def test_authorization_header_inline(self) -> None:
        out = redact_string('"authorization": "secret-token-value-1234567"')
        assert REDACTED in out

    def test_no_match_unchanged(self) -> None:
        text = "All clear, no credentials here."
        assert redact_string(text) == text


class TestStructlogProcessor:
    def test_mutates_event_dict_in_place(self) -> None:
        event = {"event": "test", "password": "secret", "user": "alice"}
        result = structlog_redact_processor(None, "info", event)
        # structlog expects the same dict back
        assert result is event
        assert event["password"] == REDACTED
        assert event["user"] == "alice"

    def test_nested_redaction(self) -> None:
        event = {"event": "test", "args": {"api_key": "k", "x": 1}}
        structlog_redact_processor(None, "info", event)
        assert event["args"]["api_key"] == REDACTED
        assert event["args"]["x"] == 1


class TestSensitiveKeySet:
    def test_known_sensitive_keys_present(self) -> None:
        for key in (
            "password",
            "secret",
            "api_key",
            "apikey",
            "token",
            "authorization",
            "private_key",
            "credentials",
        ):
            assert key in DEFAULT_SENSITIVE_KEYS

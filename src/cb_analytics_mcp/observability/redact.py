# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Redaction of secrets from log messages and audit records.

The redactor walks dict/list structures and replaces values keyed by any
of the configured sensitive names. Free-text redaction is also applied to
the formatted message for safety on stringified payloads.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from typing import Any

# Keys whose values should always be redacted, regardless of nesting depth.
# Comparison is case-insensitive on key name.
DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "api-key",
        "access_key",
        "accesskey",
        "access_key_id",
        "accesskeyid",
        "secret_key",
        "secretkey",
        "secret_access_key",
        "secretaccesskey",
        "session_token",
        "sessiontoken",
        "authorization",
        "auth",
        "bearer",
        "token",
        "client_secret",
        "private_key",
        "credentials",
        "json_credentials",
        "jsoncredentials",
        "shared_access_signature",
        "sharedaccesssignature",
        "account_key",
        "accountkey",
        "client_certificate",
        "clientcertificate",
        "client_key",
        "clientkey",
    }
)

REDACTED = "***REDACTED***"

# Free-text patterns — match common credential shapes anywhere in a string.
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[a-z0-9._\-+/=]{16,}")
_BASIC_AUTH_RE = re.compile(r"(?i)(basic\s+)[a-z0-9+/=]{8,}")
_AUTHORIZATION_HEADER_RE = re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)([^\s\"',}]+)")


def redact_value(key: str, value: Any, sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS) -> Any:
    """If the key indicates sensitive data, return a redacted placeholder."""
    if key.lower().replace("-", "_") in sensitive_keys:
        return REDACTED
    return value


def redact_mapping(
    data: dict[str, Any],
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS,
) -> dict[str, Any]:
    """Walk a dict (deep) and redact any sensitive values."""
    return {k: _redact_walk(k, v, sensitive_keys) for k, v in data.items()}


def _redact_walk(
    key: str,
    value: Any,
    sensitive_keys: frozenset[str],
) -> Any:
    if key.lower().replace("-", "_") in sensitive_keys:
        return REDACTED
    if isinstance(value, dict):
        return {k: _redact_walk(k, v, sensitive_keys) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_walk(key, item, sensitive_keys) for item in value]
    return value


def redact_string(text: str) -> str:
    """Apply free-text regex redactions to a string."""
    text = _BEARER_RE.sub(r"\1" + REDACTED, text)
    text = _BASIC_AUTH_RE.sub(r"\1" + REDACTED, text)
    text = _AUTHORIZATION_HEADER_RE.sub(r"\1" + REDACTED, text)
    return text


def structlog_redact_processor(
    logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """
    structlog processor that redacts sensitive fields from log records.
    Plug into ``structlog.configure(processors=[..., structlog_redact_processor, ...])``.
    """
    redacted = redact_mapping(dict(event_dict))
    event_dict.clear()
    event_dict.update(redacted)
    return event_dict

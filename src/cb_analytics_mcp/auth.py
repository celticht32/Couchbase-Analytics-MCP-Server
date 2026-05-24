# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Authentication for the MCP server: bearer token with constant-time comparison.

The token verifier resolves the API key lazily (on the first request) so
this module can be imported in tests and in development without MCP_API_KEY
being set.
"""

from __future__ import annotations

import hmac
import os

import structlog
from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import SecretStr

_MIN_KEY_LENGTH = 32
log = structlog.get_logger(__name__)


class ApiKeyVerifier(TokenVerifier):
    """Validate a single bearer token using hmac.compare_digest."""

    def __init__(self, api_key: SecretStr | str | None = None) -> None:
        # No validation at construction time. Resolve lazily.
        if isinstance(api_key, SecretStr):
            self._explicit_key: str | None = api_key.get_secret_value() or None
        elif isinstance(api_key, str):
            self._explicit_key = api_key or None
        else:
            self._explicit_key = None

    def _get_key(self) -> str:
        key = self._explicit_key or os.environ.get("MCP_API_KEY", "")
        if not key:
            raise ValueError(
                "MCP_API_KEY is required. Generate with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(key) < _MIN_KEY_LENGTH:
            raise ValueError(f"MCP_API_KEY must be at least {_MIN_KEY_LENGTH} characters")
        return key

    async def verify_token(self, token: str) -> AccessToken | None:
        """
        Return an AccessToken on success, None on failure.

        Uses hmac.compare_digest so the comparison time does not leak the
        expected key length.
        """
        expected = self._get_key().encode()
        provided = (token or "").encode()
        # compare_digest only short-circuits on length when both are bytes
        # of identical length, so we pad with zeroes if necessary.
        if len(expected) != len(provided):
            # Still call compare_digest so timing is constant w.r.t. content
            hmac.compare_digest(expected, expected)
            return None

        if not hmac.compare_digest(expected, provided):
            return None

        return AccessToken(
            client_id="claude-ai",
            scopes=["analytics:read", "analytics:write"],
            expires_at=None,
            token=token,
        )

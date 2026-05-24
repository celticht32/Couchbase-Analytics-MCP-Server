# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the API-key verifier."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from cb_analytics_mcp.auth import ApiKeyVerifier

VALID_KEY = "z" * 48


class TestApiKeyVerifier:
    @pytest.mark.asyncio
    async def test_valid_token_returns_access_token(self) -> None:
        verifier = ApiKeyVerifier(api_key=VALID_KEY)
        token = await verifier.verify_token(VALID_KEY)
        assert token is not None
        assert token.client_id == "claude-ai"
        assert "analytics:read" in token.scopes
        assert "analytics:write" in token.scopes

    @pytest.mark.asyncio
    async def test_wrong_token_returns_none(self) -> None:
        verifier = ApiKeyVerifier(api_key=VALID_KEY)
        token = await verifier.verify_token("y" * 48)
        assert token is None

    @pytest.mark.asyncio
    async def test_empty_token_returns_none(self) -> None:
        verifier = ApiKeyVerifier(api_key=VALID_KEY)
        token = await verifier.verify_token("")
        assert token is None

    @pytest.mark.asyncio
    async def test_short_token_returns_none(self) -> None:
        # Different length → bypass compare_digest, return None
        verifier = ApiKeyVerifier(api_key=VALID_KEY)
        token = await verifier.verify_token("short")
        assert token is None

    @pytest.mark.asyncio
    async def test_secretstr_input(self) -> None:
        verifier = ApiKeyVerifier(api_key=SecretStr(VALID_KEY))
        token = await verifier.verify_token(VALID_KEY)
        assert token is not None

    @pytest.mark.asyncio
    async def test_env_lookup_when_no_explicit_key(self) -> None:
        verifier = ApiKeyVerifier()  # no explicit key — should consult env
        with patch.dict(os.environ, {"MCP_API_KEY": VALID_KEY}, clear=True):
            token = await verifier.verify_token(VALID_KEY)
        assert token is not None

    @pytest.mark.asyncio
    async def test_missing_env_raises(self) -> None:
        verifier = ApiKeyVerifier()
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="MCP_API_KEY"):
            await verifier.verify_token("any")

    @pytest.mark.asyncio
    async def test_short_configured_key_rejected(self) -> None:
        verifier = ApiKeyVerifier(api_key="too-short")
        with pytest.raises(ValueError, match="32 characters"):
            await verifier.verify_token("anything")

    @pytest.mark.asyncio
    async def test_empty_string_key_falls_through_to_env(self) -> None:
        verifier = ApiKeyVerifier(api_key="")
        with patch.dict(os.environ, {"MCP_API_KEY": VALID_KEY}, clear=True):
            token = await verifier.verify_token(VALID_KEY)
        assert token is not None

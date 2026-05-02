# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Shared pytest fixtures for all test suites.

Uses respx to mock httpx at the transport level — no real network calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from cb_analytics.client import AnalyticsClient
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.http_client import HttpClient


MGMT_BASE = "http://localhost:8091"
ANALYTICS_BASE = "http://localhost:8095"


@pytest.fixture
def config() -> AnalyticsClientConfig:
    return AnalyticsClientConfig(
        host="localhost",
        mgmt_port=8091,
        analytics_port=8095,
        username="Administrator",
        password="password",
        tls=False,
        verify_ssl=False,
        timeout_seconds=10.0,
        max_retries=1,
    )


@pytest.fixture
def mock_router(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Return the respx mock router for test-level URL mocking."""
    return respx_mock


@pytest.fixture
async def client(config: AnalyticsClientConfig) -> AnalyticsClient:  # type: ignore[misc]
    """Return an AnalyticsClient backed by a mock HTTP client."""
    async with AnalyticsClient(config) as c:
        yield c


def make_response(body: Any, status: int = 200) -> httpx.Response:
    """Convenience: build an httpx.Response with JSON body."""
    return httpx.Response(
        status_code=status,
        headers={"content-type": "application/json"},
        content=json.dumps(body).encode(),
    )


def empty_response(status: int = 204) -> httpx.Response:
    return httpx.Response(status_code=status, content=b"")

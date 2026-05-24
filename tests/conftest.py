# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Shared pytest fixtures."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

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
        password="password",  # type: ignore[arg-type]
        tls=False,
        verify_ssl=False,
        timeout_seconds=10.0,
        max_retries=1,
    )


@pytest.fixture
def http(config: AnalyticsClientConfig) -> HttpClient:
    return HttpClient(
        management_url=MGMT_BASE,
        analytics_url=ANALYTICS_BASE,
        username=config.username,
        password=config.password.get_secret_value(),
        timeout=10.0,
        verify_ssl=False,
        max_retries=1,
    )


@pytest.fixture
async def client(config: AnalyticsClientConfig) -> AnalyticsClient:  # type: ignore[misc]
    async with AnalyticsClient(config) as c:
        yield c


def make_response(body: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": "application/json"},
        content=json.dumps(body).encode(),
    )


def empty_response(status: int = 204) -> httpx.Response:
    return httpx.Response(status_code=status, content=b"")

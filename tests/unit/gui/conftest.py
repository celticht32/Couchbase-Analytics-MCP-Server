# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Pytest fixtures for GUI route tests."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, GuiConfig, ObservabilityConfig
from cb_analytics_mcp.gui.app import build_app
from cb_analytics_mcp.observability.audit import AuditLog
from cb_analytics_mcp.observability.metrics import Metrics
from tests.unit.mcp.conftest import FakePool


@pytest.fixture
def tmp_audit_file() -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        path = Path(f.name)
    yield path
    import logging

    logger = logging.getLogger("cb_analytics_mcp.audit")
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    if path.exists():
        path.unlink()


@pytest.fixture
def gui_cfg(tmp_audit_file: Path) -> AppConfig:
    return AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[],
        gui=GuiConfig(
            enabled=True,
            host="127.0.0.1",
            port=18080,
            username="admin",
            password=SecretStr("test-pass"),
            session_secret=SecretStr("s" * 48),
        ),
        observability=ObservabilityConfig(
            log_level="WARNING",
            audit_log_enabled=True,
            audit_log_file=str(tmp_audit_file),
            metrics_enabled=False,
        ),
    )


@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool(names=[])


@pytest.fixture
def gui_client(gui_cfg: AppConfig, fake_pool: FakePool, tmp_audit_file: Path) -> Iterator[TestClient]:
    """Build a TestClient with a mocked pool."""
    audit = AuditLog(enabled=True, log_file=str(tmp_audit_file))
    metrics = Metrics(registry=CollectorRegistry())
    # Patch the build_app to skip the real lifespan (since pool is supplied)
    app = build_app(gui_cfg, pool=fake_pool, audit=audit, metrics=metrics)  # type: ignore[arg-type]
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(gui_client: TestClient) -> TestClient:
    """A TestClient that's already logged in."""
    response = gui_client.post(
        "/login",
        data={"username": "admin", "password": "test-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return gui_client

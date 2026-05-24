# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Test fixtures for tool _impl tests.

A FakePool returns FakeClients with AsyncMock-backed API attributes.
Each test can configure the mock return values inline.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class _ClientCfgStub:
    """Mimics AnalyticsClientConfig for tests that read client.cfg."""

    def __init__(
        self,
        host: str = "fake-host",
        tls: bool = False,
        mgmt_port: int = 8091,
        analytics_port: int = 8095,
    ) -> None:
        self.host = host
        self.tls = tls
        self.mgmt_port = mgmt_port
        self.analytics_port = analytics_port


class FakeClient:
    """
    A stand-in for AnalyticsClient. Each API attribute is a MagicMock whose
    methods are AsyncMock-coroutines.
    """

    def __init__(self) -> None:
        # A stub cfg so route handlers reading client.cfg.host don't crash
        self.cfg = _ClientCfgStub()

        self.analytics = MagicMock()
        self.analytics.execute = AsyncMock()
        self.analytics.execute_readonly = AsyncMock()

        self.admin = MagicMock()
        self.admin.get_service_status = AsyncMock()
        self.admin.get_ingestion_status = AsyncMock()
        self.admin.get_active_requests = AsyncMock()
        self.admin.get_completed_requests = AsyncMock()
        self.admin.cancel_request = AsyncMock()
        self.admin.restart_service = AsyncMock()
        self.admin.restart_node = AsyncMock()

        self.config = MagicMock()
        self.config.get_service_config = AsyncMock()
        self.config.update_service_config = AsyncMock()

        self.settings = MagicMock()
        self.settings.get_settings = AsyncMock()
        self.settings.update_settings = AsyncMock()

        self.links = MagicMock()
        self.links.get_all_links = AsyncMock()
        self.links.get_link = AsyncMock()
        self.links.create_link = AsyncMock()
        self.links.update_link = AsyncMock()
        self.links.delete_link = AsyncMock()

        self.libraries = MagicMock()
        self.libraries.list_libraries = AsyncMock()
        self.libraries.delete_library = AsyncMock()

        self.security = MagicMock()
        self.security.list_users = AsyncMock()
        self.security.get_user = AsyncMock()
        self.security.upsert_user = AsyncMock()
        self.security.delete_user = AsyncMock()
        self.security.list_groups = AsyncMock()
        self.security.upsert_group = AsyncMock()
        self.security.delete_group = AsyncMock()
        self.security.list_roles = AsyncMock()
        self.security.check_permissions = AsyncMock()

        self.cluster = MagicMock()
        self.cluster.get_cluster_info = AsyncMock()
        self.cluster.get_cluster_details = AsyncMock()
        self.cluster.get_cluster_tasks = AsyncMock()
        self.cluster.get_rebalance_progress = AsyncMock()
        self.cluster.get_auto_failover_settings = AsyncMock()
        self.cluster.configure_auto_failover = AsyncMock()
        self.cluster.get_system_events = AsyncMock()
        self.cluster.who_am_i = AsyncMock()

        self.ping = AsyncMock(return_value=True)
        self.close = AsyncMock()


class FakePool:
    """Stand-in for ClientPool — returns a FakeClient by name."""

    def __init__(self, names: list[str] | None = None) -> None:
        # None → default single cluster; explicit [] → empty pool
        if names is None:
            names = ["default"]
        self._names = names
        self._clients: dict[str, FakeClient] = {n: FakeClient() for n in self._names}
        self._capella = MagicMock()
        # Pre-configure all Capella methods as AsyncMock
        for method in (
            "list_organizations",
            "list_clusters",
            "get_cluster",
            "create_cluster",
            "delete_cluster",
            "list_backups",
            "create_backup",
            "restore_backup",
            "list_api_keys",
        ):
            setattr(self._capella, method, AsyncMock())
        self._has_capella = False

    @property
    def cluster_names(self) -> list[str]:
        return list(self._names)

    @property
    def is_empty(self) -> bool:
        return not self._names

    def default_name(self) -> str:
        return self._names[0]

    def default(self) -> FakeClient:
        return self._clients[self._names[0]]

    def get(self, name: str) -> FakeClient:
        if name not in self._clients:
            raise ValueError(f"Unknown cluster '{name}'")
        return self._clients[name]

    def resolve(self, name: str | None) -> tuple[str, FakeClient]:
        if not name:
            return self.default_name(), self.default()
        return name, self.get(name)

    @property
    def has_capella(self) -> bool:
        return self._has_capella

    @property
    def capella(self) -> Any:
        if not self._has_capella:
            raise RuntimeError("Capella not configured")
        return self._capella

    def enable_capella(self) -> None:
        self._has_capella = True

    def client_for(self, name: str) -> FakeClient:
        """Test helper: get the FakeClient for a specific cluster name."""
        return self._clients[name]


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool()


@pytest.fixture
def fake_client(fake_pool: FakePool) -> FakeClient:
    return fake_pool.default()


@pytest.fixture
def fake_pool_capella() -> FakePool:
    pool = FakePool()
    pool.enable_capella()
    return pool

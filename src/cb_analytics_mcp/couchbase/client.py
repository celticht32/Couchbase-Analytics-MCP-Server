# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""High-level client that bundles all Couchbase REST API groups."""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import SecretStr

from cb_analytics_mcp.couchbase.analytics_api import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLibraryAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics_mcp.couchbase.cluster_api import ClusterAPI, SecurityAPI
from cb_analytics_mcp.couchbase.http_client import HttpClient

log = structlog.get_logger(__name__)


class AnalyticsClientConfig:
    """Config for a single AnalyticsClient. Passwords stored as SecretStr."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str | SecretStr,
        mgmt_port: int = 8091,
        analytics_port: int = 8095,
        tls: bool = False,
        verify_ssl: bool = True,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.host = host
        self.mgmt_port = mgmt_port
        self.analytics_port = analytics_port
        self.username = username
        self.password = password if isinstance(password, SecretStr) else SecretStr(password)
        self.tls = tls
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def management_url(self) -> str:
        scheme = "https" if self.tls else "http"
        return f"{scheme}://{self.host}:{self.mgmt_port}"

    @property
    def analytics_url(self) -> str:
        scheme = "https" if self.tls else "http"
        return f"{scheme}://{self.host}:{self.analytics_port}"


class AnalyticsClient:
    """
    Single facade for all Couchbase REST endpoints used by the MCP tools.

    Usage:
        client = AnalyticsClient(config)
        await client.ping()
        result = await client.analytics.execute(...)
        await client.close()
    """

    def __init__(self, config: AnalyticsClientConfig) -> None:
        self.cfg = config  # the dataclass; .cfg, not .config
        self._http = HttpClient(
            management_url=config.management_url,
            analytics_url=config.analytics_url,
            username=config.username,
            password=config.password.get_secret_value(),
            timeout=config.timeout_seconds,
            verify_ssl=config.verify_ssl,
            max_retries=config.max_retries,
        )

        self.analytics = AnalyticsServiceAPI(self._http)
        self.admin = AnalyticsAdminAPI(self._http)
        self.config = AnalyticsConfigAPI(self._http)  # service-config API
        self.settings = AnalyticsSettingsAPI(self._http)
        self.links = AnalyticsLinksAPI(self._http)
        self.libraries = AnalyticsLibraryAPI(self._http)
        self.cluster = ClusterAPI(self._http)
        self.security = SecurityAPI(self._http)

    async def ping(self) -> bool:
        """Best-effort liveness check. Returns True if the cluster responded."""
        try:
            await self._http.get_mgmt("/pools")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> AnalyticsClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

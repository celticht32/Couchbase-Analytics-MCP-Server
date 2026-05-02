# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
AnalyticsClient — unified entry point for all Couchbase Enterprise Analytics APIs.

Usage:

    import asyncio
    from cb_analytics import AnalyticsClient, AnalyticsClientConfig

    async def main():
        config = AnalyticsClientConfig(
            host="localhost",
            username="Administrator",
            password="password",
        )
        async with AnalyticsClient(config) as client:
            # Execute SQL++
            result = await client.analytics.execute(
                AnalyticsQueryRequest(statement="SELECT 1 AS n")
            )
            print(result.results)

            # Manage RBAC
            users = await client.security.list_users()

            # Check service health
            status = await client.admin.get_service_status()

    asyncio.run(main())
"""

from __future__ import annotations

from types import TracebackType

from cb_analytics.api.analytics import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics.api.cluster import ClusterAPI
from cb_analytics.api.security import SecurityAPI
from cb_analytics.api.server_groups import ServerGroupsAPI
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.http_client import HttpClient


class AnalyticsClient:
    """
    Async context-manager client for the Couchbase Enterprise Analytics REST API.

    Exposes eight API groups as attributes:

    Attribute        | Covers
    -----------------|--------------------------------------------------
    cluster          | Node/cluster lifecycle, rebalance, failover, events
    analytics        | SQL++ query execution (POST & GET /api/v1/request)
    admin            | Active/completed requests, restart, ingestion status
    config           | Service-level and node-level configuration parameters
    settings         | /settings/analytics (replica count etc.)
    links            | Analytics link CRUD (Couchbase/S3/Azure/GCS)
    security         | RBAC, LDAP, SAML, certificates, audit, TLS
    server_groups    | Server group awareness management

    All methods are async and should be called inside an `async with` block
    or after calling `await client.__aenter__()` manually.
    """

    def __init__(self, config: AnalyticsClientConfig | None = None) -> None:
        self._config = config or AnalyticsClientConfig()
        self._http = HttpClient(
            management_url=self._config.management_url,
            analytics_url=self._config.analytics_url,
            username=self._config.username,
            password=self._config.password,
            timeout=self._config.timeout_seconds,
            verify_ssl=self._config.verify_ssl,
            max_retries=self._config.max_retries,
        )

        # API group facades
        self.cluster = ClusterAPI(self._http)
        self.analytics = AnalyticsServiceAPI(self._http)
        self.admin = AnalyticsAdminAPI(self._http)
        self.config = AnalyticsConfigAPI(self._http)
        self.settings = AnalyticsSettingsAPI(self._http)
        self.links = AnalyticsLinksAPI(self._http)
        self.security = SecurityAPI(self._http)
        self.server_groups = ServerGroupsAPI(self._http)

    async def __aenter__(self) -> "AnalyticsClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def close(self) -> None:
        """Explicitly close the underlying HTTP connections."""
        await self._http.aclose()

    async def ping(self) -> bool:
        """
        Quick connectivity check — returns True if the cluster responds to /pools.
        Does not raise; returns False on any error.
        """
        try:
            await self.cluster.get_cluster_info()
            return True
        except Exception:
            return False

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
AnalyticsClient — unified async context-manager for all Enterprise Analytics APIs.

Usage::

    import asyncio
    from cb_analytics import AnalyticsClient, AnalyticsClientConfig

    async def main():
        config = AnalyticsClientConfig(host="localhost", password="pass")
        async with AnalyticsClient(config) as client:
            result = await client.analytics.execute(
                AnalyticsQueryRequest(statement="SELECT 1 AS n")
            )
            print(result.results)

    asyncio.run(main())
"""

from __future__ import annotations

from types import TracebackType

from cb_analytics.api.analytics import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLibraryAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics.api.cluster import ClusterAPI
from cb_analytics.api.security import SecurityAPI
from cb_analytics.api.server_groups import ServerGroupsAPI
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.http_client import HttpClient
from cb_analytics.logging_setup import configure_logging
from cb_analytics.observability.metrics import MetricsRegistry


class AnalyticsClient:
    """
    Async context-manager client for Couchbase Enterprise Analytics.

    Attribute        | Covers
    -----------------|-------------------------------------------------
    cluster          | Cluster lifecycle, rebalance, failover, events
    analytics        | SQL++ query execution
    admin            | Active/completed requests, restart, ingestion
    config           | Service-level and node-level configuration
    settings         | /settings/analytics (replica count etc.)
    links            | Analytics link CRUD (Couchbase/S3/Azure/GCS)
    libraries        | UDF library management
    security         | RBAC, LDAP, SAML, certificates, audit
    server_groups    | Server Group Awareness
    metrics          | Prometheus MetricsRegistry (if enabled)
    """

    def __init__(
        self,
        config: AnalyticsClientConfig | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._config = config or AnalyticsClientConfig()

        configure_logging(
            debug=self._config.debug,
            json_output=not self._config.debug,
        )

        self.metrics = metrics or MetricsRegistry()

        self._http = HttpClient(
            management_url=self._config.management_url,
            analytics_url=self._config.analytics_url,
            username=self._config.username,
            password=self._config.password.get_secret_value(),  # unwrap SecretStr here only
            timeout=self._config.timeout_seconds,
            verify_ssl=self._config.verify_ssl,
            max_retries=self._config.max_retries,
            debug=self._config.debug,
            circuit_fail_max=self._config.circuit_fail_max,
            circuit_reset_timeout=self._config.circuit_reset_timeout,
            metrics=self.metrics,
        )

        self.cluster = ClusterAPI(self._http)
        self.analytics = AnalyticsServiceAPI(self._http)
        self.admin = AnalyticsAdminAPI(self._http)
        self.config = AnalyticsConfigAPI(self._http)
        self.settings = AnalyticsSettingsAPI(self._http)
        self.links = AnalyticsLinksAPI(self._http)
        self.libraries = AnalyticsLibraryAPI(self._http)
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
        """Explicitly close underlying HTTP connections."""
        await self._http.aclose()

    async def ping(self) -> bool:
        """Return True if the cluster responds to GET /pools."""
        try:
            await self.cluster.get_cluster_info()
            return True
        except Exception:
            return False

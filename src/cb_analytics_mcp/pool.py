# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Connection pool — one AnalyticsClient per registered cluster, plus an optional
CapellaClient for the Capella Management API.

The pool is created in the lifespan of the application (FastMCP and/or the
GUI). There is no module-level singleton, which makes it fully testable.
"""

from __future__ import annotations

import structlog

from cb_analytics_mcp.config import AppConfig, ClusterConfig
from cb_analytics_mcp.couchbase import (
    AnalyticsClient,
    AnalyticsClientConfig,
    CapellaClient,
)

log = structlog.get_logger(__name__)


class ClientPool:
    """
    Holds one AnalyticsClient per cluster plus an optional CapellaClient.

    Lifecycle: ClientPool() → await startup(cfg) → use → await shutdown()
    """

    def __init__(self) -> None:
        self._clients: dict[str, AnalyticsClient] = {}
        self._names: list[str] = []
        self._capella: CapellaClient | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def startup(self, cfg: AppConfig) -> None:
        """Build a client for every cluster; start the Capella client if configured."""
        for cluster in cfg.clusters:
            client = self._make_client(cluster)
            ok = await client.ping()
            if ok:
                log.info("cluster_connected", name=cluster.name, host=cluster.host)
            else:
                log.warning(
                    "cluster_unreachable",
                    name=cluster.name,
                    host=cluster.host,
                    msg="MCP will start anyway — cluster may come online later",
                )
            self._clients[cluster.name] = client
            self._names.append(cluster.name)

        if cfg.capella_api_key is not None:
            self._capella = CapellaClient(
                api_key_secret=cfg.capella_api_key.get_secret_value(),
                base_url=cfg.capella_base_url,
            )
            log.info("capella_client_initialised")
        else:
            log.info(
                "capella_client_not_configured",
                hint="Set CB_CAPELLA_API_KEY_SECRET to enable capella_* tools",
            )

    async def shutdown(self) -> None:
        """Close every connection cleanly. Safe to call multiple times."""
        for name, client in self._clients.items():
            try:
                await client.close()
                log.debug("cluster_disconnected", name=name)
            except Exception as e:
                log.warning("cluster_close_failed", name=name, error=str(e))
        self._clients.clear()
        self._names.clear()

        if self._capella is not None:
            try:
                await self._capella.close()
                log.debug("capella_client_closed")
            except Exception as e:
                log.warning("capella_close_failed", error=str(e))
            self._capella = None

    # ── Cluster access ─────────────────────────────────────────────────────────

    def get(self, cluster_name: str) -> AnalyticsClient:
        if cluster_name not in self._clients:
            available = ", ".join(self._names) or "(none configured)"
            raise ValueError(f"Unknown cluster '{cluster_name}'. Available: {available}")
        return self._clients[cluster_name]

    def default(self) -> AnalyticsClient:
        if not self._clients:
            raise RuntimeError("No clusters configured in ClientPool")
        return self._clients[self._names[0]]

    def default_name(self) -> str:
        if not self._names:
            raise RuntimeError("No clusters configured in ClientPool")
        return self._names[0]

    def resolve(self, cluster_name: str | None) -> tuple[str, AnalyticsClient]:
        """
        Resolve an optional cluster name to (name, client).
        Empty string or None → default cluster.
        """
        if not cluster_name:
            return self.default_name(), self.default()
        return cluster_name, self.get(cluster_name)

    @property
    def cluster_names(self) -> list[str]:
        return list(self._names)

    @property
    def is_empty(self) -> bool:
        return not self._clients

    # ── Capella access ─────────────────────────────────────────────────────────

    @property
    def capella(self) -> CapellaClient:
        """Get the Capella client; raises RuntimeError if not configured."""
        if self._capella is None:
            raise RuntimeError("Capella client is not configured. Set CB_CAPELLA_API_KEY_SECRET and restart.")
        return self._capella

    @property
    def has_capella(self) -> bool:
        return self._capella is not None

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_client(cluster: ClusterConfig) -> AnalyticsClient:
        return AnalyticsClient(
            AnalyticsClientConfig(
                host=cluster.host,
                username=cluster.username,
                password=cluster.password,
                mgmt_port=cluster.mgmt_port,
                analytics_port=cluster.analytics_port,
                tls=cluster.tls,
                verify_ssl=cluster.verify_ssl,
                timeout_seconds=cluster.timeout_seconds,
                max_retries=cluster.max_retries,
            )
        )

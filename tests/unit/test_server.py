# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Tests for build_server() — the factory that wires everything together.

We don't run the FastMCP server; we just confirm the build succeeds, the
right pieces are attached, and every tool group gets registered.
"""

from __future__ import annotations

from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, GuiConfig, ObservabilityConfig
from cb_analytics_mcp.server import build_server


def _cfg() -> AppConfig:
    return AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[],
        gui=GuiConfig(session_secret=SecretStr("s" * 48), password=SecretStr("p")),
        observability=ObservabilityConfig(
            metrics_enabled=False,
            audit_log_enabled=False,
            otel_enabled=False,
            log_level="WARNING",
        ),
    )


class TestBuildServer:
    def test_returns_quad(self) -> None:
        result = build_server(_cfg())
        assert len(result) == 4

    def test_components_are_correct_types(self) -> None:
        from cb_analytics_mcp.observability.audit import AuditLog
        from cb_analytics_mcp.observability.metrics import Metrics
        from cb_analytics_mcp.pool import ClientPool

        mcp, pool, metrics, audit = build_server(_cfg())
        assert isinstance(pool, ClientPool)
        assert isinstance(metrics, Metrics)
        assert isinstance(audit, AuditLog)
        # FastMCP is generic; just check the attribute set
        assert hasattr(mcp, "name")
        assert mcp.name == "cb-analytics-mcp"

    def test_audit_disabled_when_configured_off(self) -> None:
        _, _, _, audit = build_server(_cfg())
        assert audit.enabled is False

    def test_pool_starts_empty(self) -> None:
        _, pool, _, _ = build_server(_cfg())
        assert pool.is_empty

    def test_all_tool_groups_registered(self) -> None:
        """Every tool from every group should be reachable via the MCP tool registry."""
        import asyncio

        mcp, _, _, _ = build_server(_cfg())
        tool_list = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tool_list}

        # A representative tool from each group
        expected = {
            "list_clusters",  # meta
            "list_dataverses",  # schema
            "execute_query",  # query
            "get_service_status",  # admin
            "get_service_config",  # config_tools
            "list_links",  # links
            "list_libraries",  # libraries
            "list_users",  # security
            "ping_cluster",  # cluster
            "capella_list_organizations",  # capella
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"

    def test_total_tool_count(self) -> None:
        """Exactly 55 MCP tools should be registered."""
        import asyncio

        mcp, _, _, _ = build_server(_cfg())
        tools = asyncio.run(mcp.list_tools())
        # 2 meta + 3 schema + 5 query (execute, readonly, paginated, fetch_next, explain)
        # + 7 admin + 4 config + 5 links + 2 libraries + 9 security
        # + 9 cluster + 9 capella = 55
        assert len(tools) == 55

    def test_metrics_enabled_starts_server(self, monkeypatch) -> None:
        """When metrics_enabled=True, start_metrics_server is invoked."""
        calls: list[int] = []

        def fake_start(port: int, _registry) -> None:
            calls.append(port)

        monkeypatch.setattr("cb_analytics_mcp.server.start_metrics_server", fake_start)

        cfg = _cfg()
        cfg.observability.metrics_enabled = True
        cfg.observability.metrics_port = 19999
        build_server(cfg)
        assert calls == [19999]

    def test_otel_enabled_calls_configure_tracing(self, monkeypatch) -> None:
        called: dict[str, object] = {}

        def fake_configure(**kwargs: object) -> None:
            called.update(kwargs)

        monkeypatch.setattr("cb_analytics_mcp.server.configure_tracing", fake_configure)

        cfg = _cfg()
        cfg.observability.otel_enabled = True
        cfg.observability.otel_endpoint = "http://otel.example:4318"
        build_server(cfg)

        assert called["enabled"] is True
        assert called["endpoint"] == "http://otel.example:4318"


class TestLifespan:
    """The @asynccontextmanager lifespan inside build_server should startup
    and shutdown the pool cleanly."""

    def test_lifespan_runs_startup_and_shutdown(self) -> None:
        import asyncio
        from unittest.mock import AsyncMock

        mcp, pool, _metrics, _ = build_server(_cfg())

        # Patch pool startup/shutdown so we don't hit real Couchbase
        pool.startup = AsyncMock()  # type: ignore[method-assign]
        pool.shutdown = AsyncMock()  # type: ignore[method-assign]

        async def run() -> None:
            assert mcp.settings.lifespan is not None
            async with mcp.settings.lifespan(mcp):
                pass

        asyncio.run(run())
        pool.startup.assert_awaited_once()
        pool.shutdown.assert_awaited_once()

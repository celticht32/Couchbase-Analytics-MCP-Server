# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the ClientPool."""

from __future__ import annotations

import pytest
import respx
from pydantic import SecretStr

from cb_analytics_mcp.config import AppConfig, ClusterConfig
from cb_analytics_mcp.pool import ClientPool


def _make_cluster(name: str, host: str = "h", port: int = 8091) -> ClusterConfig:
    return ClusterConfig(
        name=name,
        host=host,
        username="u",
        password=SecretStr("p"),
        mgmt_port=port,
    )


@respx.mock
@pytest.mark.asyncio
async def test_startup_with_single_cluster() -> None:
    respx.get("http://h:8091/pools").mock(return_value=respx.MockResponse(200, json={"ok": True}))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[_make_cluster("c1")],
    )
    pool = ClientPool()
    await pool.startup(cfg)

    assert pool.cluster_names == ["c1"]
    assert pool.default_name() == "c1"
    assert not pool.is_empty
    assert not pool.has_capella

    await pool.shutdown()
    assert pool.is_empty


@respx.mock
@pytest.mark.asyncio
async def test_startup_with_multiple_clusters_preserves_order() -> None:
    respx.get("http://h:8091/pools").mock(return_value=respx.MockResponse(200, json={"ok": True}))
    respx.get("http://h:8092/pools").mock(return_value=respx.MockResponse(200, json={"ok": True}))
    respx.get("http://h:8093/pools").mock(return_value=respx.MockResponse(200, json={"ok": True}))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[
            _make_cluster("prod", port=8091),
            _make_cluster("stage", port=8092),
            _make_cluster("dev", port=8093),
        ],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        assert pool.cluster_names == ["prod", "stage", "dev"]
        assert pool.default_name() == "prod"
    finally:
        await pool.shutdown()


@respx.mock
@pytest.mark.asyncio
async def test_startup_continues_when_cluster_unreachable() -> None:
    """A failing ping is logged but doesn't prevent startup."""
    import httpx

    respx.get("http://h:8091/pools").mock(side_effect=httpx.ConnectError("refused"))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[_make_cluster("c1")],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        assert pool.cluster_names == ["c1"]  # client created regardless
    finally:
        await pool.shutdown()


@respx.mock
@pytest.mark.asyncio
async def test_get_by_name_returns_correct_client() -> None:
    respx.get("http://h:8091/pools").mock(return_value=respx.MockResponse(200, json={}))
    respx.get("http://h:8092/pools").mock(return_value=respx.MockResponse(200, json={}))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[_make_cluster("c1", port=8091), _make_cluster("c2", port=8092)],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        c1 = pool.get("c1")
        c2 = pool.get("c2")
        assert c1.cfg.mgmt_port == 8091
        assert c2.cfg.mgmt_port == 8092
        assert c1 is not c2
    finally:
        await pool.shutdown()


@respx.mock
@pytest.mark.asyncio
async def test_get_unknown_cluster_raises() -> None:
    respx.get("http://h:8091/pools").mock(return_value=respx.MockResponse(200, json={}))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[_make_cluster("c1")],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        with pytest.raises(ValueError, match="Unknown cluster"):
            pool.get("does-not-exist")
    finally:
        await pool.shutdown()


@respx.mock
@pytest.mark.asyncio
async def test_resolve_default() -> None:
    respx.get("http://h:8091/pools").mock(return_value=respx.MockResponse(200, json={}))

    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        clusters=[_make_cluster("c1")],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        name, _ = pool.resolve(None)
        assert name == "c1"
        name, _ = pool.resolve("")
        assert name == "c1"
        name, _ = pool.resolve("c1")
        assert name == "c1"
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_default_on_empty_pool_raises() -> None:
    pool = ClientPool()
    with pytest.raises(RuntimeError, match="No clusters"):
        pool.default()
    with pytest.raises(RuntimeError, match="No clusters"):
        pool.default_name()


@pytest.mark.asyncio
async def test_capella_not_configured_raises() -> None:
    pool = ClientPool()
    with pytest.raises(RuntimeError, match="Capella"):
        _ = pool.capella


@respx.mock
@pytest.mark.asyncio
async def test_capella_initialised_when_key_present() -> None:
    cfg = AppConfig(
        mcp_api_key=SecretStr("z" * 48),
        capella_api_key=SecretStr("cap-key"),
        clusters=[],
    )
    pool = ClientPool()
    await pool.startup(cfg)
    try:
        assert pool.has_capella
        assert pool.capella is not None
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_shutdown_is_idempotent() -> None:
    pool = ClientPool()
    cfg = AppConfig(mcp_api_key=SecretStr("z" * 48), clusters=[])
    await pool.startup(cfg)
    await pool.shutdown()
    await pool.shutdown()  # should not raise

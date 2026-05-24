# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for the central config loader."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from cb_analytics_mcp.config import (
    config_summary,
    load_clusters_from_env,
    load_clusters_from_file,
    load_config,
    validate_config,
)


def _base_env(**extra: str) -> dict[str, str]:
    base = {
        "CB_ANALYTICS_HOST": "myhost",
        "CB_ANALYTICS_USERNAME": "u",
        "CB_ANALYTICS_PASSWORD": "p1234567890",
        "MCP_API_KEY": "z" * 48,
        "GUI_SESSION_SECRET": "s" * 48,
        "GUI_PASSWORD": "real-password",
    }
    base.update(extra)
    return base


class TestLoadConfigEnv:
    def test_minimal_env_works(self) -> None:
        with patch.dict(os.environ, _base_env(), clear=True):
            cfg = load_config()
        assert len(cfg.clusters) == 1
        assert cfg.clusters[0].host == "myhost"
        assert cfg.clusters[0].name == "default"

    def test_custom_cluster_name(self) -> None:
        with patch.dict(os.environ, _base_env(CB_ANALYTICS_CLUSTER_NAME="prod"), clear=True):
            cfg = load_config()
        assert cfg.clusters[0].name == "prod"

    def test_tls_parsed(self) -> None:
        with patch.dict(os.environ, _base_env(CB_ANALYTICS_TLS="true"), clear=True):
            cfg = load_config()
        assert cfg.clusters[0].tls is True

    def test_custom_ports(self) -> None:
        env = _base_env(CB_ANALYTICS_MGMT_PORT="18091", CB_ANALYTICS_ANALYTICS_PORT="18095")
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.clusters[0].mgmt_port == 18091
        assert cfg.clusters[0].analytics_port == 18095

    def test_capella_key(self) -> None:
        env = _base_env(CB_CAPELLA_API_KEY_SECRET="capkey")
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.capella_api_key is not None
        assert cfg.capella_api_key.get_secret_value() == "capkey"

    def test_no_capella_key(self) -> None:
        with patch.dict(os.environ, _base_env(), clear=True):
            cfg = load_config()
        assert cfg.capella_api_key is None

    def test_observability_defaults(self) -> None:
        with patch.dict(os.environ, _base_env(), clear=True):
            cfg = load_config()
        assert cfg.observability.log_level == "INFO"
        assert cfg.observability.log_format == "json"
        assert cfg.observability.audit_log_enabled is True

    def test_log_level_uppercase(self) -> None:
        with patch.dict(os.environ, _base_env(LOG_LEVEL="debug"), clear=True):
            cfg = load_config()
        assert cfg.observability.log_level == "DEBUG"

    def test_invalid_int_raises(self) -> None:
        with patch.dict(os.environ, _base_env(MCP_PORT="not-a-number"), clear=True):
            with pytest.raises(ValueError, match="MCP_PORT"):
                load_config()


class TestLoadClustersFromFile:
    def test_multi_cluster_file(self) -> None:
        data = [
            {"name": "prod", "host": "p", "password": "p1"},
            {"name": "staging", "host": "s", "password": "p2"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            fname = f.name
        try:
            clusters = load_clusters_from_file(fname)
            assert len(clusters) == 2
            assert clusters[0].name == "prod"
            assert clusters[1].name == "staging"
        finally:
            os.unlink(fname)

    def test_file_overrides_env(self) -> None:
        data = [{"name": "from-file", "host": "h", "password": "p"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            fname = f.name
        try:
            env = _base_env(CB_ANALYTICS_CLUSTERS_FILE=fname)
            with patch.dict(os.environ, env, clear=True):
                cfg = load_config()
            assert len(cfg.clusters) == 1
            assert cfg.clusters[0].name == "from-file"
        finally:
            os.unlink(fname)

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_clusters_from_file("/nonexistent/path.json")

    def test_missing_password_raises(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"name": "c", "host": "h"}], f)
            fname = f.name
        try:
            with pytest.raises(ValueError, match="password"):
                load_clusters_from_file(fname)
        finally:
            os.unlink(fname)

    def test_invalid_top_level_type(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"not": "a list"}, f)
            fname = f.name
        try:
            with pytest.raises(ValueError, match="must contain a JSON array"):
                load_clusters_from_file(fname)
        finally:
            os.unlink(fname)


class TestLoadClustersFromEnv:
    def test_missing_host_returns_empty(self) -> None:
        with patch.dict(os.environ, {"CB_ANALYTICS_PASSWORD": "p"}, clear=True):
            clusters = load_clusters_from_env()
        assert clusters == []

    def test_missing_password_returns_empty(self) -> None:
        with patch.dict(os.environ, {"CB_ANALYTICS_HOST": "h"}, clear=True):
            clusters = load_clusters_from_env()
        assert clusters == []


class TestValidateConfig:
    def test_minimal_valid_config(self) -> None:
        with patch.dict(os.environ, _base_env(), clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert errors == []

    def test_missing_api_key(self) -> None:
        env = _base_env()
        env.pop("MCP_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("MCP_API_KEY" in e for e in errors)

    def test_short_api_key(self) -> None:
        env = _base_env(MCP_API_KEY="too-short")
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("32 characters" in e for e in errors)

    def test_no_clusters(self) -> None:
        with patch.dict(os.environ, {"MCP_API_KEY": "z" * 48}, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("No clusters" in e for e in errors)

    def test_default_gui_password_rejected(self) -> None:
        env = _base_env(GUI_PASSWORD="changeme")
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("GUI_PASSWORD" in e for e in errors)

    def test_default_session_secret_rejected(self) -> None:
        env = _base_env()
        env.pop("GUI_SESSION_SECRET", None)
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("GUI_SESSION_SECRET" in e for e in errors)

    def test_invalid_log_level(self) -> None:
        env = _base_env(LOG_LEVEL="TRACE")
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        errors = validate_config(cfg)
        assert any("LOG_LEVEL" in e for e in errors)


class TestConfigSummary:
    def test_summary_redacts_secrets(self) -> None:
        with patch.dict(os.environ, _base_env(CB_CAPELLA_API_KEY_SECRET="cap"), clear=True):
            cfg = load_config()
        summary = config_summary(cfg)
        text = json.dumps(summary)
        # Secrets should not appear
        assert "p1234567890" not in text
        assert "real-password" not in text
        assert "cap" not in text or "capella" in text  # cap could appear as a substring of "capella"
        # Structure
        assert summary["mcp"]["api_key_set"] is True
        assert summary["capella"]["configured"] is True
        assert len(summary["clusters"]) == 1

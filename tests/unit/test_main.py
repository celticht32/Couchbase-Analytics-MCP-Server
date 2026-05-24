# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the process entrypoint."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from cb_analytics_mcp.__main__ import main, parse_args


class TestParseArgs:
    def test_no_args_defaults(self) -> None:
        args = parse_args([])
        assert args.gui_only is False
        assert args.check is False

    def test_gui_only_flag(self) -> None:
        args = parse_args(["--gui-only"])
        assert args.gui_only is True

    def test_check_flag(self) -> None:
        args = parse_args(["--check"])
        assert args.check is True

    def test_version(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            parse_args(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "cb-analytics-mcp" in out
        assert "1.0.0" in out


def _full_env() -> dict[str, str]:
    return {
        "CB_ANALYTICS_HOST": "h",
        "CB_ANALYTICS_USERNAME": "u",
        "CB_ANALYTICS_PASSWORD": "pwd1234567890",
        "MCP_API_KEY": "z" * 48,
        "GUI_SESSION_SECRET": "s" * 48,
        "GUI_PASSWORD": "real-password",
    }


class TestCheck:
    def test_check_with_valid_env_returns_0(self) -> None:
        with patch.dict(os.environ, _full_env(), clear=True):
            assert main(["--check"]) == 0

    def test_check_missing_api_key_returns_2(self, capsys) -> None:
        env = _full_env()
        env.pop("MCP_API_KEY")
        with patch.dict(os.environ, env, clear=True):
            assert main(["--check"]) == 2
        err = capsys.readouterr().err
        assert "MCP_API_KEY" in err

    def test_check_missing_cluster_returns_2(self, capsys) -> None:
        env = _full_env()
        env.pop("CB_ANALYTICS_HOST")
        with patch.dict(os.environ, env, clear=True):
            assert main(["--check"]) == 2
        err = capsys.readouterr().err
        assert "clusters" in err.lower()

    def test_check_short_api_key_returns_2(self, capsys) -> None:
        env = _full_env()
        env["MCP_API_KEY"] = "short"
        with patch.dict(os.environ, env, clear=True):
            assert main(["--check"]) == 2
        err = capsys.readouterr().err
        assert "32" in err

    def test_invalid_int_returns_2(self, capsys) -> None:
        env = _full_env()
        env["MCP_PORT"] = "not-a-number"
        with patch.dict(os.environ, env, clear=True):
            assert main(["--check"]) == 2
        err = capsys.readouterr().err
        assert "MCP_PORT" in err or "integer" in err.lower()


class TestGuiOnlyValidation:
    """In --gui-only mode, MCP_API_KEY is not required."""

    def test_gui_only_check_without_api_key(self) -> None:
        env = _full_env()
        env.pop("MCP_API_KEY")
        with patch.dict(os.environ, env, clear=True):
            # --gui-only + --check together — should succeed since key is not strict
            assert main(["--gui-only", "--check"]) == 0

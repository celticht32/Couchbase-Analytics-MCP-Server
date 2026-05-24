# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for the cb-analytics-mcp CLI tool subcommand."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from cb_analytics_mcp.cli import (
    _build_impl_map,
    _parse_kv_args,
    _resolve_impl,
    run_tools_command,
)


class TestParseKvArgs:
    def test_string_value(self) -> None:
        assert _parse_kv_args(["name=prod"]) == {"name": "prod"}

    def test_int_value_parsed_as_int(self) -> None:
        # JSON-parses to int
        assert _parse_kv_args(["page_size=100"]) == {"page_size": 100}

    def test_bool_value_parsed(self) -> None:
        assert _parse_kv_args(["readonly=true"]) == {"readonly": True}
        assert _parse_kv_args(["enabled=false"]) == {"enabled": False}

    def test_json_object(self) -> None:
        out = _parse_kv_args(['named_args={"id": 5}'])
        assert out == {"named_args": {"id": 5}}

    def test_quoted_string_with_spaces(self) -> None:
        # Argparse will already strip shell quotes; we just get the string
        out = _parse_kv_args(["statement=SELECT * FROM x"])
        assert out == {"statement": "SELECT * FROM x"}

    def test_multiple_args(self) -> None:
        out = _parse_kv_args(["a=1", "b=hello", "c=true"])
        assert out == {"a": 1, "b": "hello", "c": True}

    def test_no_equals_raises(self) -> None:
        with pytest.raises(ValueError, match="KEY=VALUE"):
            _parse_kv_args(["just-a-key"])

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="empty key"):
            _parse_kv_args(["=value"])

    def test_empty_value_is_empty_string(self) -> None:
        # Not JSON-parseable → falls through to string
        assert _parse_kv_args(["key="]) == {"key": ""}


class TestImplMap:
    def test_all_tools_mapped(self) -> None:
        m = _build_impl_map()
        # Should cover all 55 known tools
        assert len(m) == 55

    def test_known_tools_resolved(self) -> None:
        # Tools whose _impl exists should resolve to a callable
        fn = _resolve_impl("list_clusters")
        assert callable(fn)

    def test_unknown_tool_returns_none(self) -> None:
        assert _resolve_impl("totally_made_up_tool") is None


class TestToolsListCommand:
    def test_list_all(self, capsys) -> None:
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="list",
            category=None,
        )
        rc = run_tools_command(args)
        out = capsys.readouterr().out
        assert rc == 0
        # Should print 55 lines (one per tool)
        assert out.count("\n") == 55

    def test_list_filtered_by_category(self, capsys) -> None:
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="list",
            category="write",
        )
        rc = run_tools_command(args)
        out = capsys.readouterr().out
        assert rc == 0
        # Every line must be tagged [write]
        for line in out.strip().split("\n"):
            assert "[write]" in line

    def test_no_subcommand_returns_2(self, capsys) -> None:
        import argparse

        args = argparse.Namespace(command="tools", tools_command=None)
        rc = run_tools_command(args)
        err = capsys.readouterr().err
        assert rc == 2
        assert "subcommand required" in err


class TestToolsCallOffline:
    """Smoke-test the offline-call path with mocked config."""

    def test_call_unknown_tool_returns_2(self, capsys, monkeypatch) -> None:
        # Bypass real config so the test doesn't hit the env
        monkeypatch.setenv("MCP_API_KEY", "z" * 48)
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="call",
            name="nonexistent_tool",
            arg=[],
            offline=True,
            remote=None,
        )
        rc = run_tools_command(args)
        err = capsys.readouterr().err
        assert rc == 2
        assert "unknown tool" in err

    def test_call_list_clusters_offline(self, capsys, monkeypatch) -> None:
        """End-to-end: offline call to list_clusters with no clusters configured."""
        monkeypatch.setenv("MCP_API_KEY", "z" * 48)
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="call",
            name="list_clusters",
            arg=[],
            offline=True,
            remote=None,
        )
        rc = run_tools_command(args)
        out = capsys.readouterr().out
        assert rc == 0
        # Output should be valid JSON with ok=True
        result = json.loads(out)
        assert result["ok"] is True
        assert result["data"]["count"] == 0

    def test_bad_arg_format_returns_2(self, capsys, monkeypatch) -> None:
        monkeypatch.setenv("MCP_API_KEY", "z" * 48)
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="call",
            name="list_clusters",
            arg=["malformed_no_equals"],
            offline=True,
            remote=None,
        )
        rc = run_tools_command(args)
        err = capsys.readouterr().err
        assert rc == 2
        assert "KEY=VALUE" in err


class TestToolsCallRemote:
    """Remote mode tests with httpx mocked."""

    def test_remote_requires_api_key(self, capsys, monkeypatch) -> None:
        monkeypatch.delenv("MCP_API_KEY", raising=False)
        import argparse

        args = argparse.Namespace(
            command="tools",
            tools_command="call",
            name="list_clusters",
            arg=[],
            offline=False,
            remote="http://localhost:8000/mcp",
        )
        rc = run_tools_command(args)
        err = capsys.readouterr().err
        assert rc == 2
        assert "MCP_API_KEY" in err

    def test_remote_success(self, capsys, monkeypatch) -> None:
        monkeypatch.setenv("MCP_API_KEY", "z" * 48)
        import argparse

        # Mock the httpx call
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = lambda: {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"ok": True, "data": {"clusters": []}},
            }
            mock_response.raise_for_status = lambda: None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_class.return_value.__aenter__.return_value = mock_client

            args = argparse.Namespace(
                command="tools",
                tools_command="call",
                name="list_clusters",
                arg=[],
                offline=False,
                remote="http://localhost:8000/mcp",
            )
            rc = run_tools_command(args)
            out = capsys.readouterr().out
            assert rc == 0
            assert "ok" in out

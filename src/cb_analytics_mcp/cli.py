# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Command-line interface for invoking MCP tools directly, without going
through Claude.

Two modes:

- **offline**: instantiate the client pool in-process and call the tool's
  `_impl` function directly. No running server required. Reads the same
  env config the server would use.
- **remote**: send the call via HTTP to a running cb-analytics-mcp server.
  Uses the same JSON-over-HTTP shape that MCP clients use, with the
  `MCP_API_KEY` env var as the bearer token.

Both modes pretty-print the resulting JSON dict to stdout. Exits non-zero
on a tool-level error so the CLI plays nicely with shell pipelines.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from cb_analytics_mcp.rate_limit import TOOL_CATEGORY

# ── Argument parsing helpers ──────────────────────────────────────────────


def _parse_kv_args(raw_args: list[str]) -> dict[str, Any]:
    """
    Parse repeated --arg KEY=VALUE pairs into a dict.

    VALUE is JSON-decoded when possible; otherwise treated as a literal string.
    This lets the user write:
      --arg cluster=prod              → {"cluster": "prod"}
      --arg page_size=100             → {"page_size": 100}
      --arg named_args='{"id": 5}'    → {"named_args": {"id": 5}}
      --arg readonly=true             → {"readonly": True}
    """
    out: dict[str, Any] = {}
    for raw in raw_args:
        if "=" not in raw:
            raise ValueError(f"--arg expects KEY=VALUE, got: {raw!r}")
        key, _, value = raw.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"--arg has empty key in: {raw!r}")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def _print(obj: Any) -> None:
    """Pretty-print a result dict to stdout."""
    print(json.dumps(obj, indent=2, default=str))


def _exit_code_for_result(result: dict[str, Any]) -> int:
    """Tool-level success → 0, error → 1."""
    if isinstance(result, dict) and result.get("ok") is False:
        return 1
    return 0


# ── Top-level dispatch ─────────────────────────────────────────────────────


def run_tools_command(args: argparse.Namespace) -> int:
    """Entry point for `cb-analytics-mcp tools …`. Returns a process exit code."""
    if not args.tools_command:
        print("error: subcommand required ('list' or 'call')", file=sys.stderr)
        return 2
    if args.tools_command == "list":
        return _cmd_list(args)
    if args.tools_command == "call":
        return _cmd_call(args)
    print(f"error: unknown tools subcommand: {args.tools_command}", file=sys.stderr)
    return 2


def _cmd_list(args: argparse.Namespace) -> int:
    """`tools list` — print all tools (optionally filtered by category)."""
    rows: list[tuple[str, str]] = []
    for tool_name, tool_cat in sorted(TOOL_CATEGORY.items()):
        if args.category and tool_cat != args.category:
            continue
        rows.append((tool_name, tool_cat))
    if not rows:
        print("(no tools matched)", file=sys.stderr)
        return 1
    width = max(len(n) for n, _ in rows)
    for n, c in rows:
        print(f"{n:<{width}}  [{c}]")
    return 0


def _cmd_call(args: argparse.Namespace) -> int:
    """`tools call NAME --arg KEY=VALUE …` — invoke a single tool."""
    try:
        kwargs = _parse_kv_args(args.arg)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.remote:
        return asyncio.run(_call_remote(args.remote, args.name, kwargs))
    return asyncio.run(_call_offline(args.name, kwargs))


# ── Offline mode ──────────────────────────────────────────────────────────


async def _call_offline(tool_name: str, kwargs: dict[str, Any]) -> int:
    """
    Call the tool's `_impl()` function in-process.

    Builds a real ClientPool from env config so the tool actually hits
    a Couchbase cluster (if one is configured). For tools that don't need
    a cluster (e.g. list_clusters), this still works because the pool just
    has zero clusters.
    """
    from cb_analytics_mcp.cache import ResultCache
    from cb_analytics_mcp.config import load_config
    from cb_analytics_mcp.observability.logging import configure_logging
    from cb_analytics_mcp.pool import ClientPool

    try:
        cfg = load_config()
    except (ValueError, FileNotFoundError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    # Suppress noisy startup logging — the CLI output should be just the JSON
    configure_logging(level="WARNING", fmt=cfg.observability.log_format)

    pool = ClientPool()
    await pool.startup(cfg)
    cache = ResultCache()

    impl_fn = _resolve_impl(tool_name)
    if impl_fn is None:
        print(f"error: unknown tool: {tool_name}", file=sys.stderr)
        await pool.shutdown()
        return 2

    try:
        # Tools that take a cache parameter get one; others ignore it.
        # We pass cache as a kwarg only when the signature accepts it.
        import inspect

        sig = inspect.signature(impl_fn)
        call_kwargs = dict(kwargs)
        if "cache" in sig.parameters and "cache" not in call_kwargs:
            call_kwargs["cache"] = cache

        result = await impl_fn(pool, **call_kwargs)
    except Exception as e:
        # Format errors the same way the MCP wrapper would
        from cb_analytics_mcp.tools.shared import fmt_error

        result = fmt_error(e)
    finally:
        await pool.shutdown()

    _print(result)
    return _exit_code_for_result(result)


# Map tool name → its `_impl` function. We use a lazy lookup so importing
# cli.py doesn't transitively import every tool module at startup.
_IMPL_MAP: dict[str, str] = {}


def _build_impl_map() -> dict[str, str]:
    """Map tool_name → 'module:function_name' for every _impl in tools/."""
    if _IMPL_MAP:
        return _IMPL_MAP
    # Tool→module mapping. Mirrors register() calls in server.py.
    groups: dict[str, list[str]] = {
        "meta": ["list_clusters", "get_capabilities"],
        "schema": ["list_dataverses", "list_datasets", "infer_schema"],
        "query": [
            "execute_query",
            "execute_query_readonly",
            "execute_query_paginated",
            "fetch_next_page",
            "explain_query",
        ],
        "admin": [
            "get_service_status",
            "get_ingestion_status",
            "get_active_requests",
            "get_completed_requests",
            "cancel_request",
            "restart_service",
            "restart_node",
        ],
        "config_tools": [
            "get_service_config",
            "update_service_config",
            "get_analytics_settings",
            "update_analytics_settings",
        ],
        "links": ["list_links", "get_link", "create_link", "update_link", "delete_link"],
        "libraries": ["list_libraries", "delete_library"],
        "security": [
            "list_users",
            "get_user",
            "upsert_user",
            "delete_user",
            "list_groups",
            "upsert_group",
            "delete_group",
            "list_roles",
            "check_permissions",
        ],
        "cluster": [
            "ping_cluster",
            "get_cluster_info",
            "get_cluster_details",
            "get_cluster_tasks",
            "get_rebalance_progress",
            "get_auto_failover_settings",
            "configure_auto_failover",
            "get_system_events",
            "who_am_i",
        ],
        "capella": [
            "capella_list_organizations",
            "capella_list_clusters",
            "capella_get_cluster",
            "capella_create_cluster",
            "capella_delete_cluster",
            "capella_list_backups",
            "capella_create_backup",
            "capella_restore_backup",
            "capella_list_api_keys",
        ],
    }
    for module, tools in groups.items():
        for tool in tools:
            _IMPL_MAP[tool] = f"cb_analytics_mcp.tools.{module}:{tool}_impl"
    return _IMPL_MAP


def _resolve_impl(tool_name: str) -> Any | None:
    """Resolve a tool name to its `_impl` function, lazily importing the module."""
    mapping = _build_impl_map()
    if tool_name not in mapping:
        return None
    import importlib

    module_path, _, attr = mapping[tool_name].partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, attr, None)


# ── Remote mode ───────────────────────────────────────────────────────────


async def _call_remote(url: str, tool_name: str, kwargs: dict[str, Any]) -> int:
    """
    Send an MCP tool call over HTTP to a running server.

    Uses the streamable-HTTP envelope: a POST with a JSON-RPC body, bearer
    token from MCP_API_KEY. We bypass the official MCP client for simplicity
    — this CLI is for ops/debugging, not for production traffic.
    """
    import os

    import httpx

    api_key = os.environ.get("MCP_API_KEY", "").strip()
    if not api_key:
        print("error: MCP_API_KEY not set in environment", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": kwargs},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        envelope = resp.json()
    except httpx.HTTPError as e:
        print(f"error: HTTP call failed: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError:
        print(f"error: server returned non-JSON (status {resp.status_code})", file=sys.stderr)
        return 1

    if "error" in envelope:
        _print(envelope["error"])
        return 1
    result = envelope.get("result", envelope)
    _print(result)
    # Best-effort: if result contains structured content with ok=False, exit non-zero
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            inner = content[0]
            if isinstance(inner, dict) and inner.get("type") == "text":
                try:
                    parsed = json.loads(inner.get("text", ""))
                    if isinstance(parsed, dict) and parsed.get("ok") is False:
                        return 1
                except json.JSONDecodeError:
                    pass
    return 0

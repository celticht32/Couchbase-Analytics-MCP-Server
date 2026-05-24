# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Process entrypoint — used by both `python -m cb_analytics_mcp` and the
`cb-analytics-mcp` console script.

Modes:
  default     Start the MCP server (and the GUI if GUI_ENABLED=true)
  --gui-only  Start only the GUI (useful for local admin without MCP)
  --check     Validate config and exit
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import structlog

from cb_analytics_mcp.config import config_summary, load_config, validate_config

log = structlog.get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cb-analytics-mcp",
        description="MCP server + GUI for Couchbase Enterprise Analytics",
    )
    parser.add_argument(
        "--gui-only",
        action="store_true",
        help="Run only the GUI (without the MCP server)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate config and exit without starting any server",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cb-analytics-mcp {_version()}",
    )

    # ── tools subcommand (CLI for invoking individual tools) ─────────────────
    sub = parser.add_subparsers(dest="command")
    tools = sub.add_parser(
        "tools",
        help="CLI utilities for inspecting and calling individual MCP tools",
    )
    tools_sub = tools.add_subparsers(dest="tools_command", required=False)

    list_p = tools_sub.add_parser("list", help="List all registered tools and exit")
    list_p.add_argument(
        "--category",
        choices=["query", "read", "write"],
        help="Filter by rate-limit category",
    )

    call_p = tools_sub.add_parser("call", help="Invoke a single tool")
    call_p.add_argument("name", help="Tool name (e.g. list_dataverses, execute_query)")
    call_p.add_argument(
        "--arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Tool argument (repeatable). VALUE is parsed as JSON when "
            "possible, otherwise as a string. Examples: --arg cluster=prod "
            "--arg statement='SELECT 1' --arg named_args='{\"id\": 5}'"
        ),
    )
    mode_grp = call_p.add_mutually_exclusive_group()
    mode_grp.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Instantiate the client pool in-process and call the tool directly. "
            "No running server required. Uses the same env config the server "
            "would use. This is the default if --remote is not specified."
        ),
    )
    mode_grp.add_argument(
        "--remote",
        metavar="URL",
        help=(
            "Send the call via HTTP to a running cb-analytics-mcp server. "
            "Example: --remote http://localhost:8000/mcp. Reads MCP_API_KEY "
            "from the environment for the bearer token."
        ),
    )

    return parser.parse_args(argv)


def _version() -> str:
    from cb_analytics_mcp import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # ── tools subcommand routes off before normal startup ────────────────────
    if args.command == "tools":
        from cb_analytics_mcp.cli import run_tools_command

        return run_tools_command(args)

    try:
        cfg = load_config()
    except (ValueError, FileNotFoundError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    errors = validate_config(cfg, strict=not args.gui_only)
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 2

    if args.check:
        from cb_analytics_mcp.observability.logging import configure_logging

        configure_logging(level=cfg.observability.log_level, fmt=cfg.observability.log_format)
        log.info("config_valid", config=config_summary(cfg))
        return 0

    if args.gui_only:
        return _run_gui_only(cfg)

    return _run_mcp_server(cfg)


def _run_mcp_server(cfg: Any) -> int:
    """Run the FastMCP server (and the GUI in parallel if enabled)."""
    from cb_analytics_mcp.server import build_server

    mcp, _pool, _metrics, _audit = build_server(cfg)

    if cfg.gui.enabled:
        # Run GUI + MCP concurrently
        return asyncio.run(_run_both(mcp, cfg))

    try:
        asyncio.run(mcp.run_streamable_http_async())
    except KeyboardInterrupt:
        log.info("server_interrupted")
    return 0


async def _run_both(mcp: Any, cfg: Any) -> int:
    """Run MCP server and GUI in parallel asyncio tasks."""
    from cb_analytics_mcp.gui.app import run_gui

    mcp_task = asyncio.create_task(mcp.run_streamable_http_async(), name="mcp")
    gui_task = asyncio.create_task(run_gui(cfg), name="gui")

    try:
        done, pending = await asyncio.wait({mcp_task, gui_task}, return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()
        for task in done:
            if task.exception():
                log.error("task_failed", task=task.get_name(), error=str(task.exception()))
    except KeyboardInterrupt:
        log.info("server_interrupted")
        for task in (mcp_task, gui_task):
            task.cancel()
    return 0


def _run_gui_only(cfg: Any) -> int:
    """Run only the GUI (no MCP server)."""
    from cb_analytics_mcp.gui.app import run_gui_blocking

    run_gui_blocking(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())

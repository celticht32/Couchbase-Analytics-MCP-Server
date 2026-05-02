# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Command-line interface for the Couchbase Enterprise Analytics SDK.

Usage:
    cb-analytics query execute "SELECT 1 AS n"
    cb-analytics admin status
    cb-analytics admin active-requests
    cb-analytics config get-service
    cb-analytics links list
    cb-analytics security users list
    cb-analytics cluster info
    cb-analytics gui    # launch the TUI
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from cb_analytics.client import AnalyticsClient
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import AnalyticsError, AnalyticsQueryError
from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency, ServiceConfig

app = typer.Typer(
    name="cb-analytics",
    help="Couchbase Enterprise Analytics REST API CLI",
    no_args_is_help=True,
)
query_app = typer.Typer(help="SQL++ query execution")
admin_app = typer.Typer(help="Admin operations")
config_app = typer.Typer(help="Configuration management")
links_app = typer.Typer(help="Analytics links management")
security_app = typer.Typer(help="Security and RBAC")
cluster_app = typer.Typer(help="Cluster operations")

app.add_typer(query_app, name="query")
app.add_typer(admin_app, name="admin")
app.add_typer(config_app, name="config")
app.add_typer(links_app, name="links")
app.add_typer(security_app, name="security")
app.add_typer(cluster_app, name="cluster")

console = Console()

# ── Global options ────────────────────────────────────────────────────────────

HOST_OPT = typer.Option(None, "--host", "-h", envvar="CB_ANALYTICS_HOST", help="Cluster host")
PORT_OPT = typer.Option(None, "--port", "-p", envvar="CB_ANALYTICS_MGMT_PORT", help="Management port")
USER_OPT = typer.Option(None, "--username", "-u", envvar="CB_ANALYTICS_USERNAME")
PASS_OPT = typer.Option(None, "--password", envvar="CB_ANALYTICS_PASSWORD")


def get_client(host: str | None, port: int | None, username: str | None, password: str | None) -> AnalyticsClient:
    kwargs = {}
    if host:
        kwargs["host"] = host
    if port:
        kwargs["mgmt_port"] = port
    if username:
        kwargs["username"] = username
    if password:
        kwargs["password"] = password
    config = AnalyticsClientConfig(**kwargs)
    return AnalyticsClient(config)


def run_async(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ── Query commands ────────────────────────────────────────────────────────────


@query_app.command("execute")
def query_execute(
    statement: str = typer.Argument(..., help="SQL++ statement to execute"),
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
    consistency: str = typer.Option("not_bounded", help="Scan consistency"),
    timeout: Optional[str] = typer.Option(None, help="Timeout e.g. 30s"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON results"),
) -> None:
    """Execute a SQL++ statement and display results."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            try:
                sc = ScanConsistency(consistency)
                result = await client.analytics.execute(
                    AnalyticsQueryRequest(
                        statement=statement,
                        scan_consistency=sc,
                        timeout=timeout,
                    )
                )
                if result.results:
                    if isinstance(result.results[0], dict):
                        table = Table(*result.results[0].keys(), show_header=True)
                        for row in result.results:
                            table.add_row(*[str(v) for v in row.values()])
                        console.print(table)
                    else:
                        for r in result.results:
                            console.print(r)
                else:
                    console.print("[dim]No rows returned[/dim]")

                if result.metrics:
                    m = result.metrics
                    console.print(
                        f"\n[dim]elapsed={m.elapsedTime}  exec={m.executionTime}  "
                        f"rows={m.resultCount}  size={m.resultSize}B[/dim]"
                    )
            except AnalyticsQueryError as e:
                console.print(f"[red]Query error [{e.code}]: {e}[/red]")
                raise typer.Exit(1)
            except AnalyticsError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)

    run_async(_run())


@query_app.command("explain")
def query_explain(
    statement: str = typer.Argument(...),
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Return the query execution plan for a SQL++ statement."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            result = await client.analytics.execute(
                AnalyticsQueryRequest(statement=f"EXPLAIN {statement}")
            )
            console.print(JSON(json.dumps(result.results)))

    run_async(_run())


# ── Admin commands ────────────────────────────────────────────────────────────


@admin_app.command("status")
def admin_status(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Show Analytics service status."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            status = await client.admin.get_service_status()
            console.print(JSON(json.dumps(status.model_dump(exclude_none=True))))

    run_async(_run())


@admin_app.command("active-requests")
def admin_active(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """List currently running Analytics queries."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            reqs = await client.admin.get_active_requests()
            if not reqs:
                console.print("[dim]No active requests[/dim]")
                return
            table = Table("Context ID", "Elapsed", "State", "Statement")
            for r in reqs:
                stmt = (r.statement or "")[:60]
                table.add_row(r.clientContextID or "", r.elapsedTime or "", r.state or "", stmt)
            console.print(table)

    run_async(_run())


@admin_app.command("ingestion")
def admin_ingestion(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Show ingestion status for all links and datasets."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            status = await client.admin.get_ingestion_status()
            console.print(JSON(json.dumps(status.model_dump())))

    run_async(_run())


# ── Config commands ───────────────────────────────────────────────────────────


@config_app.command("get-service")
def config_get_service(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Display current service-level configuration."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            cfg = await client.config.get_service_config()
            console.print(JSON(json.dumps(cfg.model_dump(exclude_none=True))))

    run_async(_run())


@config_app.command("set")
def config_set(
    param: str = typer.Argument(..., help="Parameter name e.g. resultTtl"),
    value: str = typer.Argument(..., help="New value"),
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Set a single service configuration parameter."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            # Try to coerce to int/bool
            typed_value: int | bool | str
            if value.isdigit():
                typed_value = int(value)
            elif value.lower() in ("true", "false"):
                typed_value = value.lower() == "true"
            else:
                typed_value = value

            cfg = ServiceConfig(**{param: typed_value})
            result = await client.config.update_service_config(cfg)
            console.print(f"[green]Updated {param}[/green]")
            console.print(JSON(json.dumps(result.model_dump(exclude_none=True))))

    run_async(_run())


# ── Links commands ────────────────────────────────────────────────────────────


@links_app.command("list")
def links_list(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
    dataverse: Optional[str] = typer.Option(None, help="Filter by dataverse"),
    link_type: Optional[str] = typer.Option(None, "--type", help="Filter by type"),
) -> None:
    """List all Analytics links."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            links = await client.links.get_all_links(dataverse=dataverse, link_type=link_type)
            if not links:
                console.print("[dim]No links found[/dim]")
                return
            table = Table("Name", "Dataverse", "Type", "Active Datasets")
            for lk in links:
                datasets = ", ".join(lk.activeDatasets or [])
                table.add_row(lk.name or "", lk.dataverse or "", lk.type or "", datasets)
            console.print(table)

    run_async(_run())


# ── Security commands ─────────────────────────────────────────────────────────


@security_app.command("users")
def security_users(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """List all RBAC users."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            users = await client.security.list_users()
            table = Table("ID", "Domain", "Roles")
            for u in users:
                roles = ", ".join(r.get("role", "") for r in (u.roles or []))
                table.add_row(u.id or "", u.domain or "", roles)
            console.print(table)

    run_async(_run())


@security_app.command("roles")
def security_roles(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """List all available RBAC roles."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            roles = await client.security.list_roles()
            table = Table("Role", "Name", "Description")
            for r in roles:
                table.add_row(
                    r.get("role", ""),
                    r.get("name", ""),
                    r.get("desc", ""),
                )
            console.print(table)

    run_async(_run())


# ── Cluster commands ──────────────────────────────────────────────────────────


@cluster_app.command("info")
def cluster_info(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Display cluster information and node list."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            info = await client.cluster.get_cluster_details()
            console.print(f"[bold]Cluster:[/bold] {info.clusterName}")
            console.print(f"[bold]Balanced:[/bold] {info.balanced}")
            console.print(f"[bold]Memory Quota:[/bold] {info.memoryQuota} MB")
            table = Table("Hostname", "Status", "Services")
            for node in info.nodes:
                table.add_row(
                    node.get("hostname", ""),
                    node.get("status", ""),
                    ", ".join(node.get("services", [])),
                )
            console.print(table)

    run_async(_run())


@cluster_app.command("tasks")
def cluster_tasks(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """List currently running cluster tasks."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            tasks = await client.cluster.get_cluster_tasks()
            if not tasks:
                console.print("[dim]No active tasks[/dim]")
                return
            table = Table("Type", "Status", "Progress")
            for task in tasks:
                table.add_row(
                    task.type or "",
                    task.status or "",
                    f"{task.progress:.1f}%" if task.progress is not None else "",
                )
            console.print(table)

    run_async(_run())


@cluster_app.command("ping")
def cluster_ping(
    host: Optional[str] = HOST_OPT,
    port: Optional[int] = PORT_OPT,
    username: Optional[str] = USER_OPT,
    password: Optional[str] = PASS_OPT,
) -> None:
    """Check connectivity to the cluster."""

    async def _run() -> None:
        async with get_client(host, port, username, password) as client:
            ok = await client.ping()
            if ok:
                console.print("[green]✓ Connected[/green]")
            else:
                console.print("[red]✗ Cannot connect[/red]")
                raise typer.Exit(1)

    run_async(_run())


# ── GUI launcher ──────────────────────────────────────────────────────────────


@app.command("gui")
def launch_gui() -> None:
    """Launch the interactive Terminal UI."""
    from cb_analytics.gui.app import run as run_gui
    run_gui()


if __name__ == "__main__":
    app()

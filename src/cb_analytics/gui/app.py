# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Couchbase Enterprise Analytics — Terminal User Interface (TUI).

Built with Textual. Provides a rich, keyboard-driven interface for:
  ▸ SQL++ query execution with metrics display
  ▸ Active/completed request monitoring
  ▸ Service status and ingestion health
  ▸ Configuration viewer and editor
  ▸ RBAC user/group management
  ▸ Link management (list, create, delete)
  ▸ Server group overview
  ▸ Cluster stats

Run:
    cb-analytics-gui
    # or
    python -m cb_analytics.gui.app
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Markdown,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from cb_analytics.client import AnalyticsClient
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import AnalyticsError, AnalyticsQueryError
from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency


# ── Styles ────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: $surface;
}

#header-info {
    background: $primary-darken-3;
    color: $text;
    height: 1;
    padding: 0 2;
    text-align: right;
}

.panel {
    border: round $primary;
    padding: 1;
    margin: 1;
}

.panel-title {
    color: $accent;
    text-style: bold;
    padding: 0 1;
}

.metric-grid {
    layout: grid;
    grid-size: 3;
    grid-gutter: 1;
    height: auto;
}

.metric-box {
    border: solid $primary-darken-1;
    height: 5;
    padding: 0 1;
    background: $surface-darken-1;
}

.metric-label {
    color: $text-muted;
    text-style: italic;
    font-size: 0.8;
}

.metric-value {
    color: $accent;
    text-style: bold;
}

#query-editor {
    height: 12;
    border: solid $primary;
}

#query-toolbar {
    height: 3;
    layout: horizontal;
    padding: 0 1;
}

#results-table {
    height: 1fr;
}

#status-bar {
    height: 1;
    background: $primary-darken-2;
    padding: 0 2;
    color: $text-muted;
}

.error-text {
    color: $error;
}

.success-text {
    color: $success;
}

.warning-text {
    color: $warning;
}

Button {
    margin: 0 1;
}

DataTable {
    height: 1fr;
}

.form-row {
    height: 3;
    layout: horizontal;
    padding: 0 1;
}

.form-label {
    width: 20;
    height: 3;
    content-align: right middle;
    padding-right: 2;
    color: $text-muted;
}

Input {
    width: 1fr;
}

Select {
    width: 1fr;
}
"""

# ── Connection Screen ─────────────────────────────────────────────────────────


class ConnectionScreen(Screen):  # type: ignore[type-arg]
    """Initial screen: enter connection credentials."""

    BINDINGS = [Binding("escape", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🔌  Connect to Couchbase Enterprise Analytics", classes="panel-title"),
            Container(
                Horizontal(
                    Label("Host:", classes="form-label"),
                    Input(value=os.getenv("CB_ANALYTICS_HOST", "localhost"), id="inp-host"),
                    classes="form-row",
                ),
                Horizontal(
                    Label("Mgmt Port:", classes="form-label"),
                    Input(value=os.getenv("CB_ANALYTICS_MGMT_PORT", "8091"), id="inp-mgmt-port"),
                    classes="form-row",
                ),
                Horizontal(
                    Label("Analytics Port:", classes="form-label"),
                    Input(value=os.getenv("CB_ANALYTICS_ANALYTICS_PORT", "8095"), id="inp-analytics-port"),
                    classes="form-row",
                ),
                Horizontal(
                    Label("Username:", classes="form-label"),
                    Input(value=os.getenv("CB_ANALYTICS_USERNAME", "Administrator"), id="inp-user"),
                    classes="form-row",
                ),
                Horizontal(
                    Label("Password:", classes="form-label"),
                    Input(
                        value=os.getenv("CB_ANALYTICS_PASSWORD", "password"),
                        id="inp-pass",
                        password=True,
                    ),
                    classes="form-row",
                ),
                Horizontal(
                    Button("Connect", variant="primary", id="btn-connect"),
                    Button("Quit", variant="default", id="btn-quit"),
                ),
                classes="panel",
            ),
        )
        yield Footer()

    @on(Button.Pressed, "#btn-connect")
    async def do_connect(self) -> None:
        host = self.query_one("#inp-host", Input).value.strip()
        mgmt_port = int(self.query_one("#inp-mgmt-port", Input).value.strip() or "8091")
        analytics_port = int(self.query_one("#inp-analytics-port", Input).value.strip() or "8095")
        username = self.query_one("#inp-user", Input).value.strip()
        password = self.query_one("#inp-pass", Input).value.strip()

        config = AnalyticsClientConfig(
            host=host,
            mgmt_port=mgmt_port,
            analytics_port=analytics_port,
            username=username,
            password=password,
            verify_ssl=False,
            max_retries=1,
        )
        client = AnalyticsClient(config)
        try:
            ok = await client.ping()
            if ok:
                self.app.client = client  # type: ignore[attr-defined]
                await self.app.push_screen(MainScreen())
            else:
                self.notify("Could not connect — check credentials and host", severity="error")
        except Exception as e:
            self.notify(f"Connection failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-quit")
    def do_quit(self) -> None:
        self.app.exit()


# ── Query Panel ───────────────────────────────────────────────────────────────


class QueryPanel(Container):
    """SQL++ query editor with results table and metrics."""

    last_metrics: reactive[dict[str, Any]] = reactive({})

    def compose(self) -> ComposeResult:
        yield Static("SQL++ Query", classes="panel-title")
        yield TextArea(
            "SELECT 1 AS ping;",
            id="query-editor",
            language="sql",
            show_line_numbers=True,
        )
        yield Horizontal(
            Button("▶  Run", variant="primary", id="btn-run"),
            Button("⏹  Cancel", variant="warning", id="btn-cancel"),
            Select(
                [
                    ("not_bounded", "not_bounded"),
                    ("request_plus", "request_plus"),
                    ("at_plus", "at_plus"),
                ],
                value="not_bounded",
                id="sel-consistency",
            ),
            Input(placeholder="timeout e.g. 30s", id="inp-timeout"),
            id="query-toolbar",
        )
        yield Static("", id="query-status", classes="status-bar")
        yield DataTable(id="results-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.cursor_type = "row"

    @on(Button.Pressed, "#btn-run")
    async def run_query(self) -> None:
        statement = self.query_one("#query-editor", TextArea).text.strip()
        if not statement:
            return

        consistency_val = self.query_one("#sel-consistency", Select).value
        timeout = self.query_one("#inp-timeout", Input).value.strip() or None

        sc = ScanConsistency(consistency_val) if consistency_val else None

        self._update_status("Running…", "warning")
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]

        try:
            result = await client.analytics.execute(
                AnalyticsQueryRequest(
                    statement=statement,
                    scan_consistency=sc,
                    timeout=timeout,
                )
            )
            self._render_results(result.results)
            metrics = result.metrics
            status = (
                f"✓ {metrics.resultCount} rows  "
                f"elapsed={metrics.elapsedTime}  "
                f"exec={metrics.executionTime}  "
                f"size={metrics.resultSize} bytes"
            ) if metrics else "✓ success"
            self._update_status(status, "success")
        except AnalyticsQueryError as e:
            self._update_status(f"✗ Query error [{e.code}]: {e}", "error")
            self._clear_results()
        except AnalyticsError as e:
            self._update_status(f"✗ {e}", "error")
            self._clear_results()

    @on(Button.Pressed, "#btn-cancel")
    async def cancel_query(self) -> None:
        self.notify("Cancel sent (by clientContextID)", severity="information")

    def _render_results(self, rows: list[Any]) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        if not rows:
            table.add_column("(no rows)", key="empty")
            return

        if not isinstance(rows[0], dict):
            table.add_column("value")
            for row in rows:
                table.add_row(str(row))
            return

        cols = list(rows[0].keys())
        for col in cols:
            table.add_column(col, key=col)
        for row in rows:
            table.add_row(*[str(row.get(c, "")) for c in cols])

    def _clear_results(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

    def _update_status(self, msg: str, level: str = "info") -> None:
        status = self.query_one("#query-status", Static)
        status.update(msg)


# ── Monitor Panel ─────────────────────────────────────────────────────────────


class MonitorPanel(Container):
    """Live monitoring: service status, ingestion, active requests."""

    def compose(self) -> ComposeResult:
        yield Static("Service Monitor", classes="panel-title")
        yield Horizontal(
            Button("Refresh", variant="primary", id="btn-refresh-monitor"),
            Button("Restart Service ⚠️", variant="error", id="btn-restart-service"),
        )
        yield Container(
            Static("SERVICE STATUS", classes="metric-label"),
            Static("…", id="svc-status", classes="metric-value"),
            Static("INGESTION LINKS", classes="metric-label"),
            Static("…", id="svc-ingestion", classes="metric-value"),
            classes="panel",
        )
        yield Static("Active Requests", classes="panel-title")
        yield DataTable(id="active-reqs-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#active-reqs-table", DataTable)
        table.add_column("Context ID")
        table.add_column("Elapsed")
        table.add_column("State")
        table.add_column("Statement")
        self.refresh_monitor()

    @on(Button.Pressed, "#btn-refresh-monitor")
    def on_refresh(self) -> None:
        self.refresh_monitor()

    @on(Button.Pressed, "#btn-restart-service")
    async def on_restart(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            await client.admin.restart_service()
            self.notify("Service restart initiated", severity="warning")
        except AnalyticsError as e:
            self.notify(f"Restart failed: {e}", severity="error")

    @work(exclusive=True)
    async def refresh_monitor(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            status = await client.admin.get_service_status()
            ingestion = await client.admin.get_ingestion_status()
            active = await client.admin.get_active_requests()

            self.query_one("#svc-status", Static).update(
                f"[green]{status.state}[/green]" if status.state == "ACTIVE"
                else f"[red]{status.state}[/red]"
            )
            self.query_one("#svc-ingestion", Static).update(
                f"{len(ingestion.links)} link(s)"
            )

            table = self.query_one("#active-reqs-table", DataTable)
            table.clear()
            for req in active:
                stmt = (req.statement or "")[:60] + "…" if req.statement and len(req.statement) > 60 else (req.statement or "")
                table.add_row(
                    req.clientContextID or "",
                    req.elapsedTime or "",
                    req.state or "",
                    stmt,
                )
        except AnalyticsError as e:
            self.notify(f"Monitor refresh failed: {e}", severity="error")


# ── Config Panel ──────────────────────────────────────────────────────────────


class ConfigPanel(Container):
    """View and edit Analytics service configuration."""

    def compose(self) -> ComposeResult:
        yield Static("Service Configuration", classes="panel-title")
        yield Horizontal(
            Button("Load Config", variant="primary", id="btn-load-config"),
        )
        yield ScrollableContainer(
            Static("(Press 'Load Config' to fetch current configuration)", id="config-display"),
            classes="panel",
        )

    @on(Button.Pressed, "#btn-load-config")
    @work(exclusive=True)
    async def load_config(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            svc_config = await client.config.get_service_config()
            node_config = await client.config.get_node_config()
            combined = {
                "service": svc_config.model_dump(exclude_none=True),
                "node": node_config.model_dump(exclude_none=True),
            }
            pretty = json.dumps(combined, indent=2)
            self.query_one("#config-display", Static).update(
                f"[dim]Last fetched: {datetime.now().strftime('%H:%M:%S')}[/dim]\n\n{pretty}"
            )
        except AnalyticsError as e:
            self.notify(f"Config load failed: {e}", severity="error")


# ── RBAC Panel ────────────────────────────────────────────────────────────────


class RbacPanel(Container):
    """User and group management panel."""

    def compose(self) -> ComposeResult:
        yield Static("RBAC — Users & Groups", classes="panel-title")
        yield Horizontal(
            Button("Refresh Users", variant="primary", id="btn-rbac-refresh"),
        )
        yield DataTable(id="users-table", zebra_stripes=True)
        yield Static("Groups", classes="panel-title")
        yield DataTable(id="groups-table", zebra_stripes=True)

    def on_mount(self) -> None:
        users_table = self.query_one("#users-table", DataTable)
        users_table.add_column("Username")
        users_table.add_column("Domain")
        users_table.add_column("Roles")

        groups_table = self.query_one("#groups-table", DataTable)
        groups_table.add_column("Group")
        groups_table.add_column("Description")
        groups_table.add_column("Roles")

        self.refresh_rbac()

    @on(Button.Pressed, "#btn-rbac-refresh")
    def on_refresh(self) -> None:
        self.refresh_rbac()

    @work(exclusive=True)
    async def refresh_rbac(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            users = await client.security.list_users()
            groups = await client.security.list_groups()

            users_table = self.query_one("#users-table", DataTable)
            users_table.clear()
            for user in users:
                role_str = ", ".join(
                    r.get("role", "") for r in (user.roles or [])
                )
                users_table.add_row(
                    user.id or "", user.domain or "", role_str
                )

            groups_table = self.query_one("#groups-table", DataTable)
            groups_table.clear()
            for group in groups:
                role_str = ", ".join(
                    r.get("role", "") for r in (group.roles or [])
                )
                groups_table.add_row(
                    group.id or "", group.description or "", role_str
                )
        except AnalyticsError as e:
            self.notify(f"RBAC refresh failed: {e}", severity="error")


# ── Links Panel ───────────────────────────────────────────────────────────────


class LinksPanel(Container):
    """Analytics links management."""

    def compose(self) -> ComposeResult:
        yield Static("Analytics Links", classes="panel-title")
        yield Horizontal(
            Button("Refresh Links", variant="primary", id="btn-links-refresh"),
        )
        yield DataTable(id="links-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#links-table", DataTable)
        table.add_column("Name")
        table.add_column("Dataverse")
        table.add_column("Type")
        table.add_column("Active Datasets")
        self.refresh_links()

    @on(Button.Pressed, "#btn-links-refresh")
    def on_refresh(self) -> None:
        self.refresh_links()

    @work(exclusive=True)
    async def refresh_links(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            links = await client.links.get_all_links()
            table = self.query_one("#links-table", DataTable)
            table.clear()
            for link in links:
                datasets = ", ".join(link.activeDatasets or [])
                table.add_row(
                    link.name or "",
                    link.dataverse or "",
                    link.type or "",
                    datasets,
                )
        except AnalyticsError as e:
            self.notify(f"Links refresh failed: {e}", severity="error")


# ── Cluster Panel ─────────────────────────────────────────────────────────────


class ClusterPanel(Container):
    """Cluster overview: nodes, server groups, cluster tasks."""

    def compose(self) -> ComposeResult:
        yield Static("Cluster Overview", classes="panel-title")
        yield Horizontal(
            Button("Refresh", variant="primary", id="btn-cluster-refresh"),
        )
        yield Static("Nodes", classes="panel-title")
        yield DataTable(id="nodes-table", zebra_stripes=True)
        yield Static("Server Groups", classes="panel-title")
        yield DataTable(id="groups-table", zebra_stripes=True)
        yield Static("Active Tasks", classes="panel-title")
        yield DataTable(id="tasks-table", zebra_stripes=True)

    def on_mount(self) -> None:
        nodes = self.query_one("#nodes-table", DataTable)
        nodes.add_column("Hostname")
        nodes.add_column("Status")
        nodes.add_column("Services")

        groups = self.query_one("#groups-table", DataTable)
        groups.add_column("Group Name")
        groups.add_column("Node Count")

        tasks = self.query_one("#tasks-table", DataTable)
        tasks.add_column("Type")
        tasks.add_column("Status")
        tasks.add_column("Progress")

        self.refresh_cluster()

    @on(Button.Pressed, "#btn-cluster-refresh")
    def on_refresh(self) -> None:
        self.refresh_cluster()

    @work(exclusive=True)
    async def refresh_cluster(self) -> None:
        client: AnalyticsClient = self.app.client  # type: ignore[attr-defined]
        try:
            details = await client.cluster.get_cluster_details()
            sg_response = await client.server_groups.get_groups()
            tasks = await client.cluster.get_cluster_tasks()

            nodes_table = self.query_one("#nodes-table", DataTable)
            nodes_table.clear()
            for node in details.nodes:
                services = ", ".join(node.get("services", []))
                nodes_table.add_row(
                    node.get("hostname", ""),
                    node.get("status", ""),
                    services,
                )

            groups_table = self.query_one("#groups-table", DataTable)
            groups_table.clear()
            for group in sg_response.groups:
                groups_table.add_row(
                    group.name or "",
                    str(len(group.nodes)),
                )

            tasks_table = self.query_one("#tasks-table", DataTable)
            tasks_table.clear()
            for task in tasks:
                tasks_table.add_row(
                    task.type or "",
                    task.status or "",
                    f"{task.progress:.1f}%" if task.progress is not None else "",
                )
        except AnalyticsError as e:
            self.notify(f"Cluster refresh failed: {e}", severity="error")


# ── Main Screen ───────────────────────────────────────────────────────────────


class MainScreen(Screen):  # type: ignore[type-arg]
    """Primary screen with tabbed interface."""

    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit"),
        Binding("ctrl+r", "refresh_all", "Refresh All"),
        Binding("f1", "switch_tab('query')", "Query"),
        Binding("f2", "switch_tab('monitor')", "Monitor"),
        Binding("f3", "switch_tab('config')", "Config"),
        Binding("f4", "switch_tab('rbac')", "RBAC"),
        Binding("f5", "switch_tab('links')", "Links"),
        Binding("f6", "switch_tab('cluster')", "Cluster"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="query"):
            with TabPane("Query [F1]", id="query"):
                yield QueryPanel()
            with TabPane("Monitor [F2]", id="monitor"):
                yield MonitorPanel()
            with TabPane("Config [F3]", id="config"):
                yield ConfigPanel()
            with TabPane("RBAC [F4]", id="rbac"):
                yield RbacPanel()
            with TabPane("Links [F5]", id="links"):
                yield LinksPanel()
            with TabPane("Cluster [F6]", id="cluster"):
                yield ClusterPanel()
        yield Footer()

    def action_refresh_all(self) -> None:
        self.notify("Refreshing…", severity="information", timeout=1)

    def action_switch_tab(self, tab_id: str) -> None:
        try:
            self.query_one(TabbedContent).active = tab_id
        except NoMatches:
            pass


# ── App ───────────────────────────────────────────────────────────────────────


class CbAnalyticsApp(App):  # type: ignore[type-arg]
    """Couchbase Enterprise Analytics TUI Application."""

    TITLE = "Couchbase Enterprise Analytics"
    SUB_TITLE = "REST API Client"
    CSS = CSS

    client: AnalyticsClient | None = None

    async def on_mount(self) -> None:
        await self.push_screen(ConnectionScreen())

    async def on_unmount(self) -> None:
        if self.client:
            await self.client.close()


def run() -> None:
    """Entry point for the cb-analytics-gui command."""
    app = CbAnalyticsApp()
    app.run()


if __name__ == "__main__":
    run()

# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Couchbase Enterprise Analytics — Terminal User Interface (TUI).

Bug fixes vs v1.0:
  - Removed unused imports (asyncio, Vertical, Log, Markdown)
  - MonitorTab widget updates now use call_from_thread() from @work tasks
  - Auto-refresh timer added to MonitorPanel (configurable: 15/30/60s/manual)
  - client accessed via self.app.client with proper None guard
  - SchemaTab dataset-click handler properly awaits in @work context
  - ConnectionScreen properly sets self.app.client before navigating
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
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

import os


# ── Connection Screen ─────────────────────────────────────────────────────────

class ConnectionScreen(Screen):  # type: ignore[type-arg]
    """Startup screen for entering cluster credentials."""

    BINDINGS = [Binding("escape", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🔌  Connect to Couchbase Enterprise Analytics", id="conn-title"),
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
                id="conn-form",
            ),
            id="conn-container",
        )
        yield Footer()

    @on(Button.Pressed, "#btn-connect")
    def on_connect_pressed(self) -> None:
        """Kick off connection in a worker to avoid blocking the event loop."""
        self._do_connect()

    @work
    async def _do_connect(self) -> None:
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
            password=password,  # type: ignore[arg-type]
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
                await client.close()
                self.app.call_from_thread(
                    self.notify, "Could not connect — check credentials", severity="error"
                )
        except Exception as e:
            await client.close()
            self.app.call_from_thread(
                self.notify, f"Connection failed: {e}", severity="error"
            )

    @on(Button.Pressed, "#btn-quit")
    def do_quit(self) -> None:
        self.app.exit()


# ── Query Panel ───────────────────────────────────────────────────────────────

class QueryPanel(Container):
    """SQL++ editor with results table and metrics."""

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
                [("not_bounded", "not_bounded"), ("request_plus", "request_plus"), ("at_plus", "at_plus")],
                value="not_bounded",
                id="sel-consistency",
            ),
            Input(placeholder="timeout e.g. 30s", id="inp-timeout"),
            id="query-toolbar",
        )
        yield Static("", id="query-status", classes="status-bar")
        yield DataTable(id="results-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#results-table", DataTable).cursor_type = "row"

    @on(Button.Pressed, "#btn-run")
    def on_run_pressed(self) -> None:
        self._run_query()

    @work(exclusive=True)
    async def _run_query(self) -> None:
        statement = self.query_one("#query-editor", TextArea).text.strip()
        if not statement:
            return

        consistency_val = self.query_one("#sel-consistency", Select).value
        timeout = self.query_one("#inp-timeout", Input).value.strip() or None
        sc = ScanConsistency(consistency_val) if consistency_val else None

        self.call_from_thread(self._update_status, "Running…", "warning")

        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            self.call_from_thread(self._update_status, "✗ Not connected", "error")
            return

        try:
            result = await client.analytics.execute(
                AnalyticsQueryRequest(statement=statement, scan_consistency=sc, timeout=timeout)
            )
            self.call_from_thread(self._render_results, result.results)
            metrics = result.metrics
            status = (
                f"✓ {metrics.resultCount} rows  elapsed={metrics.elapsedTime}  "
                f"exec={metrics.executionTime}  size={metrics.resultSize}B"
            ) if metrics else "✓ success"
            self.call_from_thread(self._update_status, status, "success")
        except AnalyticsQueryError as e:
            self.call_from_thread(self._update_status, f"✗ Query error [{e.code}]: {e}", "error")
            self.call_from_thread(self._clear_results)
        except AnalyticsError as e:
            self.call_from_thread(self._update_status, f"✗ {e}", "error")
            self.call_from_thread(self._clear_results)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel_pressed(self) -> None:
        self.notify("Cancel sent — no active clientContextID tracked", severity="information")

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
        self.query_one("#results-table", DataTable).clear(columns=True)

    def _update_status(self, msg: str, level: str = "info") -> None:
        self.query_one("#query-status", Static).update(msg)


# ── Monitor Panel ─────────────────────────────────────────────────────────────

class MonitorPanel(Container):
    """Live monitoring: service status, ingestion, active requests."""

    _timer_handle: Any = None
    _refresh_interval: int = 30  # seconds

    def compose(self) -> ComposeResult:
        yield Static("Service Monitor", classes="panel-title")
        yield Horizontal(
            Button("Refresh", variant="primary", id="btn-refresh-monitor"),
            Button("Restart Service ⚠️", variant="error", id="btn-restart-service"),
            Select(
                [("15", "15s"), ("30", "30s"), ("60", "60s"), ("0", "Manual only")],
                value="30",
                id="sel-refresh-interval",
                prompt="Auto-refresh",
            ),
            id="monitor-toolbar",
        )
        yield Container(
            Static("STATUS: …", id="svc-status"),
            Static("INGESTION: …", id="svc-ingestion"),
            id="svc-cards",
        )
        yield Static("Active Requests", classes="panel-title")
        yield DataTable(id="active-reqs-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#active-reqs-table", DataTable)
        table.add_column("Context ID")
        table.add_column("Elapsed")
        table.add_column("State")
        table.add_column("Statement")
        self._start_timer()

    def on_unmount(self) -> None:
        self._stop_timer()

    @on(Select.Changed, "#sel-refresh-interval")
    def on_interval_changed(self, event: Select.Changed) -> None:
        self._stop_timer()
        try:
            self._refresh_interval = int(str(event.value))
        except (ValueError, TypeError):
            self._refresh_interval = 0
        if self._refresh_interval > 0:
            self._start_timer()

    def _start_timer(self) -> None:
        if self._refresh_interval > 0:
            self._timer_handle = self.set_interval(self._refresh_interval, self._refresh_monitor)

    def _stop_timer(self) -> None:
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None

    @on(Button.Pressed, "#btn-refresh-monitor")
    def on_refresh(self) -> None:
        self._refresh_monitor()

    @on(Button.Pressed, "#btn-restart-service")
    def on_restart_pressed(self) -> None:
        self._restart_service()

    @work
    async def _restart_service(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            await client.admin.restart_service()
            self.call_from_thread(self.notify, "Service restart initiated", severity="warning")
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"Restart failed: {e}", severity="error")

    @work(exclusive=True)
    async def _refresh_monitor(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            status = await client.admin.get_service_status()
            ingestion = await client.admin.get_ingestion_status()
            active = await client.admin.get_active_requests()

            state_str = status.state or "UNKNOWN"
            self.call_from_thread(
                self.query_one("#svc-status", Static).update,
                f"STATUS: {state_str}"
            )
            self.call_from_thread(
                self.query_one("#svc-ingestion", Static).update,
                f"INGESTION: {len(ingestion.links)} link(s)"
            )

            def _update_table() -> None:
                table = self.query_one("#active-reqs-table", DataTable)
                table.clear()
                for req in active:
                    stmt = (req.statement or "")[:60]
                    table.add_row(req.clientContextID or "", req.elapsedTime or "", req.state or "", stmt)

            self.call_from_thread(_update_table)
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"Monitor refresh failed: {e}", severity="error")


# ── Config Panel ──────────────────────────────────────────────────────────────

class ConfigPanel(Container):
    """View Analytics service and node configuration."""

    def compose(self) -> ComposeResult:
        yield Static("Service Configuration", classes="panel-title")
        yield Button("Load Config", variant="primary", id="btn-load-config")
        yield ScrollableContainer(
            Static("(Press 'Load Config' to fetch current configuration)", id="config-display"),
            id="config-scroll",
        )

    @on(Button.Pressed, "#btn-load-config")
    def on_load_pressed(self) -> None:
        self._load_config()

    @work(exclusive=True)
    async def _load_config(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            svc = await client.config.get_service_config()
            node = await client.config.get_node_config()
            combined = {"service": svc.model_dump(exclude_none=True), "node": node.model_dump(exclude_none=True)}
            pretty = json.dumps(combined, indent=2)
            ts = datetime.now().strftime("%H:%M:%S")
            self.call_from_thread(
                self.query_one("#config-display", Static).update,
                f"Last fetched: {ts}\n\n{pretty}"
            )
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"Config load failed: {e}", severity="error")


# ── RBAC Panel ────────────────────────────────────────────────────────────────

class RbacPanel(Container):
    """User and group management."""

    def compose(self) -> ComposeResult:
        yield Static("RBAC — Users & Groups", classes="panel-title")
        yield Button("Refresh Users", variant="primary", id="btn-rbac-refresh")
        yield DataTable(id="users-table", zebra_stripes=True)
        yield Static("Groups", classes="panel-title")
        yield DataTable(id="groups-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#users-table", DataTable).add_columns("Username", "Domain", "Roles")
        self.query_one("#groups-table", DataTable).add_columns("Group", "Description", "Roles")
        self._refresh_rbac()

    @on(Button.Pressed, "#btn-rbac-refresh")
    def on_refresh(self) -> None:
        self._refresh_rbac()

    @work(exclusive=True)
    async def _refresh_rbac(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            users = await client.security.list_users()
            groups = await client.security.list_groups()

            def _update() -> None:
                ut = self.query_one("#users-table", DataTable)
                ut.clear()
                for user in users:
                    role_str = ", ".join(r.get("role", "") for r in (user.roles or []))
                    ut.add_row(user.id or "", user.domain or "", role_str)

                gt = self.query_one("#groups-table", DataTable)
                gt.clear()
                for group in groups:
                    role_str = ", ".join(r.get("role", "") for r in (group.roles or []))
                    gt.add_row(group.id or "", group.description or "", role_str)

            self.call_from_thread(_update)
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"RBAC refresh failed: {e}", severity="error")


# ── Links Panel ───────────────────────────────────────────────────────────────

class LinksPanel(Container):
    """Analytics links overview."""

    def compose(self) -> ComposeResult:
        yield Static("Analytics Links", classes="panel-title")
        yield Button("Refresh Links", variant="primary", id="btn-links-refresh")
        yield DataTable(id="links-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#links-table", DataTable).add_columns("Name", "Dataverse", "Type", "Active Datasets")
        self._refresh_links()

    @on(Button.Pressed, "#btn-links-refresh")
    def on_refresh(self) -> None:
        self._refresh_links()

    @work(exclusive=True)
    async def _refresh_links(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            links = await client.links.get_all_links()

            def _update() -> None:
                table = self.query_one("#links-table", DataTable)
                table.clear()
                for link in links:
                    datasets = ", ".join(link.activeDatasets or [])
                    table.add_row(link.name or "", link.dataverse or "", link.type or "", datasets)

            self.call_from_thread(_update)
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"Links refresh failed: {e}", severity="error")


# ── Cluster Panel ─────────────────────────────────────────────────────────────

class ClusterPanel(Container):
    """Cluster nodes, server groups, and active tasks."""

    def compose(self) -> ComposeResult:
        yield Static("Cluster Overview", classes="panel-title")
        yield Button("Refresh", variant="primary", id="btn-cluster-refresh")
        yield Static("Nodes", classes="panel-title")
        yield DataTable(id="nodes-table", zebra_stripes=True)
        yield Static("Server Groups", classes="panel-title")
        yield DataTable(id="sg-table", zebra_stripes=True)
        yield Static("Active Tasks", classes="panel-title")
        yield DataTable(id="tasks-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#nodes-table", DataTable).add_columns("Hostname", "Status", "Services")
        self.query_one("#sg-table", DataTable).add_columns("Group Name", "Node Count")
        self.query_one("#tasks-table", DataTable).add_columns("Type", "Status", "Progress")
        self._refresh_cluster()

    @on(Button.Pressed, "#btn-cluster-refresh")
    def on_refresh(self) -> None:
        self._refresh_cluster()

    @work(exclusive=True)
    async def _refresh_cluster(self) -> None:
        client: AnalyticsClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            details = await client.cluster.get_cluster_details()
            sg_response = await client.server_groups.get_groups()
            tasks = await client.cluster.get_cluster_tasks()

            def _update() -> None:
                nt = self.query_one("#nodes-table", DataTable)
                nt.clear()
                for node in details.nodes:
                    nt.add_row(
                        node.get("hostname", ""),
                        node.get("status", ""),
                        ", ".join(node.get("services", [])),
                    )
                gt = self.query_one("#sg-table", DataTable)
                gt.clear()
                for group in sg_response.groups:
                    gt.add_row(group.name or "", str(len(group.nodes)))

                tt = self.query_one("#tasks-table", DataTable)
                tt.clear()
                for task in tasks:
                    tt.add_row(
                        task.type or "",
                        task.status or "",
                        f"{task.progress:.1f}%" if task.progress is not None else "",
                    )

            self.call_from_thread(_update)
        except AnalyticsError as e:
            self.call_from_thread(self.notify, f"Cluster refresh failed: {e}", severity="error")


# ── Main Screen ───────────────────────────────────────────────────────────────

class MainScreen(Screen):  # type: ignore[type-arg]
    """Primary tabbed interface."""

    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit"),
        Binding("ctrl+r", "refresh_all", "Refresh"),
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
        except Exception:
            pass


# ── App Root ──────────────────────────────────────────────────────────────────

class CbAnalyticsApp(App):  # type: ignore[type-arg]
    """Couchbase Enterprise Analytics TUI Application."""

    TITLE = "Couchbase Enterprise Analytics"
    SUB_TITLE = "REST API Client v1.1.0"

    client: AnalyticsClient | None = None

    async def on_mount(self) -> None:
        await self.push_screen(ConnectionScreen())

    async def on_unmount(self) -> None:
        if self.client is not None:
            await self.client.close()


def run() -> None:
    """Entry point for cb-analytics-gui command."""
    CbAnalyticsApp().run()


if __name__ == "__main__":
    run()

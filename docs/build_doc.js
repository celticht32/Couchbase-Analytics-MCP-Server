// cb-analytics Word Document Generator
// Copyright (c) 2026 Chris Ahrendt — MIT License
"use strict";

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, LevelFormat, ExternalHyperlink,
  HeadingLevel, BorderStyle, WidthType, ShadingType, VerticalAlign,
  SimpleField, PageBreak, UnderlineType, TableOfContents
} = require("docx");
const fs = require("fs");
const path = require("path");

// ── Constants ─────────────────────────────────────────────────────────────────
const BASE   = path.join(__dirname, "images");
const DXA    = 1440; // 1 inch in DXA
const PAGE_W = 12240;
const PAGE_H = 15840;
const MARGIN = 1080; // 0.75 inch
const CONTENT_W = PAGE_W - (MARGIN * 2); // 10080 DXA = 7 inches

// ── Colours ───────────────────────────────────────────────────────────────────
const DARK_BLUE   = "1E3A5F";
const MID_BLUE    = "2E5FA3";
const LIGHT_BLUE  = "D6E4F7";
const ACCENT      = "C0392B";
const GRAY_DARK   = "2C2C2C";
const GRAY_MID    = "555555";
const GRAY_LIGHT  = "F5F5F5";
const WHITE       = "FFFFFF";
const TABLE_HEAD  = "1E3A5F";
const TABLE_ROW1  = "FFFFFF";
const TABLE_ROW2  = "EEF4FB";
const CODE_BG     = "F0F4F8";
const BORDER_COL  = "CCCCCC";

// ── Helpers ───────────────────────────────────────────────────────────────────
function border() {
  const b = { style: BorderStyle.SINGLE, size: 1, color: BORDER_COL };
  return { top: b, bottom: b, left: b, right: b };
}
function noBorder() {
  const b = { style: BorderStyle.NONE, size: 0, color: WHITE };
  return { top: b, bottom: b, left: b, right: b };
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 180 },
    children: [new TextRun({ text, font: "Arial", size: 36, bold: true, color: DARK_BLUE })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: MID_BLUE, space: 6 } }
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: 28, bold: true, color: MID_BLUE })]
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: GRAY_DARK })]
  });
}

function para(runs, spacing = { before: 80, after: 80 }) {
  const children = typeof runs === "string"
    ? [new TextRun({ text: runs, font: "Arial", size: 22, color: GRAY_DARK })]
    : runs;
  return new Paragraph({ children, spacing });
}

function body(text, color = GRAY_DARK) {
  return para([new TextRun({ text, font: "Arial", size: 22, color })]);
}

function code(text) {
  return new Paragraph({
    spacing: { before: 40, after: 40 },
    shading: { fill: CODE_BG, type: ShadingType.CLEAR },
    indent: { left: 360 },
    children: [new TextRun({ text, font: "Courier New", size: 18, color: "1A1A6E" })]
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: "Arial", size: 22, color: GRAY_DARK })]
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: "Arial", size: 22, color: GRAY_DARK })]
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function spacer(points = 120) {
  return new Paragraph({ spacing: { before: 0, after: points }, children: [] });
}

function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 160 },
    children: [new TextRun({ text, font: "Arial", size: 18, italics: true, color: GRAY_MID })]
  });
}

function callout(label, text, color = MID_BLUE, bgColor = LIGHT_BLUE) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [new TableRow({
      children: [new TableCell({
        borders: { top: { style: BorderStyle.SINGLE, size: 8, color }, bottom: noBorder().bottom, left: noBorder().left, right: noBorder().right },
        shading: { fill: bgColor, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 120, left: 200, right: 200 },
        width: { size: CONTENT_W, type: WidthType.DXA },
        children: [
          new Paragraph({ spacing: { before: 0, after: 60 }, children: [new TextRun({ text: label, font: "Arial", size: 20, bold: true, color })] }),
          new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text, font: "Arial", size: 20, color: GRAY_DARK })] }),
        ]
      })]
    })]
  });
}

// ── Image helper — scale to fit content width, maintain aspect ratio ──────────
function imageRow(filename, label, widthPct = 1.0) {
  const imgPath = path.join(BASE, filename);
  if (!fs.existsSync(imgPath)) {
    console.warn(`  WARNING: missing image ${filename}`);
    return [body(`[Image: ${label}]`)];
  }
  const data = fs.readFileSync(imgPath);
  const targetW = Math.round(CONTENT_W * widthPct);
  
  // Get native dimensions from filename pattern
  const dims = {
    "diag-01-system-architecture.png": [2000, 1520],
    "diag-02-request-lifecycle.png":   [1600, 1500],
    "diag-03-api-groups.png":           [2200, 2120],
    "diag-04-exception-hierarchy.png":  [1400, 1120],
    "diag-05-configuration-flow.png":   [1800, 1300],
    "ss-01-connection.png":             [1500, 870],
    "ss-02-query.png":                  [1500, 942],
    "ss-03-monitor.png":                [1500, 867],
    "ss-04-rbac.png":                   [2000, 996],
    "ss-05-links.png":                  [1500, 540],
    "ss-06-cluster.png":                [1500, 696],
    "ss-07-cli.png":                    [1500, 990],
  };
  const [nativeW, nativeH] = dims[filename] || [1500, 900];
  const targetH = Math.round(targetW * (nativeH / nativeW));
  
  // Convert DXA to EMU (1 DXA = 635 EMU)
  const emuW = targetW * 635;
  const emuH = targetH * 635;
  
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 60 },
      children: [new ImageRun({ data, transformation: { width: emuW / 9144, height: emuH / 9144 }, type: "png" })]
    }),
    caption(label)
  ];
}

// ── Header table (two-column using tabs) ─────────────────────────────────────
function makeHeader() {
  return new Header({
    children: [
      new Paragraph({
        spacing: { before: 0, after: 80 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: MID_BLUE, space: 4 } },
        tabStops: [{ type: "right", position: CONTENT_W }],
        children: [
          new TextRun({ text: "cb-analytics", font: "Arial", size: 18, bold: true, color: DARK_BLUE }),
          new TextRun({ text: " · Couchbase Enterprise Analytics SDK", font: "Arial", size: 18, color: GRAY_MID }),
          new TextRun({ text: "\t", font: "Arial", size: 18 }),
          new TextRun({ text: "Copyright © 2026 Chris Ahrendt", font: "Arial", size: 18, color: GRAY_MID }),
        ]
      })
    ]
  });
}

function makeFooter() {
  return new Footer({
    children: [
      new Paragraph({
        spacing: { before: 80, after: 0 },
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: MID_BLUE, space: 4 } },
        tabStops: [{ type: "right", position: CONTENT_W }],
        children: [
          new TextRun({ text: "MIT License — Private & Confidential", font: "Arial", size: 18, color: GRAY_MID }),
          new TextRun({ text: "\t", font: "Arial", size: 18 }),
          new TextRun({ text: "Page ", font: "Arial", size: 18, color: GRAY_MID }),
          new SimpleField("PAGE"),
        ]
      })
    ]
  });
}

// ── Table builder ─────────────────────────────────────────────────────────────
function dataTable(headers, rows, colWidths) {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  
  const makeCell = (text, isHeader, w, bold = false, color = null) => new TableCell({
    borders: border(),
    width: { size: w, type: WidthType.DXA },
    shading: { fill: isHeader ? TABLE_HEAD : (color || TABLE_ROW1), type: ShadingType.CLEAR },
    margins: { top: 100, bottom: 100, left: 160, right: 160 },
    children: [new Paragraph({
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ text: String(text), font: "Arial", size: isHeader ? 20 : 20, bold: isHeader || bold, color: isHeader ? WHITE : GRAY_DARK })]
    })]
  });

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => makeCell(h, true, colWidths[i]))
  });

  const dataRows = rows.map((row, ri) => new TableRow({
    children: row.map((cell, ci) => makeCell(cell, false, colWidths[ci], false, ri % 2 === 1 ? TABLE_ROW2 : TABLE_ROW1))
  }));

  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows]
  });
}

// =============================================================================
// DOCUMENT SECTIONS
// =============================================================================

function coverSection() {
  return [
    spacer(2880),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "cb-analytics", font: "Arial", size: 72, bold: true, color: DARK_BLUE })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 120 },
      children: [new TextRun({ text: "Python SDK · CLI · Terminal UI", font: "Arial", size: 32, color: MID_BLUE })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 240 },
      children: [new TextRun({ text: "Couchbase Enterprise Analytics REST API", font: "Arial", size: 28, color: GRAY_MID, italics: true })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 0 },
      border: { top: { style: BorderStyle.SINGLE, size: 8, color: ACCENT }, bottom: { style: BorderStyle.NONE, size: 0, color: WHITE } },
      children: []
    }),
    spacer(480),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Architecture · Implementation Guide · Screenshots", font: "Arial", size: 24, color: GRAY_MID })]
    }),
    spacer(2400),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 80 },
      children: [new TextRun({ text: "Copyright © 2026 Chris Ahrendt", font: "Arial", size: 24, bold: true, color: DARK_BLUE })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "MIT License  ·  Version 1.0.0  ·  May 2026", font: "Arial", size: 22, color: GRAY_MID })]
    }),
    pageBreak(),
  ];
}

function tocSection() {
  return [
    h1("Table of Contents"),
    new TableOfContents("Contents", {
      hyperlink: true,
      headingStyleRange: "1-3",
      stylesWithLevels: [
        { styleName: "Heading1", level: 1 },
        { styleName: "Heading2", level: 2 },
        { styleName: "Heading3", level: 3 },
      ]
    }),
    pageBreak(),
  ];
}

// ── Section 1: Executive Summary ──────────────────────────────────────────────
function executiveSummary() {
  return [
    h1("1. Executive Summary"),
    body("cb-analytics is a complete, production-ready Python implementation of the Couchbase Enterprise Analytics REST API. It provides a typed SDK, command-line interface, and an interactive Terminal UI, giving developers and operators full programmatic access to every documented Analytics endpoint."),
    spacer(120),
    callout("Key Facts",
      "142 unit tests · 8 API group classes · 60+ Pydantic v2 models · MIT License · Python 3.11+",
      DARK_BLUE, LIGHT_BLUE),
    spacer(120),
    h2("1.1 What Is Covered"),
    body("Every endpoint documented at https://docs.couchbase.com/enterprise-analytics/current/reference/rest-intro.html is implemented, including:"),
    bullet("Cluster initialization, node management, rebalance, failover (hard and graceful), auto-failover configuration"),
    bullet("Analytics SQL++ query execution with scan consistency, named/positional parameters, timeout, and read-only mode"),
    bullet("Analytics Admin: active/completed request monitoring, service and node restart, ingestion status"),
    bullet("Analytics Config: service-level and node-specific parameter management"),
    bullet("Analytics Links: full CRUD for Couchbase, S3, Azure Blob, and GCS links"),
    bullet("Security and RBAC: users, groups, roles, LDAP, SAML, saslauthd, password policy, audit, TLS certificates, system secrets"),
    bullet("Server Group Awareness: create, rename, update membership, delete groups"),
    bullet("Statistics, logging, events, and diagnostics"),
    spacer(160),
    h2("1.2 Technology Stack"),
    dataTable(
      ["Component", "Technology", "Purpose"],
      [
        ["HTTP Client",     "httpx (async)",       "Non-blocking I/O for all API calls"],
        ["Retry Logic",     "tenacity",            "Exponential backoff for transient errors"],
        ["Data Validation", "Pydantic v2",         "60+ typed request/response models"],
        ["Configuration",   "pydantic-settings",   "CB_ANALYTICS_* environment variables"],
        ["Terminal UI",     "Textual",             "6-panel keyboard-driven interface"],
        ["CLI",             "Typer + Rich",        "Command-line with formatted output"],
        ["Testing",         "pytest + respx",      "142 mocked unit tests, no live cluster"],
        ["CI/CD",           "GitHub Actions",      "Lint → type-check → unit → integration"],
      ],
      [3200, 3000, 3880]
    ),
    pageBreak(),
  ];
}

// ── Section 2: Architecture ───────────────────────────────────────────────────
function architectureSection() {
  return [
    h1("2. Architecture"),
    h2("2.1 System Architecture"),
    body("The cb-analytics SDK is organized in three layers: the user interface layer (TUI and CLI), the SDK core layer (client facade, HTTP client, models, and exceptions), and the API layer which maps directly to Couchbase's REST endpoints."),
    spacer(80),
    ...imageRow("diag-01-system-architecture.png", "Figure 1 – System Architecture Overview", 1.0),

    h2("2.2 Request Lifecycle"),
    body("Every API call follows the same lifecycle: the caller passes a Pydantic model to an API group class, which builds the request payload and delegates to HttpClient. HttpClient handles authentication, routing to the correct base URL (management port 8091 or analytics port 8095), retry logic, and response parsing. Any errors in the response body are surfaced as typed exceptions."),
    spacer(80),
    ...imageRow("diag-02-request-lifecycle.png", "Figure 2 – Request Lifecycle (9-step annotated flow)", 0.9),

    h2("2.3 API Groups and Endpoint Coverage"),
    body("The SDK exposes eight API group classes, each covering a logical area of the Couchbase REST API. The diagram below maps every implemented endpoint to its group class."),
    spacer(80),
    ...imageRow("diag-03-api-groups.png", "Figure 3 – Complete API Group and Endpoint Map", 1.0),

    h2("2.4 Exception Hierarchy"),
    body("All SDK exceptions derive from AnalyticsError, enabling callers to catch all SDK errors with a single except clause. The hierarchy distinguishes retryable errors (ConnectionError, ServerError) from non-retryable ones, and provides structured query error detail including error code, SQL++ line and column numbers."),
    spacer(80),
    ...imageRow("diag-04-exception-hierarchy.png", "Figure 4 – Exception Hierarchy and Retry Policy", 0.85),

    h2("2.5 Configuration Architecture"),
    body("Configuration is loaded in priority order: constructor keyword arguments override environment variables, which override .env file values, which override defaults. The AnalyticsClientConfig class (built on pydantic-settings) validates all values on instantiation and exposes computed properties for the management and analytics base URLs."),
    spacer(80),
    ...imageRow("diag-05-configuration-flow.png", "Figure 5 – Configuration Sources and Priority Order", 0.9),
    pageBreak(),
  ];
}

// ── Section 3: GUI Screenshots ────────────────────────────────────────────────
function screenshotsSection() {
  return [
    h1("3. User Interface"),
    body("The cb-analytics-gui command launches a full Terminal User Interface built with Textual. It provides six panels accessible via function keys F1–F6, plus a connection screen for entering cluster credentials. All panels support keyboard navigation and live data refresh."),

    h2("3.1 Connection Screen"),
    body("The connection screen appears on startup and reads default values from CB_ANALYTICS_* environment variables. The user can override any field before connecting."),
    spacer(80),
    ...imageRow("ss-01-connection.png", "Figure 6 – Connection Screen (startup with credential entry)", 0.85),

    h2("3.2 Query Tab [F1]"),
    body("The Query tab provides a SQL++ editor with syntax highlighting, a scan consistency selector, optional timeout field, and a results table. After execution, the status bar shows elapsed time, execution time, row count, and result size in bytes."),
    spacer(80),
    ...imageRow("ss-02-query.png", "Figure 7 – Query Tab (SQL++ editor with results table and metrics)", 0.9),

    h2("3.3 Monitor Tab [F2]"),
    body("The Monitor tab shows the current service status (ACTIVE/INACTIVE), ingestion link count, and authorized node list. The active requests table refreshes on demand and shows context ID, elapsed time, state, and a truncated statement preview. Completed requests are listed below."),
    spacer(80),
    ...imageRow("ss-03-monitor.png", "Figure 8 – Monitor Tab (service status, active and completed queries)", 0.9),

    h2("3.4 RBAC Tab [F4]"),
    body("The RBAC tab lists all users with their domain, display name, assigned roles, and group memberships. Below the user table, all defined groups are shown with their descriptions, assigned roles, and optional LDAP group references."),
    spacer(80),
    ...imageRow("ss-04-rbac.png", "Figure 9 – RBAC Tab (users, groups, roles, and LDAP references)", 0.9),

    h2("3.5 Links Tab [F5]"),
    body("The Links tab lists all Analytics links — local Couchbase, remote Couchbase, S3, Azure Blob, and GCS — with their type, dataverse, active dataset count, and connection status."),
    spacer(80),
    ...imageRow("ss-05-links.png", "Figure 10 – Links Tab (Analytics data source links)", 0.85),

    h2("3.6 Cluster Tab [F6]"),
    body("The Cluster tab shows all cluster nodes with their hostname, health status, and active services. Below, server groups are listed with their node count. Active cluster tasks (rebalance, index build, etc.) are shown at the bottom."),
    spacer(80),
    ...imageRow("ss-06-cluster.png", "Figure 11 – Cluster Tab (nodes, server groups, active tasks)", 0.85),

    h2("3.7 CLI Output"),
    body("The cb-analytics CLI provides formatted table output for all major operations: query execution, admin status, link management, RBAC user listing, and cluster inspection."),
    spacer(80),
    ...imageRow("ss-07-cli.png", "Figure 12 – CLI Output (query results, admin status, links, users)", 0.85),
    pageBreak(),
  ];
}

// ── Section 4: Implementation Guide ──────────────────────────────────────────
function implementationGuide() {
  return [
    h1("4. Implementation Guide"),

    // 4.1 Installation
    h2("4.1 Installation"),
    body("cb-analytics requires Python 3.11 or later. Install from PyPI or from source:"),
    spacer(60),
    code("# Production install"),
    code("pip install cb-analytics"),
    code(""),
    code("# With development tools (testing, linting, type-checking)"),
    code('pip install "cb-analytics[dev]"'),
    code(""),
    code("# From source"),
    code("git clone https://github.com/cahrendt/cb-analytics.git"),
    code("cd cb-analytics"),
    code('pip install -e ".[dev]"'),
    spacer(120),
    body("The following packages are installed automatically as dependencies:"),
    dataTable(
      ["Package", "Version", "Purpose"],
      [
        ["httpx",           ">=0.27", "Async HTTP client"],
        ["pydantic",        ">=2.7",  "Data validation and models"],
        ["pydantic-settings",">=2.3", "Environment-based configuration"],
        ["tenacity",        ">=8.3",  "Retry with exponential backoff"],
        ["structlog",       ">=24.1", "Structured logging"],
        ["textual",         ">=0.61", "Terminal UI framework"],
        ["typer",           ">=0.12", "CLI framework"],
        ["rich",            ">=13.7", "Formatted terminal output"],
        ["python-dotenv",   ">=1.0",  ".env file support"],
        ["prometheus-client",">=0.20","Metrics exposition"],
      ],
      [2800, 1400, 5880]
    ),

    // 4.2 Configuration
    pageBreak(),
    h2("4.2 Configuration"),
    body("All configuration is read from environment variables with the CB_ANALYTICS_ prefix, a .env file in the working directory, or passed directly as constructor keyword arguments. Constructor arguments always take the highest priority."),
    spacer(80),
    dataTable(
      ["Environment Variable", "Default", "Description"],
      [
        ["CB_ANALYTICS_HOST",             "localhost",    "Cluster hostname or IP address"],
        ["CB_ANALYTICS_MGMT_PORT",        "8091",         "Management API port (18091 for TLS)"],
        ["CB_ANALYTICS_ANALYTICS_PORT",   "8095",         "Analytics API port (18095 for TLS)"],
        ["CB_ANALYTICS_USERNAME",         "Administrator","RBAC username"],
        ["CB_ANALYTICS_PASSWORD",         "password",     "RBAC password — use a secrets manager in production"],
        ["CB_ANALYTICS_TLS",              "false",        "Enable HTTPS (auto-selects TLS ports)"],
        ["CB_ANALYTICS_VERIFY_SSL",       "true",         "Verify TLS certificates (false for self-signed)"],
        ["CB_ANALYTICS_TIMEOUT_SECONDS",  "60.0",         "Per-request timeout in seconds"],
        ["CB_ANALYTICS_MAX_RETRIES",      "3",            "Retry attempts for transient errors"],
      ],
      [3800, 1680, 4600]
    ),
    spacer(120),
    body("Example .env file:"),
    code("CB_ANALYTICS_HOST=my-cluster.internal"),
    code("CB_ANALYTICS_USERNAME=analytics_user"),
    code("CB_ANALYTICS_PASSWORD=SecretPass123!"),
    code("CB_ANALYTICS_TLS=false"),
    code("CB_ANALYTICS_TIMEOUT_SECONDS=120.0"),

    // 4.3 Python SDK
    h2("4.3 Python SDK Usage"),
    h3("4.3.1 Basic Connection"),
    body("Always use AnalyticsClient as an async context manager. This ensures HTTP connections are properly closed on exit, even if an exception is raised."),
    code("import asyncio"),
    code("from cb_analytics import AnalyticsClient, AnalyticsClientConfig"),
    code(""),
    code("async def main():"),
    code("    config = AnalyticsClientConfig("),
    code('        host="my-cluster.internal",'),
    code('        username="Administrator",'),
    code('        password="password",'),
    code("    )"),
    code("    async with AnalyticsClient(config) as client:"),
    code("        ok = await client.ping()"),
    code('        print(f"Connected: {ok}")'),
    code(""),
    code("asyncio.run(main())"),
    spacer(80),
    callout("Tip",
      "If CB_ANALYTICS_* environment variables are set, you can call AnalyticsClient() with no arguments and the config is loaded automatically.",
      MID_BLUE, LIGHT_BLUE),

    h3("4.3.2 Executing SQL++"),
    body("The analytics.execute() method accepts an AnalyticsQueryRequest model and returns an AnalyticsQueryResponse with typed results, metrics, and warnings."),
    code("from cb_analytics.models import AnalyticsQueryRequest, ScanConsistency"),
    code(""),
    code("result = await client.analytics.execute("),
    code("    AnalyticsQueryRequest("),
    code('        statement="""'),
    code("            SELECT a.airlinename, COUNT(r.id) AS routes"),
    code("            FROM `Default`.airline a"),
    code("            JOIN `Default`.route r ON r.airlineid = a.id"),
    code("            GROUP BY a.airlinename ORDER BY routes DESC LIMIT 10"),
    code('        """,'),
    code("        scan_consistency=ScanConsistency.REQUEST_PLUS,"),
    code('        timeout="30s",'),
    code("    )"),
    code(")"),
    code("for row in result.results:"),
    code("    print(row['airlinename'], row['routes'])"),
    code("print(f'Elapsed: {result.metrics.elapsedTime}')"),

    h3("4.3.3 Parameterized Queries"),
    body("Use positional parameters ($1, $2, ...) or named parameters ($name) to avoid SQL injection risks and improve plan caching."),
    code("# Positional parameters"),
    code("result = await client.analytics.execute("),
    code("    AnalyticsQueryRequest("),
    code('        statement="SELECT * FROM airline WHERE id = $1",'),
    code("        args=[42],"),
    code("    )"),
    code(")"),
    code(""),
    code("# Named parameters"),
    code("result = await client.analytics.execute("),
    code("    AnalyticsQueryRequest("),
    code('        statement="SELECT * FROM airline WHERE callsign = $callsign",'),
    code('        named_args={"callsign": "UAL"},'),
    code("    )"),
    code(")"),

    h3("4.3.4 Error Handling"),
    body("Handle specific exception types to take different recovery actions. AnalyticsConnectionError and AnalyticsServerError are retried automatically by tenacity, so they will only be raised after all retry attempts are exhausted."),
    code("from cb_analytics.exceptions import ("),
    code("    AnalyticsQueryError,     # SQL++ compilation or runtime error"),
    code("    AnalyticsAuthError,      # 401 or 403"),
    code("    AnalyticsNotFoundError,  # 404"),
    code("    AnalyticsRequestError,   # 400 or 409"),
    code("    AnalyticsError,          # base class — catches everything"),
    code(")"),
    code(""),
    code("try:"),
    code('    result = await client.analytics.execute(AnalyticsQueryRequest(statement="BAD SQL"))'),
    code("except AnalyticsQueryError as e:"),
    code('    print(f"SQL error [{e.code}] at line {e.line}: {e}")'),
    code("except AnalyticsAuthError:"),
    code('    print("Check credentials and RBAC roles")'),
    code("except AnalyticsError as e:"),
    code('    print(f"SDK error: {e}")'),

    h3("4.3.5 Admin Operations"),
    body("Monitor running queries, cancel long-running operations, and check service health through the admin API group."),
    code("# List active queries"),
    code("active = await client.admin.get_active_requests()"),
    code("for req in active:"),
    code("    print(req.clientContextID, req.elapsedTime, req.state)"),
    code(""),
    code("# Cancel a specific query"),
    code('await client.admin.cancel_request("ctx-abc-123")'),
    code(""),
    code("# Check service status"),
    code("status = await client.admin.get_service_status()"),
    code('print(f"Analytics state: {status.state}")'),
    code(""),
    code("# Check ingestion status"),
    code("ingestion = await client.admin.get_ingestion_status()"),
    code('print(f"Links: {len(ingestion.links)}")'),

    h3("4.3.6 Configuration Management"),
    body("Read and update Analytics service configuration parameters. Only fields explicitly set (non-None) are sent in PUT requests."),
    code("from cb_analytics.models import ServiceConfig"),
    code(""),
    code("# View current config"),
    code("cfg = await client.config.get_service_config()"),
    code('print(f"Result TTL: {cfg.resultTtl}s")'),
    code('print(f"Memory budget: {cfg.activeMemoryGlobalBudget} bytes")'),
    code(""),
    code("# Update a parameter"),
    code("updated = await client.config.update_service_config("),
    code("    ServiceConfig(resultTtl=7200)  # only this field is sent"),
    code(")"),

    h3("4.3.7 Analytics Links"),
    body("Manage data ingestion links. Supported types are couchbase (local or remote cluster DCP), s3, azureblob, and gcs."),
    code("# List all links"),
    code("links = await client.links.get_all_links()"),
    code(""),
    code("# Create an S3 link"),
    code("await client.links.create_link("),
    code('    name="myS3Link",'),
    code('    dataverse="Default",'),
    code("    config={"),
    code('        "type": "s3",'),
    code('        "region": "us-east-1",'),
    code('        "accessKeyId": "AKIAIOSFODNN7EXAMPLE",'),
    code('        "secretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",'),
    code("    },"),
    code(")"),
    code(""),
    code("# Delete a link"),
    code('await client.links.delete_link("myS3Link")'),

    h3("4.3.8 RBAC and Security"),
    body("Create and manage users, groups, and their role assignments. Changes take effect immediately."),
    code("from cb_analytics.models import RbacDomain, UserUpsertRequest, GroupUpsertRequest"),
    code(""),
    code("# Create a user"),
    code("await client.security.upsert_user("),
    code("    domain=RbacDomain.LOCAL,"),
    code('    username="alice",'),
    code("    request=UserUpsertRequest("),
    code('        password="SecurePass123!",'),
    code('        roles="analytics_reader[*]",'),
    code('        name="Alice Smith",'),
    code("    ),"),
    code(")"),
    code(""),
    code("# Create a group"),
    code("await client.security.upsert_group("),
    code('    groupname="analytics-team",'),
    code("    request=GroupUpsertRequest("),
    code('        description="Analytics read-only users",'),
    code('        roles="analytics_reader[*]",'),
    code("    ),"),
    code(")"),
    code(""),
    code("# Check permissions"),
    code("from cb_analytics.models import PermissionCheckRequest"),
    code("result = await client.security.check_permissions("),
    code("    PermissionCheckRequest(permissions='cluster.analytics!read')"),
    code(")"),

    // 4.4 CLI
    pageBreak(),
    h2("4.4 CLI Reference"),
    body("The cb-analytics command-line interface provides formatted table output for all major operations. Global options (--host, --port, --username, --password) can be set via environment variables or passed explicitly."),
    spacer(80),
    dataTable(
      ["Command", "Description"],
      [
        ["cb-analytics query execute \"SQL\"",  "Execute SQL++ and display results as table"],
        ["cb-analytics query execute \"SQL\" --consistency request_plus", "Execute with request-plus scan consistency"],
        ["cb-analytics query explain \"SQL\"",  "Show query execution plan JSON"],
        ["cb-analytics admin status",            "Show Analytics service status"],
        ["cb-analytics admin active-requests",   "List currently running queries"],
        ["cb-analytics admin ingestion",         "Show per-link ingestion status"],
        ["cb-analytics config get-service",      "Display service-level configuration"],
        ["cb-analytics config set resultTtl 7200", "Update a configuration parameter"],
        ["cb-analytics links list",             "List all Analytics links"],
        ["cb-analytics links list --type s3",   "Filter links by type"],
        ["cb-analytics security users",         "List all RBAC users and their roles"],
        ["cb-analytics security roles",         "List all available roles"],
        ["cb-analytics cluster info",           "Show cluster nodes and memory quotas"],
        ["cb-analytics cluster tasks",          "List active cluster tasks"],
        ["cb-analytics cluster ping",           "Check connectivity (exit 0 = success)"],
        ["cb-analytics-gui",                    "Launch the interactive Terminal UI"],
      ],
      [4680, 5400]
    ),

    // 4.5 TUI
    h2("4.5 TUI Key Bindings"),
    dataTable(
      ["Key", "Action"],
      [
        ["F1",     "Switch to Query tab (SQL++ editor with results table)"],
        ["F2",     "Switch to Monitor tab (active queries, service status)"],
        ["F3",     "Switch to Config tab (service/node configuration viewer)"],
        ["F4",     "Switch to RBAC tab (users and group management)"],
        ["F5",     "Switch to Links tab (Analytics link overview)"],
        ["F6",     "Switch to Cluster tab (nodes, server groups, tasks)"],
        ["Ctrl+R", "Refresh the current panel"],
        ["Ctrl+Q", "Quit the application"],
        ["Escape", "Go back / close a modal"],
      ],
      [1440, 8640]
    ),

    // 4.6 Testing
    pageBreak(),
    h2("4.6 Running Tests"),
    body("The test suite uses pytest with respx for HTTP mocking. Unit tests require no live cluster and run in under one second. Integration tests skip automatically unless CB_ANALYTICS_HOST is set."),
    spacer(80),
    code("# Unit tests only — no Couchbase required (142 tests, ~0.8s)"),
    code("pytest tests/unit/ -v"),
    code(""),
    code("# With coverage report"),
    code("pytest tests/unit/ --cov=cb_analytics --cov-report=html"),
    code("open htmlcov/index.html"),
    code(""),
    code("# Integration tests — requires a running Couchbase cluster"),
    code("docker-compose up -d"),
    code("CB_ANALYTICS_HOST=localhost pytest tests/integration/ -v"),
    code(""),
    code("# All tests"),
    code("pytest"),
    spacer(120),
    body("Test file coverage:"),
    dataTable(
      ["Test File", "Tests", "Coverage Area"],
      [
        ["test_cluster_api.py",               "31", "All ClusterAPI methods and error handling"],
        ["test_analytics_api.py",             "30", "Service, Admin, Config, Settings, Links APIs"],
        ["test_security_api.py",              "28", "RBAC, certs, LDAP, SAML, audit, secrets"],
        ["test_server_groups_and_models.py",  "22", "ServerGroups, Pydantic models, exceptions, config"],
        ["test_http_client_and_edge_cases.py","31", "HTTP status mapping, retry, auth, content types"],
        ["test_integration.py",               "24", "Live cluster end-to-end (auto-skip)"],
      ],
      [4200, 1000, 4880]
    ),

    // 4.7 Deployment
    h2("4.7 Deployment Guide"),
    h3("4.7.1 Docker Compose (Local Development)"),
    code("# Start Couchbase with Analytics service"),
    code("docker-compose up -d"),
    code(""),
    code("# Wait for initialization, then run integration tests"),
    code("CB_ANALYTICS_HOST=localhost \\"),
    code("CB_ANALYTICS_PASSWORD=password \\"),
    code("    pytest tests/integration/ -v"),
    spacer(80),

    h3("4.7.2 Production Security"),
    body("For production deployments, observe the following security practices:"),
    numbered("Never hard-code credentials. Use environment variables injected by your secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, etc.)."),
    numbered("Enable TLS: set CB_ANALYTICS_TLS=true and use ports 18091 (management) and 18095 (analytics)."),
    numbered("Set CB_ANALYTICS_VERIFY_SSL=true (the default). For internal CAs, load the certificate into the OS trust store."),
    numbered("Create a dedicated RBAC user with the minimum required roles. For read-only query access, analytics_reader is sufficient."),
    numbered("Set CB_ANALYTICS_TIMEOUT_SECONDS to match your longest expected query. The default of 60 seconds may be too short for large aggregations."),
    numbered("Set CB_ANALYTICS_MAX_RETRIES=3 (default) to tolerate transient network hiccups without overwhelming the cluster."),
    spacer(80),

    h3("4.7.3 Minimum RBAC Permissions"),
    dataTable(
      ["Operation", "Required Role"],
      [
        ["Execute SQL++ queries",        "analytics_reader  or  analytics_select"],
        ["Execute DDL (CREATE/DROP)",    "analytics_admin"],
        ["Manage links",                 "analytics_admin"],
        ["Restart Analytics service",    "Full Admin  or  Cluster Admin"],
        ["View/edit RBAC users",         "Full Admin  or  Security Admin"],
        ["Read cluster configuration",   "Full Admin  or  Read-Only Admin"],
        ["Modify cluster configuration", "Full Admin"],
      ],
      [4800, 5280]
    ),
    spacer(80),

    h3("4.7.4 TLS Configuration"),
    body("To connect to a TLS-enabled cluster:"),
    code("# .env file for TLS cluster"),
    code("CB_ANALYTICS_HOST=my-cluster.company.com"),
    code("CB_ANALYTICS_TLS=true"),
    code("CB_ANALYTICS_VERIFY_SSL=true"),
    code("CB_ANALYTICS_MGMT_PORT=18091"),
    code("CB_ANALYTICS_ANALYTICS_PORT=18095"),
    code(""),
    code("# For self-signed certificates in development:"),
    code("CB_ANALYTICS_VERIFY_SSL=false"),
    spacer(80),

    h3("4.7.5 CI/CD Integration"),
    body("The included GitHub Actions workflow runs on every push and pull request:"),
    numbered("Lint with ruff"),
    numbered("Type-check with mypy"),
    numbered("Unit tests on Python 3.11 and 3.12"),
    numbered("Integration tests against a real Couchbase container"),
    numbered("Package build validation"),
    spacer(80),
    code("# Run the same checks locally"),
    code("ruff check src/ tests/"),
    code("mypy src/cb_analytics/"),
    code("pytest tests/unit/ --cov=cb_analytics --cov-fail-under=90"),
    pageBreak(),
  ];
}

// ── Section 5: API Reference ──────────────────────────────────────────────────
function apiReferenceSection() {
  return [
    h1("5. API Reference Summary"),
    body("Complete documentation is available in the source code docstrings. Each method includes the HTTP method, URI, and a description. The tables below summarize the most commonly used methods."),

    h2("5.1 Analytics Service API (client.analytics)"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["execute()",          "POST", "/api/v1/request",        "Execute SQL++ statement"],
        ["execute_readonly()", "GET",  "/api/v1/request",        "Read-only SQL++ via GET"],
      ],
      [2500, 800, 3200, 3580]
    ),

    h2("5.2 Analytics Admin API (client.admin)"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["get_active_requests()",    "GET",    "/api/v1/active_requests",    "Currently running queries"],
        ["cancel_request(id)",       "DELETE", "/api/v1/active_requests",    "Cancel by clientContextID"],
        ["get_completed_requests()", "GET",    "/api/v1/completed_requests", "Recent query history"],
        ["get_service_status()",     "GET",    "/api/v1/status/service",     "Service state and nodes"],
        ["restart_service()",        "POST",   "/api/v1/service/restart",    "Restart all Analytics nodes"],
        ["restart_node()",           "POST",   "/api/v1/node/restart",       "Restart this node only"],
        ["get_ingestion_status()",   "GET",    "/api/v1/status/ingestion",   "Per-link ingestion status"],
      ],
      [2500, 900, 3200, 3480]
    ),

    h2("5.3 Analytics Config API (client.config)"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["get_service_config()",       "GET", "/api/v1/config/service", "Service-level parameters"],
        ["update_service_config(cfg)", "PUT", "/api/v1/config/service", "Modify service parameters"],
        ["get_node_config()",          "GET", "/api/v1/config/node",    "Node-specific parameters"],
        ["update_node_config(cfg)",    "PUT", "/api/v1/config/node",    "Modify node parameters"],
      ],
      [2700, 800, 3000, 3580]
    ),

    h2("5.4 Analytics Links API (client.links)"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["create_link(name, dv, cfg)", "POST",   "/api/v1/link/{name}", "Create Couchbase/S3/Azure/GCS link"],
        ["get_link(name)",             "GET",    "/api/v1/link/{name}", "Get link metadata"],
        ["update_link(name, cfg)",     "PUT",    "/api/v1/link/{name}", "Update link configuration"],
        ["delete_link(name)",          "DELETE", "/api/v1/link/{name}", "Delete a link"],
        ["get_all_links()",            "GET",    "/api/v1/link",        "List all links (with filters)"],
      ],
      [2700, 900, 2700, 3780]
    ),

    h2("5.5 Security API (client.security) — Selected Methods"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["list_users()",                    "GET",    "/settings/rbac/users",              "All users"],
        ["upsert_user(domain, user, req)",  "PUT",    "/settings/rbac/users/{domain}/{u}", "Create/replace user"],
        ["delete_user(domain, username)",   "DELETE", "/settings/rbac/users/{domain}/{u}", "Delete user"],
        ["list_groups()",                   "GET",    "/settings/rbac/groups",             "All groups"],
        ["upsert_group(name, req)",         "PUT",    "/settings/rbac/groups/{name}",      "Create/replace group"],
        ["check_permissions(req)",          "POST",   "/pools/default/checkPermissions",   "Verify permissions"],
        ["configure_ldap(settings)",        "POST",   "/settings/ldap",                    "Configure LDAP auth"],
        ["get_audit_settings()",            "GET",    "/settings/audit",                   "Audit configuration"],
        ["get_trusted_cas()",               "GET",    "/node/controller/loadTrustedCAs",   "Trusted root CAs"],
      ],
      [2500, 900, 3400, 3280]
    ),

    h2("5.6 Cluster API (client.cluster) — Selected Methods"),
    dataTable(
      ["Method", "HTTP", "Endpoint", "Description"],
      [
        ["initialize_cluster(req)",        "POST", "/clusterInit",                     "Initialize new cluster"],
        ["get_cluster_details()",          "GET",  "/pools/default",                   "Cluster overview"],
        ["get_cluster_tasks()",            "GET",  "/pools/default/tasks",             "Running tasks"],
        ["rebalance(req)",                 "POST", "/controller/rebalance",            "Start rebalance"],
        ["get_rebalance_progress()",       "GET",  "/pools/default/rebalanceProgress", "Rebalance progress"],
        ["hard_failover(req)",             "POST", "/controller/failOver",             "Hard failover"],
        ["configure_auto_failover(cfg)",   "POST", "/settings/autoFailover",           "Auto-failover config"],
        ["get_statistic(metric)",          "GET",  "/pools/default/stats/range/{m}",   "Single metric"],
        ["start_log_collection(req)",      "POST", "/controller/startLogsCollection",  "Collect logs"],
      ],
      [2700, 900, 3400, 3080]
    ),
    pageBreak(),
  ];
}

// ── Section 6: Troubleshooting ────────────────────────────────────────────────
function troubleshootingSection() {
  return [
    h1("6. Troubleshooting"),

    h2("6.1 Common Errors"),
    dataTable(
      ["Error", "Cause", "Resolution"],
      [
        ["AnalyticsConnectionError: Connection refused",   "Wrong host/port or Couchbase not running",  "Verify CB_ANALYTICS_HOST and check curl http://host:8091/pools"],
        ["AnalyticsAuthError: Authentication failed",      "Wrong credentials or user lacks roles",      "Check username/password. Verify user has analytics_reader role."],
        ["AnalyticsQueryError [24000]: Syntax error",      "Invalid SQL++ statement",                   "Use cb-analytics query explain to validate the statement."],
        ["AnalyticsQueryError [24006]: Unknown dataset",   "Dataset not found in the specified dataverse","Check dataverse and dataset names are correct."],
        ["AnalyticsNotFoundError",                         "Resource URI not found (404)",              "Verify the link name, dataverse name, or user ID."],
        ["SSL certificate verification failed",            "Self-signed certificate in use",             "Set CB_ANALYTICS_VERIFY_SSL=false for dev, or load CA cert in production."],
      ],
      [2800, 2800, 4480]
    ),

    h2("6.2 Query Timeout Tuning"),
    body("If analytics queries time out, increase the client timeout and the server-side result TTL:"),
    code("# Increase client timeout"),
    code("config = AnalyticsClientConfig(timeout_seconds=120.0)"),
    code(""),
    code("# Increase server-side result TTL via config API"),
    code("await client.config.update_service_config(ServiceConfig(resultTtl=120))"),
    code(""),
    code("# Use timeout parameter per-query"),
    code('result = await client.analytics.execute(AnalyticsQueryRequest(statement="...", timeout="120s"))'),
    spacer(80),

    h2("6.3 Connection Pool Exhaustion"),
    body("If requests start failing after a period of high load, check whether queries are being cancelled properly. Long-running queries hold the underlying socket connection. Use cancel_request() to terminate any stuck queries."),
    spacer(80),

    h2("6.4 Ingestion Lag"),
    body("A high pending mutation count indicates that KV mutations are not yet visible to Analytics queries. Use request_plus scan consistency to wait for mutations to be reflected, or check the ingestion status to identify which link has the highest lag."),
    code("# Check ingestion status"),
    code("ingestion = await client.admin.get_ingestion_status()"),
    code("for link in ingestion.links:"),
    code("    print(link)"),
    spacer(80),

    pageBreak(),
  ];
}

// ── Section 7: License ────────────────────────────────────────────────────────
function licenseSection() {
  return [
    h1("7. License"),
    body("cb-analytics is released under the MIT License."),
    spacer(120),
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA },
      columnWidths: [CONTENT_W],
      rows: [new TableRow({ children: [new TableCell({
        borders: border(),
        shading: { fill: GRAY_LIGHT, type: ShadingType.CLEAR },
        margins: { top: 200, bottom: 200, left: 300, right: 300 },
        width: { size: CONTENT_W, type: WidthType.DXA },
        children: [
          new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: "MIT License", font: "Courier New", size: 22, bold: true, color: DARK_BLUE })] }),
          new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: "Copyright (c) 2026 Chris Ahrendt", font: "Courier New", size: 20, color: GRAY_DARK })] }),
          new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:", font: "Courier New", size: 20, color: GRAY_DARK })] }),
          new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.", font: "Courier New", size: 20, color: GRAY_DARK })] }),
          new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.', font: "Courier New", size: 20, color: GRAY_DARK })] }),
        ]
      })]})],
    }),
  ];
}

// =============================================================================
// BUILD DOCUMENT
// =============================================================================
async function buildDocument() {
  console.log("Building Word document...");

  const children = [
    ...coverSection(),
    ...tocSection(),
    ...executiveSummary(),
    ...architectureSection(),
    ...screenshotsSection(),
    ...implementationGuide(),
    ...apiReferenceSection(),
    ...troubleshootingSection(),
    ...licenseSection(),
  ];

  const doc = new Document({
    creator: "Chris Ahrendt",
    title: "cb-analytics — Couchbase Enterprise Analytics SDK",
    description: "Architecture, Implementation Guide, and Screenshots",
    styles: {
      default: {
        document: { run: { font: "Arial", size: 22 } }
      },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 36, bold: true, font: "Arial", color: DARK_BLUE },
          paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 }
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 28, bold: true, font: "Arial", color: MID_BLUE },
          paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 }
        },
        {
          id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 24, bold: true, font: "Arial", color: GRAY_DARK },
          paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 }
        },
      ]
    },
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [{
            level: 0, format: LevelFormat.BULLET, text: "\u2022",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }]
        },
        {
          reference: "numbers",
          levels: [{
            level: 0, format: LevelFormat.DECIMAL, text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }]
        },
      ]
    },
    sections: [{
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN }
        }
      },
      headers: { default: makeHeader() },
      footers: { default: makeFooter() },
      children
    }]
  });

  const outPath = path.join(__dirname, "..", "cb-analytics-documentation.docx");
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outPath, buffer);
  const sizeKB = Math.round(buffer.length / 1024);
  console.log(`  Written: ${outPath} (${sizeKB}KB)`);
}

buildDocument().catch(err => { console.error(err); process.exit(1); });

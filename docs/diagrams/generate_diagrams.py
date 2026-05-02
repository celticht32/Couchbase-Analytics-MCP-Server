"""Generate all architecture SVG diagrams for cb-analytics documentation."""
# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT

import os

OUT = os.path.join(os.path.dirname(__file__))

# ── Shared theme ──────────────────────────────────────────────────────────────
BG      = "#0d1117"
BG2     = "#161b22"
BG3     = "#21262d"
BORDER  = "#30363d"
ACCENT  = "#f78166"
BLUE    = "#58a6ff"
GREEN   = "#3fb950"
PURPLE  = "#d2a8ff"
AMBER   = "#e3b341"
TEAL    = "#39d353"
MUTED   = "#8b949e"
WHITE   = "#e6edf3"
FONT    = "JetBrains Mono, Consolas, monospace"
SANS    = "Inter, Segoe UI, Arial, sans-serif"

def rect(x,y,w,h,fill,stroke=BORDER,rx=8,opacity=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" rx="{rx}" opacity="{opacity}"/>'

def text(x,y,s,fill=WHITE,size=13,anchor="middle",weight="normal",family=SANS):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" font-family="{family}">{s}</text>'

def mono(x,y,s,fill=ACCENT,size=11,anchor="middle"):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-family="{FONT}">{s}</text>'

def arrow(x1,y1,x2,y2,color=BLUE,dashed=False):
    da = 'stroke-dasharray="6,4"' if dashed else ''
    return (f'<defs><marker id="ah{abs(hash((x1,y1,x2,y2)))%9999}" markerWidth="8" markerHeight="8" '
            f'refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{color}"/></marker></defs>'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" {da} '
            f'marker-end="url(#ah{abs(hash((x1,y1,x2,y2)))%9999})"/>')

def svg_wrap(w,h,content):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
<rect width="{w}" height="{h}" fill="{BG}"/>
{content}
</svg>'''

# ── Diagram 1: System Architecture ───────────────────────────────────────────
def diagram_system_architecture():
    parts = []

    # Title
    parts.append(rect(0,0,1000,50,BG2,BORDER,0))
    parts.append(text(500,31,"cb-analytics · System Architecture",WHITE,18,"middle","600",SANS))

    # User layer
    parts.append(rect(30,70,940,130,BG2,BLUE,10))
    parts.append(text(500,95,"User Interface Layer",BLUE,13,"middle","600",SANS))

    parts.append(rect(50,108,200,75,BG3,PURPLE,8))
    parts.append(text(150,132,"Textual TUI",PURPLE,12,"middle","600",SANS))
    parts.append(mono(150,150,"cb-analytics-gui",MUTED,10))
    parts.append(mono(150,165,"6 interactive panels",MUTED,10))

    parts.append(rect(270,108,200,75,BG3,PURPLE,8))
    parts.append(text(370,132,"Typer CLI",PURPLE,12,"middle","600",SANS))
    parts.append(mono(370,150,"cb-analytics <cmd>",MUTED,10))
    parts.append(mono(370,165,"query · admin · security",MUTED,10))

    parts.append(rect(490,108,220,75,BG3,PURPLE,8))
    parts.append(text(600,132,"Python SDK",PURPLE,12,"middle","600",SANS))
    parts.append(mono(600,150,"AnalyticsClient",MUTED,10))
    parts.append(mono(600,165,"async context manager",MUTED,10))

    parts.append(rect(730,108,220,75,BG3,PURPLE,8))
    parts.append(text(840,132,"Direct API",PURPLE,12,"middle","600",SANS))
    parts.append(mono(840,150,"8 API group classes",MUTED,10))
    parts.append(mono(840,165,"full type safety",MUTED,10))

    # SDK Core
    parts.append(rect(30,230,940,190,BG2,GREEN,10))
    parts.append(text(500,255,"SDK Core Layer",GREEN,13,"middle","600",SANS))

    cols = [
        (50,270,140,140,TEAL,"AnalyticsClient","client.py","Unified facade\n8 API groups"),
        (210,270,140,140,TEAL,"HttpClient","http_client.py","httpx async\ntenacity retry"),
        (370,270,140,140,AMBER,"Pydantic Models","models/","60+ request/\nresponse types"),
        (530,270,140,140,AMBER,"Exceptions","exceptions.py","Typed error\nhierarchy"),
        (690,270,140,140,BLUE,"Config","config.py","pydantic-settings\nenv-based"),
        (840,270,110,140,BLUE,"CLI / GUI","cli.py\napp.py","Typer + Textual\ninterfaces"),
    ]
    for x,y,w,h,color,title,file,desc in cols:
        parts.append(rect(x,y,w,h,BG3,color,8))
        parts.append(text(x+w//2,y+22,title,color,11,"middle","600",SANS))
        parts.append(mono(x+w//2,y+38,file,MUTED,9))
        for i,line in enumerate(desc.split("\n")):
            parts.append(text(x+w//2,y+60+i*16,line,MUTED,10))

    # API Groups
    parts.append(rect(30,450,940,130,BG2,ACCENT,10))
    parts.append(text(500,475,"API Groups",ACCENT,13,"middle","600",SANS))

    apis = [
        (50,490,"ClusterAPI","cluster.py","40+ endpoints"),
        (195,490,"AnalyticsServiceAPI","analytics.py","SQL++ exec"),
        (340,490,"AnalyticsAdminAPI","analytics.py","admin ops"),
        (485,490,"AnalyticsConfigAPI","analytics.py","config mgmt"),
        (630,490,"AnalyticsLinksAPI","analytics.py","link CRUD"),
        (775,490,"SecurityAPI","security.py","RBAC/TLS"),
    ]
    for x,y,title,file,desc in apis:
        parts.append(rect(x,y,135,80,BG3,ACCENT,6))
        parts.append(text(x+67,y+20,title,ACCENT,9,"middle","600",SANS))
        parts.append(mono(x+67,y+36,file,MUTED,8))
        parts.append(text(x+67,y+54,desc,MUTED,9))

    # Couchbase layer
    parts.append(rect(30,615,940,130,BG2,BORDER,10))
    parts.append(text(500,640,"Couchbase Enterprise Analytics Cluster",MUTED,13,"middle","600",SANS))

    parts.append(rect(50,655,430,75,BG3,BLUE,8))
    parts.append(text(265,678,"Management API  :8091",BLUE,11,"middle","600",SANS))
    parts.append(mono(265,698,"/clusterInit · /pools/* · /settings/rbac/* · /settings/ldap",MUTED,9))
    parts.append(mono(265,712,"/controller/* · /node/controller/* · /settings/audit",MUTED,9))

    parts.append(rect(510,655,440,75,BG3,GREEN,8))
    parts.append(text(730,678,"Analytics API  :8095",GREEN,11,"middle","600",SANS))
    parts.append(mono(730,698,"/api/v1/request · /api/v1/active_requests · /api/v1/link/*",MUTED,9))
    parts.append(mono(730,712,"/api/v1/config/* · /api/v1/status/* · /api/v1/service/restart",MUTED,9))

    # Arrows between layers
    parts.append(arrow(500,200,500,228,BLUE))
    parts.append(arrow(500,420,500,448,GREEN))
    parts.append(arrow(265,588,265,613,BLUE))
    parts.append(arrow(730,588,730,613,GREEN))

    return svg_wrap(1000,760,"\n".join(parts))

# ── Diagram 2: Request Lifecycle ──────────────────────────────────────────────
def diagram_request_lifecycle():
    parts = []

    parts.append(rect(0,0,800,50,BG2,BORDER,0))
    parts.append(text(400,31,"Request Lifecycle · analytics.execute()",WHITE,16,"middle","600",SANS))

    steps = [
        (BG2,PURPLE,"1  Caller","AnalyticsClient.analytics.execute(AnalyticsQueryRequest(...))","User code or CLI/TUI passes a Pydantic model"),
        (BG2,BLUE,"2  Service Layer","AnalyticsServiceAPI.execute()","Validates model, builds JSON payload, sets scan_consistency/timeout/args"),
        (BG2,TEAL,"3  HTTP Client","HttpClient.analytics_post('/api/v1/request', json=payload)","Routes to analytics_client (port 8095). Adds Basic Auth header."),
        (BG2,AMBER,"4  Retry Logic","tenacity.AsyncRetrying(stop=3, wait=exponential)","Retries on AnalyticsConnectionError or AnalyticsServerError (5xx)"),
        (BG2,GREEN,"5  httpx","httpx.AsyncClient.request('POST', path, json=payload)","Async HTTP request with configurable timeout"),
        (BG2,ACCENT,"6  Couchbase","POST /api/v1/request","AsterixDB executes SQL++, returns JSON with results, metrics, errors"),
        (BG2,BLUE,"7  Response Parse","AnalyticsQueryResponse.model_validate(raw)","Pydantic validates and types all fields (results, metrics, warnings, errors)"),
        (BG2,PURPLE,"8  Error Check","if response.errors: raise AnalyticsQueryError","Maps first error code/msg/line/column into typed exception"),
        (BG2,GREEN,"9  Return","return AnalyticsQueryResponse","Caller receives typed result with .results, .metrics, .warnings"),
    ]

    for i,(bg,color,label,code,desc) in enumerate(steps):
        y = 65 + i*75
        parts.append(rect(30,y,740,65,bg,color,8))
        # Step number badge
        parts.append(rect(40,y+8,32,32,color,color,16))
        parts.append(text(56,y+30,str(i+1),"#0d1117",14,"middle","700",SANS))
        # Labels
        parts.append(text(90,y+22,label,color,12,"start","600",SANS))
        parts.append(mono(90,y+38,code,WHITE,10,"start"))
        parts.append(text(90,y+54,desc,MUTED,10,"start","normal",SANS))
        # Arrow down (except last)
        if i < len(steps)-1:
            parts.append(f'<line x1="400" y1="{y+65}" x2="400" y2="{y+73}" stroke="{color}" stroke-width="2"/>')
            parts.append(f'<polygon points="394,{y+73} 406,{y+73} 400,{y+80}" fill="{color}"/>')

    return svg_wrap(800,750,"\n".join(parts))

# ── Diagram 3: API Groups Map ─────────────────────────────────────────────────
def diagram_api_groups():
    parts = []

    parts.append(rect(0,0,1100,50,BG2,BORDER,0))
    parts.append(text(550,31,"API Groups · Complete Endpoint Coverage",WHITE,16,"middle","600",SANS))

    groups = [
        ("ClusterAPI",BLUE,"cluster.py",60,70,[
            "POST /clusterInit","POST /nodes/self/controller/settings",
            "POST /settings/web","POST /node/controller/rename",
            "POST /pools/default","POST /node/controller/setupServices",
            "POST /controller/addNode","POST /controller/ejectNode",
            "POST /controller/rebalance","GET /pools/default/rebalanceProgress",
            "GET/POST /pools/default/retryRebalance","POST /controller/failOver",
            "POST /controller/startGracefulFailover","GET/POST /settings/autoFailover",
            "GET /pools","GET /pools/default","GET /pools/nodes",
            "GET /pools/default/nodeServices","GET /events",
            "GET/POST /pools/default/stats/range","POST /controller/startLogsCollection",
        ]),
        ("AnalyticsServiceAPI",GREEN,"analytics.py",60,530,[
            "POST /api/v1/request","GET /api/v1/request (read-only)",
        ]),
        ("AnalyticsAdminAPI",TEAL,"analytics.py",60,640,[
            "GET /api/v1/active_requests","DELETE /api/v1/active_requests",
            "GET /api/v1/completed_requests","GET /api/v1/status/service",
            "POST /api/v1/service/restart","POST /api/v1/node/restart",
            "GET /api/v1/status/ingestion",
        ]),
        ("AnalyticsConfigAPI",AMBER,"analytics.py",580,70,[
            "GET /api/v1/config/service","PUT /api/v1/config/service",
            "GET /api/v1/config/node","PUT /api/v1/config/node",
        ]),
        ("AnalyticsSettingsAPI",AMBER,"analytics.py",580,250,[
            "GET /settings/analytics","POST /settings/analytics",
        ]),
        ("AnalyticsLinksAPI",ACCENT,"analytics.py",580,360,[
            "POST /api/v1/link/{name}","GET /api/v1/link/{name}",
            "PUT /api/v1/link/{name}","DELETE /api/v1/link/{name}",
            "GET /api/v1/link (all)",
        ]),
        ("SecurityAPI",PURPLE,"security.py",580,530,[
            "GET/POST /settings/audit","GET/POST /settings/ldap",
            "GET/POST /settings/saml","GET/POST /settings/passwordPolicy",
            "GET/POST /settings/security","GET/POST/DELETE /settings/security/responseHeaders",
            "GET/PUT /settings/rbac/users","DELETE /settings/rbac/users/{domain}/{user}",
            "GET/PUT/DELETE /settings/rbac/groups","GET /settings/rbac/roles",
            "POST /pools/default/checkPermissions","GET/POST /node/controller/loadTrustedCAs",
            "DELETE /pools/default/trustedCAs/{id}","GET /pools/default/certificates",
            "POST /controller/regenerateCertificate","GET /nodes/self/secretsManagement",
            "POST /node/controller/secretsManagement","POST /node/controller/rotateDataKey",
        ]),
        ("ServerGroupsAPI",BLUE,"server_groups.py",60,860,[
            "GET /pools/default/serverGroups","POST /pools/default/serverGroups",
            "POST /pools/default/serverGroups/{uuid}/addNode",
            "PUT /pools/default/serverGroups/{uuid}",
            "PUT /pools/default/serverGroups?rev={n}","DELETE /pools/default/serverGroups/{uuid}",
        ]),
    ]

    for (name,color,file,x,y,endpoints) in groups:
        h = 30 + len(endpoints)*18 + 16
        parts.append(rect(x,y,500,h,BG2,color,8))
        parts.append(text(x+8,y+20,name,color,12,"start","700",SANS))
        parts.append(mono(x+300,y+20,file,MUTED,10,"start"))
        for i,ep in enumerate(endpoints):
            parts.append(mono(x+12,y+38+i*18,"·  "+ep,MUTED if "GET" not in ep else WHITE,9,"start"))

    return svg_wrap(1100,1060,"\n".join(parts))

# ── Diagram 4: Exception Hierarchy ───────────────────────────────────────────
def diagram_exceptions():
    parts = []

    parts.append(rect(0,0,700,50,BG2,BORDER,0))
    parts.append(text(350,31,"Exception Hierarchy",WHITE,16,"middle","600",SANS))

    # Root
    parts.append(rect(250,70,200,50,BG3,ACCENT,8))
    parts.append(text(350,100,"AnalyticsError",ACCENT,13,"middle","700",SANS))
    parts.append(text(350,114,"(base class)",MUTED,10))

    children = [
        (30,200,BLUE,"AnalyticsConnectionError","Network/timeout\nRetried automatically"),
        (180,200,ACCENT,"AnalyticsAuthError","401 / 403\nCheck credentials"),
        (330,200,AMBER,"AnalyticsNotFoundError","404 Not Found\nCheck resource name"),
        (30,330,GREEN,"AnalyticsRequestError","400 / 409\nFix the request"),
        (180,330,PURPLE,"AnalyticsServerError","5xx Server Error\nRetried automatically"),
        (330,330,TEAL,"AnalyticsQueryError","SQL++ error\ncode, line, column"),
    ]

    for x,y,color,name,desc in children:
        parts.append(rect(x,y,160,90,BG3,color,8))
        parts.append(text(x+80,y+26,name,color,10,"middle","700",SANS))
        for i,line in enumerate(desc.split("\n")):
            parts.append(text(x+80,y+46+i*16,line,MUTED,9))
        # Arrow from root
        parts.append(f'<line x1="350" y1="120" x2="{x+80}" y2="{y}" stroke="{color}" stroke-width="1" stroke-dasharray="4,3"/>')

    # Retry annotation
    parts.append(rect(30,450,340,80,BG2,GREEN,8))
    parts.append(text(200,474,"Retry Policy (tenacity)",GREEN,11,"middle","600",SANS))
    parts.append(text(200,492,"Retried: ConnectionError, ServerError",WHITE,10))
    parts.append(text(200,508,"Not retried: Auth, NotFound, Request, Query",MUTED,10))
    parts.append(text(200,524,"Backoff: exponential  ·  max_retries=3  ·  ceiling=10s",MUTED,9))

    # HTTP status mapping
    parts.append(rect(390,450,280,80,BG2,BLUE,8))
    parts.append(text(530,474,"HTTP Status Mapping",BLUE,11,"middle","600",SANS))
    for i,(code,exc) in enumerate([(401,"AuthError"),(403,"AuthError"),(404,"NotFoundError"),
                                     (400,"RequestError"),(409,"RequestError"),("5xx","ServerError")]):
        parts.append(mono(530,492+i*12,f"HTTP {code}  →  Analytics{exc}",MUTED,9))

    return svg_wrap(700,560,"\n".join(parts))

# ── Diagram 5: Configuration Flow ────────────────────────────────────────────
def diagram_config():
    parts = []

    parts.append(rect(0,0,900,50,BG2,BORDER,0))
    parts.append(text(450,31,"Configuration Sources & Resolution Order",WHITE,16,"middle","600",SANS))

    sources = [
        (50,80,PURPLE,"1. Constructor kwargs","Highest priority\nOverrides everything"),
        (280,80,BLUE,"2. Environment variables","CB_ANALYTICS_* prefix\nOS-level or .env file"),
        (510,80,GREEN,"3. .env file","python-dotenv\nloaded by pydantic-settings"),
        (740,80,MUTED,"4. Defaults","localhost:8091/:8095\nAdministrator/password"),
    ]
    for x,y,color,title,desc in sources:
        parts.append(rect(x,y,200,90,BG3,color,8))
        parts.append(text(x+100,y+24,title,color,10,"middle","700",SANS))
        for i,line in enumerate(desc.split("\n")):
            parts.append(text(x+100,y+46+i*16,line,MUTED,9))

    # Arrow flow
    for x in [252,482,712]:
        parts.append(f'<polygon points="{x-10},120 {x+10},120 {x},136" fill="{MUTED}" opacity="0.4"/>')

    # Config fields table
    parts.append(rect(50,200,800,380,BG2,BORDER,8))
    parts.append(text(450,224,"AnalyticsClientConfig Fields",WHITE,13,"middle","600",SANS))

    fields = [
        ("CB_ANALYTICS_HOST","host","str","localhost","Cluster hostname or IP address"),
        ("CB_ANALYTICS_MGMT_PORT","mgmt_port","int","8091","Management API port (18091 for TLS)"),
        ("CB_ANALYTICS_ANALYTICS_PORT","analytics_port","int","8095","Analytics API port (18095 for TLS)"),
        ("CB_ANALYTICS_USERNAME","username","str","Administrator","Couchbase RBAC username"),
        ("CB_ANALYTICS_PASSWORD","password","str","password","RBAC password (use secrets manager)"),
        ("CB_ANALYTICS_TLS","tls","bool","false","Enable HTTPS; changes URL scheme"),
        ("CB_ANALYTICS_VERIFY_SSL","verify_ssl","bool","true","Verify TLS cert (false for self-signed)"),
        ("CB_ANALYTICS_TIMEOUT_SECONDS","timeout_seconds","float","60.0","Per-request timeout in seconds"),
        ("CB_ANALYTICS_MAX_RETRIES","max_retries","int","3","Retry attempts for transient errors"),
    ]
    headers = ["Environment Variable","Attribute","Type","Default","Description"]
    col_xs = [60,280,390,450,510]
    col_ws = [210,100,55,50,330]

    # Header row
    parts.append(rect(50,234,800,24,BG3,BORDER,0))
    for i,h in enumerate(headers):
        parts.append(text(col_xs[i],250,h,BLUE,10,"start","600",SANS))

    for row_i,row in enumerate(fields):
        y = 260+row_i*33
        bg = BG3 if row_i%2==0 else BG2
        parts.append(rect(50,y,800,33,bg,BORDER,0))
        colors = [AMBER,WHITE,TEAL,GREEN,MUTED]
        for i,(val,color) in enumerate(zip(row,colors)):
            parts.append(mono(col_xs[i],y+18,str(val),color,9,"start"))

    # Computed props
    parts.append(rect(50,570,800,60,BG3,GREEN,8))
    parts.append(text(450,592,"Computed Properties",GREEN,11,"middle","600",SANS))
    parts.append(mono(200,610,"management_url  →  http[s]://host:mgmt_port",TEAL,10,"start"))
    parts.append(mono(200,624,"analytics_url   →  http[s]://host:analytics_port",TEAL,10,"start"))

    return svg_wrap(900,650,"\n".join(parts))

# ── Generate all diagrams ─────────────────────────────────────────────────────
diagrams = {
    "01-system-architecture.svg": diagram_system_architecture,
    "02-request-lifecycle.svg": diagram_request_lifecycle,
    "03-api-groups.svg": diagram_api_groups,
    "04-exception-hierarchy.svg": diagram_exceptions,
    "05-configuration-flow.svg": diagram_config,
}

for filename, fn in diagrams.items():
    path = os.path.join(OUT, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(fn())
    print(f"Generated {filename}")

print("All diagrams generated.")

"""Generate GUI screenshot SVGs simulating the Textual TUI panels."""
# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT

import os

OUT = os.path.dirname(__file__)

BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
BORDER = "#30363d"
ACCENT = "#f78166"
BLUE   = "#58a6ff"
GREEN  = "#3fb950"
PURPLE = "#d2a8ff"
AMBER  = "#e3b341"
TEAL   = "#79c0ff"
MUTED  = "#8b949e"
WHITE  = "#e6edf3"
FONT   = "JetBrains Mono, Consolas, monospace"
SANS   = "Inter, Segoe UI, Arial, sans-serif"

def rect(x,y,w,h,fill,stroke=BORDER,rx=4,opacity=1.0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="{rx}" opacity="{opacity}"/>'

def t(x,y,s,fill=WHITE,size=12,anchor="start",weight="normal",family=SANS):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" font-family="{family}">{s}</text>'

def m(x,y,s,fill=MUTED,size=11,anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-family="{FONT}">{s}</text>'

def svg(w,h,content,title="cb-analytics"):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
<rect width="{w}" height="{h}" fill="{BG}"/>
<!-- Drop shadow on window -->
<rect x="8" y="8" width="{w-16}" height="{h-16}" fill="#000" rx="10" opacity="0.5"/>
<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="{BG2}" rx="10" stroke="{BORDER}" stroke-width="1.5"/>
<!-- Title bar -->
<rect x="4" y="4" width="{w-8}" height="36" fill="{BG3}" rx="10"/>
<rect x="4" y="30" width="{w-8}" height="10" fill="{BG3}"/>
<!-- Traffic lights -->
<circle cx="24" cy="22" r="6" fill="#ff5f57"/>
<circle cx="44" cy="22" r="6" fill="#ffbd2e"/>
<circle cx="64" cy="22" r="6" fill="#28c840"/>
<!-- Window title -->
{t(w//2,26,"cb-analytics — Couchbase Enterprise Analytics",MUTED,12,"middle","normal",SANS)}
{content}
</svg>'''

def tab_bar(tabs, active, y=44):
    parts = []
    x = 4
    for tab in tabs:
        color = ACCENT if tab==active else MUTED
        bg_color = BG if tab==active else BG2
        border_b = ACCENT if tab==active else BORDER
        parts.append(rect(x,y,len(tab)*8+24,28,bg_color,BORDER,rx=0))
        if tab==active:
            parts.append(f'<rect x="{x}" y="{y+26}" width="{len(tab)*8+24}" height="2" fill="{ACCENT}"/>')
        parts.append(t(x+12,y+18,tab,color,11,"start","600" if tab==active else "normal",SANS))
        x += len(tab)*8+24
    return "\n".join(parts)

# ── Screenshot 1: Connection Screen ──────────────────────────────────────────
def screenshot_connection():
    parts = []
    # Header bar
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(t(800,60,"REST API Client",MUTED,11,"start","normal",SANS))

    # Connection panel
    parts.append(rect(250,110,500,380,BG3,BLUE,8))
    parts.append(t(500,142,"🔌  Connect to Couchbase Enterprise Analytics",BLUE,14,"middle","600",SANS))

    fields = [
        ("Host",            "localhost",         120),
        ("Management Port", "8091",              172),
        ("Analytics Port",  "8095",              224),
        ("Username",        "Administrator",     276),
        ("Password",        "••••••••",          328),
    ]
    for label,value,y in fields:
        parts.append(t(268,y,label,MUTED,11,"start","normal",SANS))
        parts.append(rect(368,y-14,360,24,BG,BORDER,4))
        color = MUTED if "•" in value else WHITE
        parts.append(m(376,y+3,value,color,11))

    # Buttons
    parts.append(rect(328,400,140,32,BLUE,BLUE,6))
    parts.append(t(398,421,"Connect",BG,12,"middle","700",SANS))
    parts.append(rect(482,400,120,32,BG3,BORDER,6))
    parts.append(t(542,421,"Quit",MUTED,12,"middle","normal",SANS))

    # Footer
    parts.append(rect(4,550,992,24,BG3,BORDER,0))
    parts.append(t(20,566,"Escape: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,580,"\n".join(parts),"Connection Screen")

# ── Screenshot 2: Query Tab ───────────────────────────────────────────────────
def screenshot_query():
    parts = []
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(tab_bar(["Query [F1]","Monitor [F2]","Config [F3]","RBAC [F4]","Links [F5]","Cluster [F6]"],"Query [F1]",y=74))

    # SQL++ editor box
    parts.append(rect(10,108,980,200,BG,BORDER,6))
    # Line numbers
    parts.append(rect(10,108,36,200,BG3,BORDER,0))
    for i in range(1,9):
        parts.append(m(22,124+i*22,str(i),BG3 if i>7 else MUTED,10,"middle"))
    # Code
    sql_lines = [
        ("-- Couchbase Enterprise Analytics SQL++ Console",MUTED),
        ("-- Example: find top airlines by route count",MUTED),
        ("",WHITE),
        ("SELECT",BLUE),
        ("    a.airlinename,  COUNT(r.id) AS route_count",WHITE),
        ("FROM `Default`.airline a",WHITE),
        ("JOIN `Default`.route r ON r.airlineid = a.id",WHITE),
        ("GROUP BY a.airlinename  ORDER BY route_count DESC  LIMIT 10;",WHITE),
    ]
    for i,(line,color) in enumerate(sql_lines):
        parts.append(m(54,124+(i+1)*22,line,color,11))

    # Cursor
    parts.append(rect(54,108+8*22,2,18,WHITE,WHITE,0))

    # Toolbar
    parts.append(rect(10,312,980,38,BG3,BORDER,0))
    parts.append(rect(16,320,80,22,BLUE,BLUE,4))
    parts.append(t(56,335,"▶  Run",BG,11,"middle","700",SANS))
    parts.append(rect(104,320,80,22,BG3,BORDER,4))
    parts.append(t(144,335,"⏹  Cancel",MUTED,11,"middle","normal",SANS))
    # Select
    parts.append(rect(194,320,130,22,BG,BORDER,4))
    parts.append(m(200,335,"not_bounded ▾",MUTED,10))
    # Timeout
    parts.append(rect(334,320,100,22,BG,BORDER,4))
    parts.append(m(340,335,"timeout...",MUTED,10))
    # Status right
    parts.append(m(700,335,"✓  10 rows  ·  elapsed=42ms  ·  exec=38ms  ·  size=2.1KB",GREEN,10))

    # Results table
    cols = ["airlinename","route_count"]
    col_w = 490
    parts.append(rect(10,354,980,24,BG3,BORDER,0))
    parts.append(m(20,370,cols[0],BLUE,10))
    parts.append(m(520,370,cols[1],BLUE,10))

    rows = [
        ("Delta Air Lines","3,285"),("United Airlines","3,102"),
        ("American Airlines","2,891"),("Southwest Airlines","2,654"),
        ("British Airways","1,832"),("Lufthansa","1,756"),
        ("Air France","1,621"),("Emirates","1,408"),
        ("Singapore Airlines","987"),("Qantas","876"),
    ]
    for i,(name,count) in enumerate(rows):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,378+i*22,980,22,bg,BORDER,0))
        parts.append(m(20,393+i*22,name,WHITE,10))
        parts.append(m(520,393+i*22,count,TEAL,10))

    # Footer
    parts.append(rect(4,598,992,24,BG3,BORDER,0))
    parts.append(t(20,614,"F1-F6: Switch Tab  ·  Ctrl+R: Refresh  ·  Ctrl+Q: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,628,"\n".join(parts),"Query Tab")

# ── Screenshot 3: Monitor Tab ─────────────────────────────────────────────────
def screenshot_monitor():
    parts = []
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(tab_bar(["Query [F1]","Monitor [F2]","Config [F3]","RBAC [F4]","Links [F5]","Cluster [F6]"],"Monitor [F2]",y=74))

    # Buttons
    parts.append(rect(10,108,980,38,BG3,BORDER,0))
    parts.append(rect(16,116,110,22,BLUE,BLUE,4))
    parts.append(t(71,131,"Refresh",BG,11,"middle","700",SANS))
    parts.append(rect(134,116,170,22,"#3d1111",ACCENT,4))
    parts.append(t(219,131,"Restart Service ⚠️",ACCENT,11,"middle","600",SANS))

    # Status cards
    cards = [
        (10,152,306,100,GREEN,"SERVICE STATUS","ACTIVE","Apache AsterixDB 2.1.0"),
        (326,152,306,100,BLUE,"INGESTION LINKS","3 connected","Local · myS3 · remoteCluster"),
        (642,152,348,100,AMBER,"AUTHORIZED NODES","2 nodes","node1.cluster · node2.cluster"),
    ]
    for x,y,w,h,color,label,val,sub in cards:
        parts.append(rect(x,y,w,h,BG3,color,8))
        parts.append(t(x+12,y+22,label,color,10,"start","600",SANS))
        parts.append(t(x+12,y+52,val,WHITE,22,"start","700",SANS))
        parts.append(t(x+12,y+76,sub,MUTED,10,"start","normal",SANS))

    # Active requests table
    parts.append(t(20,276,"Active Requests",WHITE,12,"start","600",SANS))
    parts.append(rect(10,284,980,24,BG3,BORDER,0))
    for label,xp in [("Context ID",20),("Elapsed",360),("State",480),("Statement",570)]:
        parts.append(m(xp,300,label,BLUE,10))

    active = [
        ("ctx-aef3-2c91","12.4s","running","SELECT * FROM `Default`.orders WHERE status = 'PENDING'..."),
        ("ctx-bb12-9f44","3.1s","running","SELECT COUNT(*) FROM `Travel`.airline GROUP BY country"),
        ("ctx-cc88-1234","0.8s","running","SELECT r.* FROM `Default`.route r LIMIT 1000"),
    ]
    for i,(ctx,elapsed,state,stmt) in enumerate(active):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,308+i*24,980,24,bg,BORDER,0))
        parts.append(m(20,324+i*24,ctx,TEAL,10))
        parts.append(m(360,324+i*24,elapsed,AMBER,10))
        parts.append(m(480,324+i*24,state,GREEN,10))
        parts.append(m(570,324+i*24,stmt[:65]+"…",MUTED,10))

    # No active msg
    parts.append(t(20,396,"Completed Requests (last 10)",WHITE,12,"start","600",SANS))
    parts.append(rect(10,404,980,24,BG3,BORDER,0))
    for label,xp in [("Context ID",20),("Elapsed",360),("State",460),("Rows",560),("Size",640)]:
        parts.append(m(xp,420,label,BLUE,10))

    completed = [
        ("ctx-d901-aaaa","485ms","success","1,243","48.2KB"),
        ("ctx-e022-bbbb","1.2s","success","0","—"),
        ("ctx-f133-cccc","38ms","success","10","2.1KB"),
    ]
    for i,(ctx,elapsed,state,rows,size) in enumerate(completed):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,428+i*24,980,24,bg,BORDER,0))
        parts.append(m(20,444+i*24,ctx,TEAL,10))
        parts.append(m(360,444+i*24,elapsed,AMBER,10))
        color = GREEN if state=="success" else ACCENT
        parts.append(m(460,444+i*24,state,color,10))
        parts.append(m(560,444+i*24,rows,WHITE,10))
        parts.append(m(640,444+i*24,size,MUTED,10))

    parts.append(rect(4,548,992,24,BG3,BORDER,0))
    parts.append(t(20,564,"F1-F6: Switch Tab  ·  Ctrl+R: Refresh  ·  Ctrl+Q: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,578,"\n".join(parts),"Monitor Tab")

# ── Screenshot 4: RBAC Tab ────────────────────────────────────────────────────
def screenshot_rbac():
    parts = []
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(tab_bar(["Query [F1]","Monitor [F2]","Config [F3]","RBAC [F4]","Links [F5]","Cluster [F6]"],"RBAC [F4]",y=74))

    parts.append(rect(10,108,980,38,BG3,BORDER,0))
    parts.append(rect(16,116,130,22,BLUE,BLUE,4))
    parts.append(t(81,131,"Refresh Users",BG,11,"middle","700",SANS))

    # Users table
    parts.append(t(20,166,"Users",WHITE,12,"start","600",SANS))
    parts.append(rect(10,174,980,24,BG3,BORDER,0))
    for label,xp in [("Username",20),("Domain",200),("Name",330),("Roles",500),("Groups",760)]:
        parts.append(m(xp,190,label,BLUE,10))

    users = [
        ("Administrator","local","","full_admin","—"),
        ("analytics_ro","local","Analytics Read-Only","analytics_reader[*]","analytics-team"),
        ("data_engineer","local","Data Engineering","analytics_admin[*], data_reader[*]","eng-team"),
        ("alice","local","Alice Smith","analytics_select[travel-sample]","analytics-team"),
        ("bob","external","Bob Jones","analytics_reader[*]","—"),
    ]
    for i,row in enumerate(users):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,198+i*24,980,24,bg,BORDER,0))
        color = AMBER if i==0 else WHITE
        parts.append(m(20,214+i*24,row[0],color,10))
        parts.append(m(200,214+i*24,row[1],TEAL,10))
        parts.append(m(330,214+i*24,row[2],MUTED,10))
        parts.append(m(500,214+i*24,row[3],PURPLE,10))
        parts.append(m(760,214+i*24,row[4],BLUE,10))

    # Groups table
    parts.append(t(20,334,"Groups",WHITE,12,"start","600",SANS))
    parts.append(rect(10,342,980,24,BG3,BORDER,0))
    for label,xp in [("Group Name",20),("Description",250),("Roles",550),("LDAP Ref",800)]:
        parts.append(m(xp,358,label,BLUE,10))

    groups = [
        ("analytics-team","Analytics read-only users","analytics_reader[*]","cn=analytics,dc=corp,dc=com"),
        ("eng-team","Data engineering team","analytics_admin[*], data_reader[*]","cn=engineers,dc=corp"),
        ("ops-team","Operations & admin","cluster_admin","cn=ops,dc=corp,dc=com"),
    ]
    for i,row in enumerate(groups):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,366+i*24,980,24,bg,BORDER,0))
        parts.append(m(20,382+i*24,row[0],AMBER,10))
        parts.append(m(250,382+i*24,row[1],MUTED,10))
        parts.append(m(550,382+i*24,row[2],PURPLE,10))
        parts.append(m(800,382+i*24,row[3],BLUE,10))

    parts.append(rect(4,468,992,24,BG3,BORDER,0))
    parts.append(t(20,484,"F1-F6: Switch Tab  ·  Ctrl+R: Refresh  ·  Ctrl+Q: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,498,"\n".join(parts),"RBAC Tab")

# ── Screenshot 5: Links Tab ────────────────────────────────────────────────────
def screenshot_links():
    parts = []
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(tab_bar(["Query [F1]","Monitor [F2]","Config [F3]","RBAC [F4]","Links [F5]","Cluster [F6]"],"Links [F5]",y=74))

    parts.append(rect(10,108,980,38,BG3,BORDER,0))
    parts.append(rect(16,116,130,22,BLUE,BLUE,4))
    parts.append(t(81,131,"Refresh Links",BG,11,"middle","700",SANS))

    parts.append(rect(10,154,980,24,BG3,BORDER,0))
    for label,xp in [("Link Name",20),("Dataverse",200),("Type",380),("Active Datasets",520),("Status",820)]:
        parts.append(m(xp,170,label,BLUE,10))

    links = [
        ("Local","Default","couchbase","airline, hotel, route, landmark","Connected"),
        ("myS3Link","TravelData","s3","flight_data, pricing","Connected"),
        ("azureArchive","Archive","azureblob","logs_2023, logs_2024","Connected"),
        ("remoteCluster","Analytics","couchbase","orders, customers","Disconnected"),
        ("gcsBackup","Backup","gcs","—","Disconnected"),
    ]
    for i,row in enumerate(links):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,178+i*28,980,28,bg,BORDER,0))
        parts.append(m(20,196+i*28,row[0],AMBER,10))
        parts.append(m(200,196+i*28,row[1],WHITE,10))
        type_colors = {"couchbase":BLUE,"s3":AMBER,"azureblob":PURPLE,"gcs":TEAL}
        parts.append(m(380,196+i*28,row[2],type_colors.get(row[2],WHITE),10))
        parts.append(m(520,196+i*28,row[3],MUTED,10))
        sc = GREEN if row[4]=="Connected" else ACCENT
        parts.append(m(820,196+i*28,row[4],sc,10))

    parts.append(rect(4,330,992,24,BG3,BORDER,0))
    parts.append(t(20,346,"F1-F6: Switch Tab  ·  Ctrl+R: Refresh  ·  Ctrl+Q: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,360,"\n".join(parts),"Links Tab")

# ── Screenshot 6: Cluster Tab ─────────────────────────────────────────────────
def screenshot_cluster():
    parts = []
    parts.append(rect(4,40,992,30,BG3,BORDER,0))
    parts.append(t(20,60,"Couchbase Enterprise Analytics",WHITE,13,"start","600",SANS))
    parts.append(tab_bar(["Query [F1]","Monitor [F2]","Config [F3]","RBAC [F4]","Links [F5]","Cluster [F6]"],"Cluster [F6]",y=74))

    parts.append(rect(10,108,980,38,BG3,BORDER,0))
    parts.append(rect(16,116,90,22,BLUE,BLUE,4))
    parts.append(t(61,131,"Refresh",BG,11,"middle","700",SANS))

    # Nodes
    parts.append(t(20,166,"Nodes",WHITE,12,"start","600",SANS))
    parts.append(rect(10,174,980,24,BG3,BORDER,0))
    for label,xp in [("Hostname",20),("Status",300),("Services",420)]:
        parts.append(m(xp,190,label,BLUE,10))

    nodes = [
        ("node1.analytics.cluster","healthy","kv, cbas"),
        ("node2.analytics.cluster","healthy","kv, cbas"),
        ("node3.analytics.cluster","healthy","kv"),
    ]
    for i,(host,status,services) in enumerate(nodes):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,198+i*24,980,24,bg,BORDER,0))
        parts.append(m(20,214+i*24,host,WHITE,10))
        sc = GREEN if status=="healthy" else ACCENT
        parts.append(m(300,214+i*24,status,sc,10))
        parts.append(m(420,214+i*24,services,TEAL,10))

    # Server Groups
    parts.append(t(20,278,"Server Groups",WHITE,12,"start","600",SANS))
    parts.append(rect(10,286,980,24,BG3,BORDER,0))
    for label,xp in [("Group Name",20),("Node Count",300),("Nodes",420)]:
        parts.append(m(xp,302,label,BLUE,10))

    sgroups = [("Group 1 (default)",2,"node1, node2"),("Group 2",1,"node3")]
    for i,(name,count,members) in enumerate(sgroups):
        bg = BG if i%2==0 else BG3
        parts.append(rect(10,310+i*24,980,24,bg,BORDER,0))
        parts.append(m(20,326+i*24,name,AMBER,10))
        parts.append(m(300,326+i*24,str(count),WHITE,10))
        parts.append(m(420,326+i*24,members,MUTED,10))

    # Tasks
    parts.append(t(20,372,"Active Cluster Tasks",WHITE,12,"start","600",SANS))
    parts.append(rect(10,380,980,24,BG3,BORDER,0))
    for label,xp in [("Type",20),("Status",250),("Progress",380)]:
        parts.append(m(xp,396,label,BLUE,10))
    parts.append(rect(10,404,980,24,BG,BORDER,0))
    parts.append(m(20,420,"(no active tasks)",MUTED,10,"start"))

    parts.append(rect(4,434,992,24,BG3,BORDER,0))
    parts.append(t(20,450,"F1-F6: Switch Tab  ·  Ctrl+R: Refresh  ·  Ctrl+Q: Quit",MUTED,10,"start","normal",FONT))

    return svg(1000,464,"\n".join(parts),"Cluster Tab")

# ── CLI screenshot ─────────────────────────────────────────────────────────────
def screenshot_cli():
    parts = []

    # Terminal window
    parts.append(rect(4,4,992,30,BG3,BORDER,0))
    parts.append(rect(4,4,992,10,BG3,BORDER,0))
    parts.append(t(500,24,"Terminal — cb-analytics",MUTED,12,"middle","normal",SANS))
    for cx,color in [(24,"#ff5f57"),(44,"#ffbd2e"),(64,"#28c840")]:
        parts.append(f'<circle cx="{cx}" cy="20" r="6" fill="{color}"/>')

    lines = [
        ("$",WHITE, "cb-analytics query execute \"SELECT a.airlinename, COUNT(*) AS routes FROM `Default`.airline a JOIN `Default`.route r ON r.airlineid = a.id GROUP BY a.airlinename ORDER BY routes DESC LIMIT 5\"",GREEN),
        ("","","",""),
        ("","",  "┌─────────────────────────────┬────────┐",BORDER),
        ("","",  "│ airlinename                 │ routes │",BLUE),
        ("","",  "├─────────────────────────────┼────────┤",BORDER),
        ("","",  "│ Delta Air Lines             │  3,285 │",WHITE),
        ("","",  "│ United Airlines             │  3,102 │",WHITE),
        ("","",  "│ American Airlines           │  2,891 │",WHITE),
        ("","",  "│ Southwest Airlines          │  2,654 │",WHITE),
        ("","",  "│ British Airways             │  1,832 │",WHITE),
        ("","",  "└─────────────────────────────┴────────┘",BORDER),
        ("","","",""),
        ("","",  "elapsed=142ms  exec=138ms  rows=5  size=312B",MUTED),
        ("","","",""),
        ("$",WHITE, "cb-analytics admin status",GREEN),
        ("","","",""),
        ("","",  '{ "state": "ACTIVE", "authorizedNodes": ["node1", "node2"], "ccRevLag": 0 }',TEAL),
        ("","","",""),
        ("$",WHITE, "cb-analytics links list",GREEN),
        ("","","",""),
        ("","",  "┌───────────────┬───────────┬────────────┬──────────────────────────────┐",BORDER),
        ("","",  "│ Name          │ Dataverse │ Type       │ Active Datasets               │",BLUE),
        ("","",  "├───────────────┼───────────┼────────────┼──────────────────────────────┤",BORDER),
        ("","",  "│ Local         │ Default   │ couchbase  │ airline, hotel, route         │",WHITE),
        ("","",  "│ myS3Link      │ TravelData│ s3         │ flight_data                  │",WHITE),
        ("","",  "└───────────────┴───────────┴────────────┴──────────────────────────────┘",BORDER),
        ("","","",""),
        ("$",WHITE, "cb-analytics security users",GREEN),
        ("","","",""),
        ("","",  "┌───────────────────┬──────────┬──────────────────────────────────────┐",BORDER),
        ("","",  "│ ID                │ Domain   │ Roles                                │",BLUE),
        ("","",  "├───────────────────┼──────────┼──────────────────────────────────────┤",BORDER),
        ("","",  "│ Administrator     │ local    │ full_admin                           │",WHITE),
        ("","",  "│ analytics_ro      │ local    │ analytics_reader[*]                  │",WHITE),
        ("","",  "│ alice             │ local    │ analytics_select[travel-sample]      │",WHITE),
        ("","",  "└───────────────────┴──────────┴──────────────────────────────────────┘",BORDER),
        ("","","",""),
        ("$",WHITE, "_",GREEN),
    ]
    for i,(prompt,pc,line,lc) in enumerate(lines):
        y = 58 + i*16
        if prompt:
            parts.append(m(14,y,prompt,pc,11))
            parts.append(m(26,y,line,lc,11))
        else:
            parts.append(m(14,y,line,lc,11))

    return svg(1000,660,"\n".join(parts),"CLI Screenshot")

# ── Generate ───────────────────────────────────────────────────────────────────
screenshots = {
    "01-connection-screen.svg": screenshot_connection,
    "02-query-tab.svg": screenshot_query,
    "03-monitor-tab.svg": screenshot_monitor,
    "04-rbac-tab.svg": screenshot_rbac,
    "05-links-tab.svg": screenshot_links,
    "06-cluster-tab.svg": screenshot_cluster,
    "07-cli-output.svg": screenshot_cli,
}

for filename, fn in screenshots.items():
    path = os.path.join(OUT, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(fn())
    print(f"Generated {filename}")

print("All screenshots generated.")

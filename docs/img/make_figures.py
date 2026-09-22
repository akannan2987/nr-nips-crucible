#!/usr/bin/env python3
"""Generate every figure under docs/img/ as SVG.

Run from the repository root:

    python3 docs/img/make_figures.py          # writes docs/img/*.svg

Pure Python, no dependencies, deterministic output (same bytes on every
platform), so a figure is edited by changing text here and rerunning, carries
no hidden metadata, and can be diffed like code. One symbol per record type
is defined once (``symbol``) and reused by every figure, so the same shape
means the same thing in every document.
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent

def fig_attention_page() -> None:
    W, H = 940, 440
    b = text(W/2, 34, "The attention page (CR-10): one audit, three doors, and the mark a person leaves", 16, INK, "middle", "bold")
    # the registry with its four kinds of flag
    b += box(30, 70, 220, 250, PANEL, COLOURS["chemical"], 10)
    b += symbol("chemical", 60, 96, 14)
    b += text(150, 100, "the registry", 12, INK, "middle", "bold")
    for i, (label, n) in enumerate((("shared identifiers", "221 groups"), ("batch conflicts", "3"), ("pending identifiers", "0"), ("doubtful formulas", "125"))):
        y = 128 + i * 44
        b += box(48, y, 184, 34, "#fff7ed", COLOURS["screening"], 6)
        b += text(140, y + 14, label, 10.5, INK, "middle", "bold")
        b += text(140, y + 27, n + " on the real export", 9.5, MUTED)
    # the one audit module
    b += arrow(252, 195, 330, 195, LINE)
    b += box(332, 150, 200, 90, "#eef2ff", COLOURS["chemical"], 8)
    b += text(432, 176, "app/audit.py", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(432, 198, ["groups, lists, ranks;", "reads the review marks"], 10.5, INK, "middle", 15)
    # three doors
    doors = (("browser · Needs attention", ["merge · keep both", "mark reviewed · set the identifier"], 74),
             ("API · GET /api/chemicals/audit", ["POST …/audit/review · …/merge", "POST …/:id/identifier"], 176),
             ("terminal · audit_chemicals.py", ["the same list, printed;", "merge_duplicate_chemicals.py"], 278))
    for title, rows, y in doors:
        b += path_arrow(f"M 532 195 L 600 {y + 30}", LINE)
        b += box(602, y, 300, 62, PAPER, LINE, 8)
        b += text(752, y + 20, title, 11.5, INK, "middle", "bold")
        b += lines(752, y + 38, rows, 10, MUTED, "middle", 13)
    # the mark
    b += box(332, 262, 200, 58, PAPER, COLOURS["chemical"], 6, dash=True)
    b += lines(432, 284, ["reviewed: {key: timestamp}", "stored on the entry itself"], 10.5, INK, "middle", 15)
    b += path_arrow("M 600 200 L 532 275", COLOURS["chemical"], dash=True)
    b += text(W/2, 378, "the page, the API and the script call one module, so they never disagree about what is flagged;", 11, INK)
    b += text(W/2, 396, "a mark left by one route is seen by the others, and a reviewed item stops counting on the banner without disappearing.", 11, INK)
    b += text(W/2, 418, "everyday version: one inspection list on the wall, with a pen tied to it — whoever ticks an item, everybody sees the tick", 10.5, MUTED)
    write("fig_attention_page.svg", svg(W, H, "One audit module read by the browser's attention page, the API and the terminal script; the review mark is stored on the entry", b))


def fig_source_tags() -> None:
    W, H = 940, 400
    b = text(W/2, 34, "Source tags (CR-11): derived from what the entry records, never stored; filter by all of them or any", 16, INK, "middle", "bold")
    chips = {"Dotmatics ID": "#4f46e5", "Excel upload": "#059669", "SDF upload": "#7c3aed", "CSV upload": "#d97706", "JSON upload": "#0284c7", "Manual": "#6b7280"}
    def chip(x, y, label):
        w = 8 + 6.4 * len(label)
        b_ = box(x, y, w, 18, chips[label] + "22", chips[label], 9, sw=1)
        b_ += text(x + w/2, y + 13, label, 9.5, chips[label], "middle", "bold")
        return b_, w
    # four entries with their tags
    rows = [("CHEM-000001  caffeine, from the export", ["Dotmatics ID", "Excel upload"]),
            ("CHEM-000002  vanillin, export + structure file", ["Dotmatics ID", "Excel upload", "SDF upload"]),
            ("CHEM-000003  from a spreadsheet of your own", ["Excel upload"]),
            ("CHEM-000004  typed in with Add Chemical", ["Manual"])]
    b += box(30, 66, 560, 200, PANEL, LINE, 10)
    b += text(310, 88, "four entries and the tags each carries", 12, INK, "middle", "bold")
    for i, (label, tags) in enumerate(rows):
        y = 106 + i * 38
        b += symbol("chemical", 52, y + 9, 9)
        b += text(66, y + 13, label, 10.5, INK, "start")
        x = 330
        for t in tags:
            c, w = chip(x, y, t); b += c; x += w + 6
    b += text(310, 254, "the tags come from formats, dtx_id and the sources the entry names", 9.5, MUTED)
    # the two readings
    b += box(610, 66, 300, 92, "#eef2ff", COLOURS["chemical"], 8)
    b += text(760, 88, "tick  Excel upload  +  SDF upload", 11.5, COLOURS["chemical"], "middle", "bold")
    b += lines(760, 110, ["all of these  →  CHEM-000002 only", "any of these  →  CHEM-000001, 000002, 000003"], 10.5, INK, "middle", 16)
    b += text(760, 146, "the default is all; one switch flips it", 9.5, MUTED)
    b += box(610, 174, 300, 92, "#fff7ed", COLOURS["screening"], 8)
    b += text(760, 196, "tick  Excel upload  +  Dotmatics ID", 11.5, COLOURS["screening"], "middle", "bold")
    b += lines(760, 218, ["all of these  →  CHEM-000001, 000002", "any of these  →  CHEM-000001, 000002, 000003"], 10.5, INK, "middle", 16)
    b += text(760, 254, "the owner's example: spreadsheet rows that also carry a REG_ID", 9.5, MUTED)
    # the strip
    b += box(30, 286, 880, 46, PAPER, LINE, 8)
    b += text(60, 314, "Compounds:", 10.5, MUTED, "start")
    x = 140
    for label, n, fill in (("All compounds 12,539", 0, COLOURS["chemical"]), ("One batch 12,533", 0, LINE), ("Several batches 6", 0, LINE), ("Batch rows 12,561", 0, LINE)):
        w = 10 + 6.6 * len(label)
        b += box(x, 298, w, 22, PAPER if fill == LINE else fill + "22", fill, 6, sw=1)
        b += text(x + w/2, 313, label, 10, INK if fill == LINE else fill, "middle", "bold")
        x += w + 8
    b += text(W/2, 356, "the same counts and the same tags from the browser, GET /api/chemicals/summary and registry_summary.py — one module, three doors;", 11, INK)
    b += text(W/2, 374, "a tag is computed when the entry is read, so it is never stale and a re-import cannot lose it.", 11, INK)
    b += text(W/2, 393, "everyday version: the coloured sticker on the folder's spine says which shelf it came from — and a folder can carry two", 10.5, MUTED)
    write("fig_source_tags.svg", svg(W, H, "Four registry entries with their source tags, the two readings of a multi-tag filter, and the strip of batch counts", b))


def fig_two_instances() -> None:
    W, H = 940, 430
    b = text(W/2, 34, "Two instances on one server (SH-12): production keeps the real data; testers get a copy on beta", 16, INK, "middle", "bold")
    # the development machine
    b += box(30, 120, 150, 90, PANEL, LINE, 10)
    b += text(105, 142, "development", 13, INK, "middle", "bold")
    b += text(105, 158, "machine", 13, INK, "middle", "bold")
    b += lines(105, 180, ["author on develop", "publish · promote"], 10.5, MUTED, "middle", 15)
    # the server
    b += box(230, 66, 680, 300, PAPER, LINE, 12, dash=True)
    b += text(570, 88, "the server — one machine, two folders, two containers, two ports", 11.5, MUTED)
    # beta
    b += box(260, 110, 290, 120, "#fff7ed", COLOURS["screening"], 10)
    b += text(405, 134, "beta instance", 13, COLOURS["screening"], "middle", "bold")
    b += lines(405, 156, ["folder nr-nips-crucible-beta · branch beta", "container crucible-py-beta · port 49161", "its own database: a copy of production's"], 10.5, INK, "middle", 15)
    b += text(405, 218, "testers log in here · nothing reaches production", 9.5, MUTED)
    # production
    b += box(590, 110, 290, 120, "#eef2ff", COLOURS["chemical"], 10)
    b += text(735, 134, "production instance", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(735, 156, ["folder nr-nips-crucible · branch master", "container crucible-py · port 49160", "the real database"], 10.5, INK, "middle", 15)
    b += text(735, 218, "the laboratory · moves only by promotion", 9.5, MUTED)
    # arrows: publish, promote, data copy
    b += arrow(182, 150, 258, 150, COLOURS["screening"])
    b += text(220, 142, "publish", 9.5, COLOURS["screening"])
    b += path_arrow("M 552 150 L 588 150", COLOURS["chemical"])
    b += text(570, 142, "promote", 9.5, COLOURS["chemical"])
    b += path_arrow("M 735 232 L 735 290 L 405 290 L 405 232", COLOURS["chemical"], dash=True)
    b += text(570, 306, "a copy of the data, one way, when you ask: backup on production, restore on beta", 9.5, MUTED)
    # shared: certificates, script
    b += box(260, 322, 620, 30, PANEL, LINE, 6)
    b += text(570, 342, "shared: the same container-py.sh (told its instance name), the same certificate (it names the host, not the port), the same setup guide", 9.5, INK)
    b += text(W/2, 392, "everyday version: the practice kitchen next to the restaurant kitchen — same equipment, a copy of tonight's ingredients,", 10.5, MUTED)
    b += text(W/2, 410, "and whatever a trainee burns there, no customer eats", 10.5, MUTED)
    write("fig_two_instances.svg", svg(W, H, "Production and beta on one server: two folders, two containers, two ports; publish reaches beta, promotion reaches production, data is copied one way on request", b))


def fig_publish_promote() -> None:
    """The two moments of the workflow once there are two instances (SH-12)."""
    W, H = 940, 400
    b = text(W/2, 34, "Two moments, not one: publish reaches beta; promotion reaches production", 16, INK, "middle", "bold")
    # the rail: three branch stations
    b += f"<line x1='90' y1='150' x2='850' y2='150' stroke='{LINE}' stroke-width='3'/>\n"
    stations = [(150, "develop", "where every change is authored", ACCENT),
                (470, "beta", "what the testers run", COLOURS["screening"]),
                (790, "master", "what the laboratory runs", COLOURS["chemical"])]
    for x, name, sub, col in stations:
        b += f"<circle cx='{x}' cy='150' r='14' fill='{PAPER}' stroke='{col}' stroke-width='3'/>\n"
        b += text(x, 112, name, 14, col, "middle", "bold", "ui-monospace,SFMono-Regular,Menlo,monospace")
        b += text(x, 128, sub, 10, MUTED)
    # moment 1: publish
    b += box(200, 168, 220, 54, "#fff7ed", COLOURS["screening"], 8)
    b += text(310, 188, "moment 1 — publish", 12, COLOURS["screening"], "middle", "bold")
    b += text(310, 206, "git push origin develop develop:beta", 10, INK, "middle", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(310, 240, "every change, the same day · CI runs · the mirror copies it", 9.5, MUTED)
    # moment 2: promote
    b += box(520, 168, 220, 54, "#eef2ff", COLOURS["chemical"], 8)
    b += text(630, 188, "moment 2 — promote", 12, COLOURS["chemical"], "middle", "bold")
    b += text(630, 206, "git push origin origin/beta:master", 10, INK, "middle", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(630, 240, "by hand, only when the testers agree · never automatic", 9.5, MUTED)
    # the instances under the stations
    b += box(360, 262, 220, 62, "#fff7ed", COLOURS["screening"], 8)
    b += text(470, 282, "beta instance · port 49161", 11.5, COLOURS["screening"], "middle", "bold")
    b += text(470, 300, "git pull origin beta · rebuild", 10, INK, "middle", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(470, 316, "testers", 9.5, MUTED)
    b += box(680, 262, 220, 62, "#eef2ff", COLOURS["chemical"], 8)
    b += text(790, 282, "production instance · port 49160", 11.5, COLOURS["chemical"], "middle", "bold")
    b += text(790, 300, "backup · git pull origin master · rebuild", 10, INK, "middle", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(790, 316, "the laboratory", 9.5, MUTED)
    b += arrow(470, 166, 470, 260, COLOURS["screening"], dash=True)
    b += arrow(790, 166, 790, 260, COLOURS["chemical"], dash=True)
    # people glyphs
    for i, x in enumerate((430, 450)):
        b += f"<circle cx='{x}' cy='338' r='4' fill='{COLOURS['screening']}'/><path d='M {x-7} 352 Q {x} 342 {x+7} 352' fill='none' stroke='{COLOURS['screening']}' stroke-width='2'/>\n"
    for x in (760, 780, 800, 820):
        b += f"<circle cx='{x}' cy='338' r='4' fill='{COLOURS['chemical']}'/><path d='M {x-7} 352 Q {x} 342 {x+7} 352' fill='none' stroke='{COLOURS['chemical']}' stroke-width='2'/>\n"
    b += text(W/2, 380, "a change that fails on beta is simply never promoted; nothing is ever edited on the server", 10.5, MUTED)
    write("fig_publish_promote.svg", svg(W, H, "Three branch stations on one rail: develop, beta, master. Publish pushes develop to beta and the beta instance pulls it; promotion pushes beta to master and production pulls it, by hand", b))


def fig_instance_name() -> None:
    """Three lines in .env.local name every resource of an instance (SH-12)."""
    W, H = 940, 420
    b = text(W/2, 34, "One file names everything: the instance name is a suffix, the port is a number, the code never knows the word", 15, INK, "middle", "bold")
    # the .env.local card
    b += box(40, 80, 250, 120, "#f9fafb", LINE, 10)
    b += text(165, 104, ".env.local  (in the beta folder)", 12, INK, "middle", "bold", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += lines(60, 132, ["USE_HTTPS=true", "CRUCIBLE_INSTANCE=beta", "CRUCIBLE_PORT=49161"], 12, INK, "start", 22, "normal")
    b += text(165, 214, "untracked · gitignored · one per folder", 9.5, MUTED)
    # the resources named from it
    rows = [
        ("image", "crucible-py-beta:latest", COLOURS["screening"]),
        ("container", "crucible-py-beta", COLOURS["screening"]),
        ("service unit", "container-crucible-py-beta.service", COLOURS["screening"]),
        ("monitor log", "/tmp/crucible-monitor-beta.log", COLOURS["screening"]),
        ("cron line", "CONTAINER_NAME=crucible-py-beta  API_URL=https://…:49161/api/stats", COLOURS["screening"]),
        ("address", "https://<vm-hostname>:49161", COLOURS["screening"]),
    ]
    y = 84
    for label, value, col in rows:
        b += path_arrow(f"M 292 140 C 330 140, 330 {y+12}, 358 {y+12}", col)
        b += box(360, y, 540, 26, PAPER, col, 6)
        b += text(372, y + 17, label, 10.5, MUTED, "start")
        b += text(470, y + 17, value, 10.5 if len(value) > 40 else 11, INK, "start", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
        y += 34
    # the default, for contrast
    b += box(40, 250, 250, 70, "#eef2ff", COLOURS["chemical"], 10)
    b += text(165, 274, "production's .env.local", 12, COLOURS["chemical"], "middle", "bold", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(165, 296, "USE_HTTPS=true   (no instance, no port)", 11, INK, "middle", "normal", "ui-monospace,SFMono-Regular,Menlo,monospace")
    b += text(165, 312, "so: crucible-py · 49160 · container-crucible-py.service", 9.5, MUTED)
    # what shares
    b += box(360, 300, 540, 44, PANEL, LINE, 6)
    b += text(630, 318, "shared on purpose: the same scripts, the same image recipe, the same certificate (it names the host, not the port)", 9.5, INK)
    b += text(630, 334, "separate on purpose: data/, backups/, the container, the image, the unit, the monitor line", 9.5, INK)
    b += text(W/2, 380, "everyday version: two identical uniforms; the name tag says which kitchen you cook in,", 10.5, MUTED)
    b += text(W/2, 398, "and the tag is pinned on the folder, not sewn into the cloth", 10.5, MUTED)
    write("fig_instance_name.svg", svg(W, H, "The three lines of the beta folder's .env.local fan out to the image, container, service unit, monitor log, cron line and address, all suffixed -beta or numbered 49161; production's file has no instance line and keeps the default names", b))


def fig_instance_label() -> None:
    """The page says which instance it is: name in, label and colour out (SH-13)."""
    W, H = 940, 430
    mono = "ui-monospace,SFMono-Regular,Menlo,monospace"
    b = text(W/2, 34, "The page says which instance it is: one name in, a word and a colour out", 16, INK, "middle", "bold")
    # the chain, left to right
    steps = [
        (30, ".env.local", ["CRUCIBLE_INSTANCE=beta", "CRUCIBLE_PORT=49161"]),
        (262, "container-py.sh", ["podman run …", "-e CRUCIBLE_INSTANCE=beta"]),
        (494, "the app", ["GET /api/instance", '{"name":"beta","label":"Beta"}']),
        (726, "the page", ["an amber pill: Beta", "tab title: [Beta] Crucible…"]),
    ]
    for x, title, rows in steps:
        b += box(x, 66, 184, 76, PANEL, LINE, 8)
        b += text(x + 92, 88, title, 12, INK, "middle", "bold")
        b += lines(x + 92, 108, rows, 9.5, INK, "middle", 15, "normal")
    for x in (216, 448, 680):
        b += arrow(x, 104, x + 44, 104, LINE)
    b += text(W/2, 164, "no name in the file means the default instance: the same chain answers \"Prod\" and indigo", 10.5, MUTED)
    # two header mock-ups
    def header(x, y, bar_fill, bar_stroke, pill_fill, pill_stroke, pill_text, label, port, tab):
        out = box(x, y - 26, 420, 22, PANEL, LINE, 6)
        out += text(x + 12, y - 11, tab, 10, MUTED, "start", "normal", mono)
        out += box(x, y, 420, 46, bar_fill, bar_stroke, 6)
        out += text(x + 14, y + 29, "Chemical & Sample Management", 12.5, INK, "start", "bold")
        out += f"<rect x='{x+230}' y='{y+13}' width='{len(label)*8+16}' height='20' rx='10' fill='{pill_fill}' stroke='{pill_stroke}' stroke-width='1.2'/>\n"
        out += text(x + 238 + len(label)*4, y + 27, label, 10.5, pill_text, "middle", "bold")
        out += text(x + 408, y + 29, f"Running on port {port}", 9.5, MUTED, "end")
        return out
    b += header(30, 226, PAPER, "#e5e7eb", "#e0e7ff", "#a5b4fc", "#3730a3", "Prod", 49160, "[Prod] Crucible: Pandora Toolbox Enhancement (v2.0)")
    b += header(490, 226, "#fffbeb", "#fcd34d", "#fef3c7", "#fbbf24", "#78350f", "Beta", 49161, "[Beta] Crucible: Pandora Toolbox Enhancement (v2.0)")
    b += text(240, 296, "production: white bar, indigo pill, the real registry", 10, MUTED)
    b += text(700, 296, "beta: amber bar, amber pill, a copy the testers may break", 10, MUTED)
    # what it is not
    b += box(30, 322, 880, 54, PANEL, LINE, 6)
    b += lines(470, 342, ["the label is derived from the same name the scripts use for the container, so the corner and the terminal cannot disagree;",
                          "nothing is stored, nothing is secret, and the answer stays open when the login arrives, because the login page must say where it is"], 9.5, INK, "middle", 15)
    b += text(W/2, 404, "everyday version: the same uniform in two kitchens, but the practice kitchen has amber walls and a name tag that says so", 10.5, MUTED)
    write("fig_instance_label.svg", svg(W, H, "One name in the settings file travels through the container script and the app to become a word and a colour in the page's corner; production shows an indigo Prod pill on a white bar, beta an amber Beta pill on an amber bar", b))


def fig_two_doors() -> None:
    """One running application, two doors into the same room (v2.21.2)."""
    W, H = 940, 440
    mono = "ui-monospace,SFMono-Regular,Menlo,monospace"
    b = text(W/2, 34, "One application, two doors into the same room: whichever you use, the service is inside", 16, INK, "middle", "bold")
    # the room
    b += box(300, 70, 340, 250, "#eef2ff", COLOURS["chemical"], 12)
    b += text(470, 96, "the running application", 13, COLOURS["chemical"], "middle", "bold")
    b += text(470, 114, "one container per instance: crucible-py · crucible-py-beta", 10, MUTED)
    # the caretaker (service) inside the room
    b += box(330, 132, 280, 96, PAPER, COLOURS["chemical"], 8)
    b += text(470, 154, "the service (systemd user unit)", 12, INK, "middle", "bold")
    b += lines(470, 174, ["container-crucible-py[-beta].service", "starts it at boot · restarts it if it dies", "owns the container while it runs"], 10, INK, "middle", 15)
    b += f"<circle cx='470' cy='268' r='14' fill='{PAPER}' stroke='{COLOURS['chemical']}' stroke-width='2'/>\n"
    b += text(470, 273, "on", 10, COLOURS["chemical"], "middle", "bold")
    b += text(470, 300, "status · stop · start · restart mean the same through either door", 10, MUTED)
    # left door: the script
    b += box(40, 120, 200, 150, "#fff7ed", COLOURS["screening"], 10)
    b += text(140, 144, "door 1: the script", 12, COLOURS["screening"], "middle", "bold")
    b += lines(140, 166, ["./container-py.sh status", "./container-py.sh stop", "./container-py.sh start", "./container-py.sh restart"], 10, INK, "middle", 16, "normal")
    b += text(140, 250, "in the instance's folder · every platform", 9, MUTED)
    b += arrow(242, 195, 298, 195, COLOURS["screening"])
    # right door: systemctl
    b += box(700, 120, 200, 150, "#f0fdf4", "#15803d", 10)
    b += text(800, 144, "door 2: the service", 12, "#15803d", "middle", "bold")
    b += lines(800, 166, ["systemctl --user status …", "systemctl --user stop …", "systemctl --user start …", "systemctl --user restart …"], 10, INK, "middle", 16, "normal")
    b += text(800, 250, "RHEL 8 only · from any folder", 9, MUTED)
    b += arrow(698, 195, 642, 195, "#15803d")
    # boot
    b += box(150, 336, 640, 40, PANEL, LINE, 8)
    b += text(470, 352, "the building opens (the server reboots)", 10.5, INK, "middle", "bold")
    b += text(470, 367, "lingering lets your services run while you are logged out; the enabled service switches the application on", 9, MUTED)
    b += arrow(470, 334, 470, 322, LINE, dash=True)
    b += text(W/2, 404, "the script builds and updates, then hands the container to the service; on a development machine there is no service and the script is the only door", 10.5, MUTED)
    b += text(W/2, 422, "everyday version: two doors into one kitchen; the caretaker inside keeps the stove lit and relights it every morning", 10.5, MUTED)
    write("fig_two_doors.svg", svg(W, H, "One running application per instance, with the systemd service inside it; two doors lead in, the script and systemctl, and the boot key underneath: lingering plus an enabled service switches it on when the server restarts", b))


def fig_six_blocks() -> None:
    """The route of every change since the beta instance: six blocks in two moments."""
    W, H = 940, 470
    mono = "ui-monospace,SFMono-Regular,Menlo,monospace"
    b = text(W/2, 34, "Every change travels the same six blocks: three to reach the testers, three to reach the laboratory", 15, INK, "middle", "bold")
    cols = [(40, "Development machine, your folder"), (350, "VM, mirror folder"), (660, "VM, instance folder")]
    for x, title in cols:
        b += text(x + 120, 66, title, 11.5, MUTED, "middle", "bold")
    def block(x, y, n, title, rows, col, fill):
        out = box(x, y, 240, 104, fill, col, 10)
        out += f"<circle cx='{x+22}' cy='{y+22}' r='13' fill='{col}'/>\n"
        out += text(x + 22, y + 27, str(n), 13, PAPER, "middle", "bold")
        out += text(x + 128, y + 27, title, 12, col, "middle", "bold")
        out += lines(x + 120, y + 50, rows, 9.5, INK, "middle", 15, "normal")
        return out
    amber, indigo = COLOURS["screening"], COLOURS["chemical"]
    # moment 1
    b += text(40, 92, "moment 1: publish, every change", 11, amber, "start", "bold")
    b += block(40, 100, 1, "commit, push, tag", ["git commit", "git push origin develop develop:beta", "git tag -a vX.Y.Z", "the public repository has it"], amber, "#fff7ed")
    b += block(350, 100, 2, "copy into the private repo", ["git fetch public", "git checkout public/develop -- .", "commit · tag · push develop develop:beta", "the private repository has it"], amber, "#fff7ed")
    b += block(660, 100, 3, "beta runs it", ["cd nr-nips-crucible-beta", "git pull --ff-only origin beta", "./container-py.sh rebuild  (if code changed)", "the testers see it"], amber, "#fff7ed")
    b += arrow(282, 152, 348, 152, amber)
    b += arrow(592, 152, 658, 152, amber)
    # pause
    b += f"<line x1='40' y1='236' x2='900' y2='236' stroke='{LINE}' stroke-width='1.2' stroke-dasharray='6 4'/>\n"
    b += text(W/2, 231, "the testers use it: minutes for a label, days for a login; a change that fails here is never promoted", 10, MUTED)
    # moment 2
    b += text(40, 262, "moment 2: promote, when the testers agree", 11, indigo, "start", "bold")
    b += block(40, 270, 4, "declare it good", ["git fetch origin", "git push origin origin/beta:master", "", "public master moves"], indigo, "#eef2ff")
    b += block(350, 270, 5, "the same, private side", ["git push origin origin/beta:master", "git diff --stat public/develop develop", "(only the six workbooks)", "private master moves"], indigo, "#eef2ff")
    b += block(660, 270, 6, "production runs it", ["cd nr-nips-crucible · backup", "git pull --ff-only origin master", "./container-py.sh rebuild  (if code changed)", "the laboratory sees it"], indigo, "#eef2ff")
    b += arrow(282, 322, 348, 322, indigo)
    b += arrow(592, 322, 658, 322, indigo)
    b += text(W/2, 408, "what changes between releases: whether blocks 3 and 6 rebuild (code) or only pull (documents), and how long the pause lasts", 10, MUTED)
    b += text(W/2, 428, "the detailed steps with expected output: 03-git-workflow.md, Flow A · everyday version: a recipe is written at home, copied into the", 10, MUTED)
    b += text(W/2, 446, "restaurant's book, cooked in the practice kitchen; when the trainees approve, it is marked approved in both places and the restaurant cooks it", 10, MUTED)
    write("fig_six_blocks.svg", svg(W, H, "Six blocks in two rows: publish (development machine commit and push, mirror copy and push, beta folder pull and rebuild) then, after the testers agree, promote (development machine push beta to master, mirror the same and the sync check, production folder backup, pull and rebuild)", b))


# ---------------------------------------------------------------- palette --
INK = "#1f2937"        # text
MUTED = "#6b7280"      # secondary text
LINE = "#9ca3af"       # box strokes, arrows
PAPER = "#ffffff"
PANEL = "#f9fafb"
ACCENT = "#374151"
COLOURS = {            # one colour per record type, everywhere
    "chemical": "#4f46e5",
    "sample": "#0d9488",
    "screening": "#d97706",
    "toxicology": "#be123c",
}
FONT = "font-family='-apple-system,Segoe UI,Helvetica,Arial,sans-serif'"

# ---------------------------------------------------------------- helpers --
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")


def svg(width: int, height: int, label: str, body: str) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"width='{width}' height='{height}' role='img' aria-label='{esc(label)}' {FONT}>\n"
        f"<rect x='0.5' y='0.5' width='{width-1}' height='{height-1}' rx='12' fill='{PAPER}' stroke='#e5e7eb'/>\n"
        f"<defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='8' markerHeight='8' orient='auto-start-reverse'>"
        f"<path d='M 0 0 L 10 5 L 0 10 z' fill='{LINE}'/></marker></defs>\n"
        f"{body}</svg>\n"
    )


def text(x: float, y: float, s: str, size: int = 13, colour: str = INK, anchor: str = "middle", weight: str = "normal", family: str | None = None) -> str:
    fam = f" font-family='{family}'" if family else ""
    return f"<text x='{x}' y='{y}' font-size='{size}' fill='{colour}' text-anchor='{anchor}' font-weight='{weight}'{fam}>{esc(s)}</text>\n"


def lines(x: float, y: float, rows: list[str], size: int = 12, colour: str = INK, anchor: str = "middle", gap: int = 16, weight: str = "normal") -> str:
    return "".join(text(x, y + i * gap, r, size, colour, anchor, weight if i == 0 else "normal") for i, r in enumerate(rows))


def box(x: float, y: float, w: float, h: float, fill: str = PANEL, stroke: str = LINE, rx: int = 8, dash: bool = False, sw: float = 1.2) -> str:
    d = " stroke-dasharray='6 4'" if dash else ""
    return f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{rx}' fill='{fill}' stroke='{stroke}' stroke-width='{sw}'{d}/>\n"


def arrow(x1: float, y1: float, x2: float, y2: float, colour: str = LINE, dash: bool = False, sw: float = 1.6) -> str:
    d = " stroke-dasharray='6 4'" if dash else ""
    return f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{colour}' stroke-width='{sw}' marker-end='url(#arrow)'{d}/>\n"


def path_arrow(d: str, colour: str = LINE, dash: bool = False) -> str:
    dd = " stroke-dasharray='6 4'" if dash else ""
    return f"<path d='{d}' fill='none' stroke='{colour}' stroke-width='1.6' marker-end='url(#arrow)'{dd}/>\n"


def symbol(kind: str, cx: float, cy: float, s: float = 18) -> str:
    """The one symbol per record type, used in every figure."""
    c = COLOURS[kind]
    if kind == "chemical":  # hexagon, the ring chemists draw
        pts = " ".join(f"{cx + s*dx},{cy + s*dy}" for dx, dy in
                       [(0, -1), (0.866, -0.5), (0.866, 0.5), (0, 1), (-0.866, 0.5), (-0.866, -0.5)])
        return f"<polygon points='{pts}' fill='{c}' fill-opacity='0.15' stroke='{c}' stroke-width='2'/>\n"
    if kind == "sample":  # a vial
        w, h = s * 0.9, s * 1.9
        return (f"<rect x='{cx-w/2}' y='{cy-h/2+s*0.35}' width='{w}' height='{h-s*0.35}' rx='{w/3}' fill='{c}' fill-opacity='0.15' stroke='{c}' stroke-width='2'/>\n"
                f"<rect x='{cx-w/3}' y='{cy-h/2}' width='{2*w/3}' height='{s*0.4}' fill='{c}'/>\n")
    if kind == "screening":  # a 3x3 grid, the assay plate
        g = s * 0.62
        out = ""
        for i in range(3):
            for j in range(3):
                out += f"<rect x='{cx - 1.5*g + i*g + 1}' y='{cy - 1.5*g + j*g + 1}' width='{g-2}' height='{g-2}' rx='2' fill='{c}' fill-opacity='{0.15 if (i+j)%2 else 0.55}' stroke='{c}' stroke-width='1.2'/>\n"
        return out
    if kind == "toxicology":  # a dose-response curve in a frame
        w, h = s * 2, s * 1.6
        x0, y0 = cx - w / 2, cy - h / 2
        curve = f"M {x0+3} {y0+h-4} C {x0+w*0.45} {y0+h-4}, {x0+w*0.55} {y0+4}, {x0+w-3} {y0+4}"
        return (f"<rect x='{x0}' y='{y0}' width='{w}' height='{h}' rx='4' fill='{c}' fill-opacity='0.12' stroke='{c}' stroke-width='2'/>\n"
                f"<path d='{curve}' fill='none' stroke='{c}' stroke-width='2.2'/>\n")
    raise ValueError(kind)


def write(name: str, content: str) -> None:
    (OUT / name).write_text(content, encoding="utf-8", newline="\n")
    print("wrote", name)


# ---------------------------------------------------------------- figures --
def fig_record_types() -> None:
    W, H = 900, 330
    b = text(W/2, 34, "The four record types, and how they hang off a chemical", 16, INK, "middle", "bold")
    cards = [
        ("chemical", "Chemical", ["The substance, on paper:", "name, formula, CAS number", "(the anchor for the rest)"]),
        ("sample", "Sample", ["A physical quantity in a vial:", "batch, concentration,", "location, expiry"]),
        ("screening", "Screening", ["The fast, broad first test:", "run a sample against an assay,", "record what happened"]),
        ("toxicology", "Toxicology study", ["The slow, careful one:", "dose levels, endpoints,", "NOAEL"]),
    ]
    xs = [90, 305, 520, 735]
    for (kind, title, desc), x in zip(cards, xs):
        b += box(x - 80, 60, 160, 170, PAPER, COLOURS[kind], 10)
        b += symbol(kind, x, 100, 20)
        b += text(x, 150, title, 14, COLOURS[kind], "middle", "bold")
        b += lines(x, 172, desc, 11, MUTED, "middle", 15)
    for x in xs[1:]:
        b += path_arrow(f"M {x} 236 L {x} 262 L 90 262 L 90 236", COLOURS["chemical"])
    b += text(W/2, 292, "sample, screening and toxicology each point at ONE chemical — that pointer is the registry's whole value", 12, INK)
    b += text(W/2, 312, "everyday version: one catalogue card per book; every loan slip, review and repair note is pinned to that card", 11, MUTED)
    write("fig_record_types.svg", svg(W, H, "The four record types: chemical, sample, screening, toxicology; the last three each point at one chemical", b))


def fig_doc_is_truth() -> None:
    W, H = 900, 340
    b = text(W/2, 34, "The one design rule: the stored document is the truth; every other column is an index", 16, INK, "middle", "bold")
    b += text(W/2, 56, "one row of the screening table, as it really is", 12, MUTED)
    # indexed columns
    cols = [("id", "UUID"), ("chemical_id", "CHEM-0042"), ("created_at", "2026-08-25"), ("seq", "18 311")]
    x = 40
    for name, val in cols:
        b += box(x, 80, 120, 70, PANEL, LINE, 6)
        b += text(x + 60, 104, name, 12, ACCENT, "middle", "bold", "monospace")
        b += text(x + 60, 132, val, 11, MUTED, "middle", "normal", "monospace")
        x += 128
    b += box(555, 80, 305, 170, "#eef2ff", COLOURS["chemical"], 8, sw=1.6)
    b += text(707, 104, "doc", 13, COLOURS["chemical"], "middle", "bold", "monospace")
    b += lines(570, 128, [
        '{ "Compound": "Phenol, 2,4-di-tertiobutyl",',
        '  "CAS": "96-76-4",',
        '  "Migration (mg/kg)": "#DIV/0!",',
        '  "Temp": "40 °C", "Time": "10 d",',
        '  "source_file": "…screening_export.xlsm",',
        '  … every column the file had … }',
    ], 11, INK, "start", 17)
    b += text(295, 175, "indexes: exist only to FIND the row quickly", 12, ACCENT, "middle", "bold")
    b += text(295, 193, "derived from doc — can be added, dropped or rebuilt", 11, MUTED)
    b += text(707, 268, "the truth: the row exactly as the laboratory wrote it", 12, COLOURS["chemical"], "middle", "bold")
    b += arrow(560, 168, 480, 168, COLOURS["chemical"], dash=True)
    b += text(520, 158, "derive", 10, MUTED)
    b += text(W/2, 305, "why it matters: an upload never has to be reshaped to fit a schema, and adding a column later breaks nothing", 12, INK)
    b += text(W/2, 324, "everyday version: the original letter in the folder; the card index in the drawer only says which folder", 11, MUTED)
    write("fig_doc_is_truth.svg", svg(W, H, "A table row: a few indexed columns beside one doc column that holds the whole record; the doc is the truth, the indexes are derived", b))


def fig_machine_layout() -> None:
    W, H = 940, 470
    b = text(W/2, 34, "Two repositories, four folders — content flows public → private only", 16, INK, "middle", "bold")
    # the development machine
    b += box(30, 70, 250, 130, PANEL, LINE, 10)
    b += text(155, 94, "Your development machine", 13, INK, "middle", "bold")
    b += box(50, 108, 210, 74, PAPER, ACCENT, 6)
    b += lines(155, 130, ["authoring folder", "branch develop", "origin = PUBLIC only"], 11, INK, "middle", 16)
    # GitHub public
    b += box(370, 70, 200, 60, "#eef2ff", COLOURS["chemical"], 10)
    b += lines(470, 94, ["PUBLIC repository", "develop · beta · master"], 12, COLOURS["chemical"], "middle", 16, "bold")
    # GitHub private
    b += box(370, 250, 200, 60, "#fff1f2", COLOURS["toxicology"], 10)
    b += lines(470, 274, ["PRIVATE repository", "develop · beta · master"], 12, COLOURS["toxicology"], "middle", 16, "bold")
    # VM
    b += box(660, 70, 250, 380, PANEL, LINE, 10)
    b += text(785, 94, "The RHEL 8 VM", 13, INK, "middle", "bold")
    b += box(680, 108, 210, 66, PAPER, ACCENT, 6)
    b += lines(785, 128, ["mirror folder", "origin = private", "+ remote 'public' (fetch only)"], 11, INK, "middle", 15)
    b += box(680, 190, 210, 96, "#fff7ed", COLOURS["screening"], 6)
    b += lines(785, 210, ["beta folder  (nr-nips-crucible-beta)", "branch beta · port 49161", "container crucible-py-beta", "its own data/ · certs/ · .env.local", "the testers"], 10.5, INK, "middle", 15)
    b += box(680, 302, 210, 130, "#eef2ff", COLOURS["chemical"], 6)
    b += lines(785, 322, ["production folder  (nr-nips-crucible)", "branch master · port 49160", "container crucible-py", "the real data/ · certs/ · .env.local", "the laboratory"], 10.5, INK, "middle", 15)
    b += text(785, 412, "moves only by a promotion", 9.5, MUTED)
    # arrows
    b += arrow(282, 120, 368, 100, COLOURS["chemical"])
    b += box(288, 82, 74, 20, PAPER, COLOURS["chemical"], 4)
    b += text(325, 96, "gate ✓ push", 10, COLOURS["chemical"])
    b += arrow(572, 100, 678, 136, COLOURS["chemical"], dash=True)
    b += text(628, 108, "fetch public", 10, MUTED)
    b += arrow(678, 156, 572, 262, COLOURS["toxicology"])
    b += text(600, 200, "commit + push", 10, MUTED)
    b += arrow(572, 280, 678, 236, COLOURS["screening"], dash=True)
    b += text(626, 250, "pull beta", 10, COLOURS["screening"])
    b += arrow(572, 300, 678, 366, COLOURS["toxicology"], dash=True)
    b += text(614, 346, "pull master", 10, MUTED)
    b += text(155, 230, "holds NO private credentials:", 11, MUTED)
    b += text(155, 246, "it cannot push to the private repository", 11, MUTED)
    b += text(W/2, 458, "a fix found on the VM travels back as a patch, never a push — the arrow never runs right to left", 12, INK)
    write("fig_machine_layout.svg", svg(W, H, "The authoring folder on the development machine pushes to the public repository; the VM's mirror folder fetches public and pushes private; the beta folder pulls beta and the production folder pulls master from private", b))


def fig_change_travels() -> None:
    W, H = 940, 250
    b = text(W/2, 34, "How a change travels — the loop after setup, on one screen", 16, INK, "middle", "bold")
    dev = "development machine"
    steps = [
        ("edit", "on develop", dev), ("test", "90 passed", dev), ("gate", "✓ SAFE TO PUSH", dev),
        ("push", "3 branches", dev), ("mirror", "public → private", "VM"), ("deploy", "pull, rebuild if code", "VM"), ("confirm", "only 6 workbooks differ", "VM"),
    ]
    x = 30
    for i, (t, sub, where) in enumerate(steps):
        col = COLOURS["chemical"] if where == dev else COLOURS["toxicology"]
        b += box(x, 80, 116, 70, PAPER, col, 8)
        b += text(x + 58, 106, t, 14, col, "middle", "bold")
        b += text(x + 58, 128, sub, 10.5, MUTED)
        b += text(x + 58, 168, where, 10, col)
        if i < len(steps) - 1:
            b += arrow(x + 118, 115, x + 130, 115, LINE)
        x += 132
    b += path_arrow(f"M 880 152 L 880 200 L 16 200 L 16 115 L 28 115", LINE, dash=True)
    b += text(W/2, 222, "a rebuild is needed only when backend/, client/ or the Dockerfile changed; documentation needs the pull alone", 11, INK)
    b += text(W/2, 240, "full commands with expected output: docs/03-git-workflow.md · one-screen version: the handbook cheat sheet", 11, MUTED)
    write("fig_change_travels.svg", svg(W, H, "Seven steps: edit, test, gate, push on the development machine; mirror, deploy, confirm on the VM; then back to edit", b))


def fig_request_path() -> None:
    W, H = 940, 300
    b = text(W/2, 34, "One request, four layers — why the routers are thin", 16, INK, "middle", "bold")
    boxes = [
        ("Browser or script", ["GET /api/chemicals", "(the web page is just", "the API's first client)"], ACCENT),
        ("Router", ["backend/app/routers/", "a few lines: receive,", "call the store, return"], COLOURS["chemical"]),
        ("Session", ["database.py · get_db", "opens a session before,", "closes it after"], COLOURS["sample"]),
        ("Store", ["store.py", "the ONLY place that", "talks to the tables"], COLOURS["screening"]),
        ("Model + database", ["models.py → SQLite file", "data/crucible.db", "(or PostgreSQL)"], COLOURS["toxicology"]),
    ]
    x = 30
    for i, (title, rows, col) in enumerate(boxes):
        b += box(x, 70, 160, 110, PAPER, col, 8)
        b += text(x + 80, 94, title, 13, col, "middle", "bold")
        b += lines(x + 80, 116, rows, 10.5, MUTED, "middle", 15)
        if i < len(boxes) - 1:
            b += arrow(x + 162, 110, x + 178, 110, LINE)
            b += arrow(x + 178, 150, x + 162, 150, LINE, dash=True)
        x += 180
    b += text(W/2, 212, "solid: the request going in · dashed: the answer coming back as JSON, byte-identical to the original prototype's", 11, INK)
    b += text(W/2, 232, "a new client — a script, another tool — gets exactly what the web page gets, because the logic lives in one place", 11, MUTED)
    b += text(W/2, 262, "everyday version: reception (router) → the key to the archive (session) → the archivist (store) → the shelves (database)", 11, MUTED)
    write("fig_request_path.svg", svg(W, H, "A request passes browser to router to session to store to model and database, and the JSON answer returns the same way", b))


def fig_two_stage() -> None:
    W, H = 940, 360
    b = text(W/2, 34, "Chemical identification: two stages, opposite rules, on purpose", 16, INK, "middle", "bold")
    b += box(30, 80, 170, 90, PANEL, LINE, 8)
    b += text(115, 104, "a screening row", 13, INK, "middle", "bold")
    b += symbol("screening", 52, 140, 10)
    b += lines(140, 132, ["name: Phenol, 2,4-di-…", "CAS: 96-76-4"], 10.5, MUTED, "middle", 15)
    b += arrow(202, 125, 250, 125, LINE)
    b += box(252, 70, 260, 110, "#eef2ff", COLOURS["chemical"], 8)
    b += text(382, 94, "Stage 1 — your own registry", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(382, 116, ["at upload, no network", "CAS matches  OR  name matches", "→ link"], 11, INK, "middle", 16)
    b += text(382, 168, "trusted: the registry is curated", 10, MUTED)
    b += arrow(514, 125, 560, 125, LINE)
    b += box(562, 70, 348, 110, "#fff1f2", COLOURS["toxicology"], 8)
    b += text(736, 94, "Stage 2 — PubChem, a background job", 13, COLOURS["toxicology"], "middle", "bold")
    b += lines(736, 116, ["name AND CAS must resolve", "to the SAME compound", "→ register it, then link"], 11, INK, "middle", 16)
    b += text(736, 168, "inference: it must corroborate itself", 10, MUTED)
    # outcomes
    b += path_arrow("M 382 182 L 382 230", COLOURS["chemical"])
    b += box(292, 232, 180, 40, PAPER, COLOURS["chemical"], 6)
    b += text(382, 257, "linked to a registry entry", 11, COLOURS["chemical"])
    b += path_arrow("M 640 182 L 640 230", COLOURS["toxicology"])
    b += box(550, 232, 180, 40, PAPER, COLOURS["toxicology"], 6)
    b += text(640, 257, "registered and linked", 11, COLOURS["toxicology"])
    b += path_arrow("M 830 182 L 830 230", LINE, dash=True)
    b += box(740, 232, 180, 40, PAPER, LINE, 6)
    b += text(830, 257, "unlinked report: the reason", 11, MUTED)
    b += text(W/2, 300, "the strict rule rejects most house-style names (tertiobutyl for tert-butyl) — chosen knowingly:", 12, INK)
    b += text(W/2, 318, "when one identifier was trusted alone, 19 compounds were registered with another substance's chemistry", 12, INK)
    b += text(W/2, 342, "everyday version: your own staff list needs one matching detail; a stranger's claim needs photo AND number to agree", 11, MUTED)
    write("fig_two_stage_identification.svg", svg(W, H, "Stage 1 links a row when either the CAS or the name matches the curated registry; stage 2 asks PubChem and registers only when name and CAS agree", b))


def fig_tracks() -> None:
    W, H = 940, 400
    b = text(W/2, 34, "The plan as six tracks: one per module, and the spine they all stand on", 16, INK, "middle", "bold")
    tracks = [
        ("CR", "Chemical Registry", "chemical", ["every way in · sort, filter, views", "unregistered + incomplete notices"], "next: CR-3 every way in"),
        ("SD", "Screening Data", "screening", ["the registry-first rule", "every way in · re-identify"], "next: SD-1 (specified)"),
        ("SM", "Sample Management", "sample", ["the same table conveniences", "the same rule, later"], "next: SM-1 after CR-1"),
        ("TX", "Toxicology", "toxicology", ["a real study export", "as a template spec"], "waits on: a file"),
        ("QC", "Query Console", None, ["saved queries · download", "recipes follow the schema"], "next: QC-1"),
    ]
    x0, w, gap = 30, 170, 8
    for i, (code, name, kind, rows, nxt) in enumerate(tracks):
        x = x0 + i * (w + gap)
        col = COLOURS[kind] if kind else ACCENT
        b += box(x, 60, w, 230, PAPER, col, 10)
        b += text(x + 16, 86, code, 15, col, "start", "bold")
        b += text(x + w/2, 112, name, 12.5, INK, "middle", "bold")
        if kind:
            b += symbol(kind, x + w/2, 152, 16)
        else:
            b += text(x + w/2, 158, "SELECT …", 13, ACCENT, "middle", "bold", "ui-monospace,Menlo,Consolas,monospace")
        b += lines(x + w/2, 198, rows, 10.5, MUTED, "middle", 15)
        b += box(x + 10, 246, w - 20, 30, PANEL, col, 6)
        b += text(x + w/2, 266, nxt, 10.5, col, "middle", "bold")
    # the spine
    b += box(30, 304, 882, 52, "#f3f4f6", ACCENT, 10)
    b += text(46, 326, "SH", 15, ACCENT, "start", "bold")
    b += text(470, 324, "Shared spine — the platform, the documents, CI, the schema, authentication, the module names", 12, INK, "middle", "bold")
    b += text(470, 344, "phases 00–05b live here · next: SH-1 module names, then SH-2 schema normalisation, then SH-3 authentication", 10.5, MUTED)
    b += text(W/2, 382, "everyday version: five trades on one renovation, each with its own list — and the scaffolding all of them stand on", 11, MUTED)
    write("fig_tracks.svg", svg(W, H, "Six tracks: Chemical Registry, Screening Data, Sample Management, Toxicology, Query Console, and the shared spine, each with its next phase", b))


def fig_registry_first() -> None:
    W, H = 940, 380
    b = text(W/2, 34, "The registry-first rule: the registry is the gate, and a row needs both keys", 16, INK, "middle", "bold")
    # the row, with two keys
    b += box(30, 80, 210, 120, PANEL, COLOURS["screening"], 8)
    b += text(135, 104, "a screening row", 13, INK, "middle", "bold")
    b += symbol("screening", 60, 150, 10)
    b += lines(160, 138, ["key 1 · name: Phenol", "key 2 · CAS: 108-95-2"], 11, INK, "middle", 18, "bold")
    b += text(135, 190, "as written in the laboratory's file", 10, MUTED)
    b += arrow(242, 140, 300, 140, LINE)
    # the door / registry
    b += box(302, 66, 300, 150, "#eef2ff", COLOURS["chemical"], 8)
    b += text(452, 90, "the Chemical Registry", 13, COLOURS["chemical"], "middle", "bold")
    b += symbol("chemical", 340, 150, 18)
    b += lines(470, 122, ["ONE registered entry must match", "BOTH the name AND the CAS", "→ link the row to it"], 11, INK, "middle", 16)
    b += text(452, 200, "nothing is registered at the door; PubChem is never asked", 10, MUTED)
    # outcomes
    b += path_arrow("M 380 218 L 380 262", COLOURS["chemical"])
    b += box(290, 264, 180, 40, PAPER, COLOURS["chemical"], 6)
    b += text(380, 289, "both keys fit: linked", 11, COLOURS["chemical"])
    b += path_arrow("M 540 218 L 540 262", LINE, dash=True)
    b += box(480, 264, 220, 40, PAPER, LINE, 6)
    b += text(590, 289, "a key missing: stored, unlinked", 11, MUTED)
    # the lobby / review
    b += arrow(702, 284, 740, 284, LINE, dash=True)
    b += box(742, 236, 170, 96, "#fff7ed", COLOURS["screening"], 8)
    b += text(827, 258, "unregistered list", 12, COLOURS["screening"], "middle", "bold")
    b += lines(827, 278, ["a notice in the registry", "download, or register", "some or all — by a person"], 10, INK, "middle", 14)
    b += path_arrow("M 827 234 L 827 218 L 620 218 L 620 140 L 604 140", COLOURS["screening"], dash=True)
    b += text(W/2, 340, "a name alone, or a CAS alone, is not enough — that is the failure the old second stage had, and the rule removes it", 12, INK)
    b += text(W/2, 362, "everyday version: a members-only building — name AND membership number must match the same member in the book; nobody joins at the door", 11, MUTED)
    write("fig_registry_first.svg", svg(W, H, "A screening row reaches the registry with two keys, its name and its CAS number; both must fit one registered entry or the row waits, unlinked, on the unregistered list", b))


def fig_module_names() -> None:
    W, H = 940, 330
    b = text(W/2, 34, "The sidebar before and after SH-1: the modules say what they are", 16, INK, "middle", "bold")
    def sidebar(x, title, items, col):
        b = box(x, 60, 300, 200, PAPER, col, 10)
        b += text(x + 150, 84, title, 12, col, "middle", "bold")
        y = 108
        for label, kind, new in items:
            if kind:
                b += symbol(kind, x + 28, y - 4, 8)
            else:
                b += text(x + 28, y, "▸", 12, MUTED)
            b += text(x + 48, y, label, 12, INK, "start", "bold" if new else "normal")
            y += 26
        return b
    old = [("Dashboard", None, False), ("Chemicals", "chemical", False), ("Samples", "sample", False),
           ("Screening", "screening", False), ("Query", None, False), ("Toxicology", "toxicology", False)]
    new = [("Dashboard", None, False), ("Chemical Registry", "chemical", True), ("Sample Management", "sample", True),
           ("Screening Data", "screening", True), ("Query", None, False), ("Toxicology", "toxicology", False)]
    b += sidebar(60, "before v2.9.0", old, LINE)
    b += arrow(372, 160, 560, 160, ACCENT)
    b += text(466, 150, "labels only", 11, MUTED)
    b += sidebar(580, "from v2.9.0", new, COLOURS["chemical"])
    b += text(W/2, 288, "the web addresses (/chemicals, /samples, /screening) and every API path are unchanged — bookmarks and scripts keep working", 11, INK)
    b += text(W/2, 310, "everyday version: the shop's departments got signs that say what they sell; the aisles did not move", 11, MUTED)
    write("fig_module_names.svg", svg(W, H, "The sidebar before and after: Chemicals, Samples and Screening become Chemical Registry, Sample Management and Screening Data; addresses unchanged", b))


def fig_auth_ladder() -> None:
    W, H = 940, 440
    b = text(W/2, 34, "Authentication as a ladder: three rungs, one flag, single sign-on at the top", 16, INK, "middle", "bold")
    # a lock symbol: body + shackle
    def lock(cx, cy, s, col, open_=False):
        body = f"<rect x='{cx-s*0.6}' y='{cy-s*0.1}' width='{s*1.2}' height='{s*0.9}' rx='{s*0.15}' fill='{col}' fill-opacity='0.18' stroke='{col}' stroke-width='2'/>\n"
        dx = s*0.55 if open_ else 0
        shackle = f"<path d='M {cx-s*0.35+dx} {cy-s*0.1} V {cy-s*0.45} A {s*0.35} {s*0.35} 0 0 1 {cx+s*0.35+dx} {cy-s*0.45} V {cy-s*0.1}' fill='none' stroke='{col}' stroke-width='2.4'/>\n"
        return body + shackle
    rungs = [
        (60,  "rung 0 · today", "open port", ["HTTPS only", "no login, nobody recorded"], LINE, True),
        (280, "rung 1 · SH-3a", "token gate", ["one shared secret", "scripts use it forever"], COLOURS["screening"], False),
        (500, "rung 2 · SH-3b", "local accounts", ["username + hashed password", "roles: viewer · editor · admin"], COLOURS["sample"], False),
        (720, "rung 3 · SH-3c", "single sign-on", ["the corporate login vouches", "no password held here"], COLOURS["chemical"], False),
    ]
    for i, (x, code, title, rows, col, open_) in enumerate(rungs):
        top = 190 - i * 40
        b += box(x, top, 170, 160, PAPER, col, 10)
        b += text(x + 85, top + 20, code, 10.5, MUTED)
        b += lock(x + 85, top + 56, 24, col, open_)
        b += text(x + 85, top + 104, title, 13, col, "middle", "bold")
        b += lines(x + 85, top + 124, rows, 10, INK, "middle", 14)
        if i < 3:
            b += arrow(x + 172, top + 80, x + 218, top + 80 - 40, ACCENT)
    b += box(60, 362, 830, 30, PANEL, ACCENT, 6)
    b += text(475, 382, "one flag, AUTH_MODE = off · token · local · sso — and one open route, /api/health, so the monitor keeps working", 11, INK, "middle", "bold", "ui-monospace,Menlo,Consolas,monospace")
    b += text(W/2, 412, "each rung keeps what the one below gave: tokens for scripts on every rung, a break-glass admin under single sign-on", 11, INK)
    b += text(W/2, 430, "everyday version: fit a lock this week, keep the key for the cleaners, and install the badge reader when the badge office delivers", 10.5, MUTED)
    write("fig_auth_ladder.svg", svg(W, H, "Three rungs from an open port to single sign-on: a token gate, local accounts, then the corporate identity provider; one feature flag; each rung keeps what the one below gave", b))

def fig_delete_gate() -> None:
    W, H = 940, 400
    b = text(W/2, 34, "Deleting a compound after CR-6: the clerk refuses, the archivist empties the folder first", 16, INK, "middle", "bold")
    # the compound with linked rows
    b += box(30, 90, 190, 150, PANEL, COLOURS["chemical"], 10)
    b += symbol("chemical", 70, 130, 16)
    b += lines(150, 124, ["CHEM-000042", "Phenol"], 11, INK, "middle", 15, "bold")
    for i in range(3):
        b += symbol("screening", 60 + i * 34, 190, 7)
    b += text(190, 194, "3 rows", 10.5, MUTED)
    b += text(125, 226, "measurements point at it", 10, MUTED)
    # left path: browser / plain API
    b += arrow(222, 130, 300, 130, LINE)
    b += box(302, 80, 290, 100, "#fff7ed", COLOURS["screening"], 8)
    b += text(447, 104, "browser · plain API", 13, COLOURS["screening"], "middle", "bold")
    b += lines(447, 126, ["REFUSED — 409", "\"3 screening rows linked; unlink them first\"", "nothing is changed"], 11, INK, "middle", 16)
    b += path_arrow("M 592 130 L 640 130", COLOURS["screening"], dash=True)
    b += box(642, 96, 270, 68, PAPER, COLOURS["screening"], 6)
    b += lines(777, 120, ["the person unlinks the rows", "on the Screening Data page, then deletes"], 10.5, INK, "middle", 15)
    # right path: forced API / script
    b += arrow(222, 200, 300, 260, LINE)
    b += box(302, 226, 290, 100, "#eef2ff", COLOURS["chemical"], 8)
    b += text(447, 250, "API with force=true · the script", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(447, 272, ["1  unlink every linked row", "2  then delete the entry", "always in that order; both counts reported"], 11, INK, "middle", 16)
    b += path_arrow("M 592 276 L 640 276", COLOURS["chemical"])
    b += box(642, 242, 270, 68, PAPER, COLOURS["chemical"], 6)
    b += lines(777, 266, ["the entry is gone; its rows keep their", "source names and point at nothing — no dangling link"], 10.5, INK, "middle", 15)
    b += text(W/2, 356, "a person clicking delete may not know rows are linked — refusing and saying so is the safe default;", 11, INK)
    b += text(W/2, 374, "a script that asked to force has said, in its own code, that it knows. Either way no row is ever left pointing at a missing entry.", 11, INK)
    b += text(W/2, 393, "everyday version: the filing clerk will not let you bin a folder with documents in it; the archivist with the master key empties it first, always", 10.5, MUTED)
    write("fig_delete_gate.svg", svg(W, H, "Deleting a compound with linked rows: the browser and the plain API refuse with 409 and send the person to unlink first; the forced API and the script unlink first, then delete", b))


def fig_every_way_in() -> None:
    W, H = 940, 400
    b = text(W/2, 34, "Every way into the Chemical Registry goes through one door", 16, INK, "middle", "bold")
    doors = [
        (60, "the browser", "screening", ["Chemical Registry →", "Upload Chemicals →", "JSON Upload (or Excel/CSV, SDF)"]),
        (290, "the API", "sample", ["curl -F file=@… to", "/upload/excel · /upload/sdf", "/upload/json · /import (body)"]),
        (520, "the terminal", "toxicology", ["./container-py.sh import", "chemicals <file>", "or import_file.py directly"]),
        (750, "the export", "chemical", ["./container-py.sh export", "chemicals <file.json>", "review it, load it back"]),
    ]
    for x, title, kind, rows in doors:
        b += box(x, 70, 160, 120, PAPER, COLOURS[kind], 10)
        b += text(x + 80, 94, title, 13, COLOURS[kind], "middle", "bold")
        b += lines(x + 80, 118, rows, 10.5, INK, "middle", 15)
        if title != "the export":
            b += path_arrow(f"M {x+80} 192 L {x+80} 222 L 470 222 L 470 244", COLOURS[kind])
        else:
            b += path_arrow(f"M 470 330 L 470 340 L {x+80} 340 L {x+80} 192", COLOURS[kind], dash=True)
    b += box(300, 246, 340, 84, "#eef2ff", COLOURS["chemical"], 10)
    b += text(470, 270, "backend/app/imports.py — one parser per format", 12.5, COLOURS["chemical"], "middle", "bold")
    b += lines(470, 292, [".json · .csv/.tsv · .xlsx/.xls · .sdf", "upsert by chemical_id · a missing CAS is a valid entry", "one report shape: inserted, updated, errors"], 10.5, INK, "middle", 14)
    b += text(W/2, 368, "whichever door a file arrives by, it is read by the same code — so the browser, a script and a curl command cannot disagree", 11, INK)
    b += text(W/2, 388, "everyday version: the shop has a front door, a delivery hatch and a phone line — but one stockroom, one stock list, one clerk", 10.5, MUTED)
    write("fig_every_way_in.svg", svg(W, H, "Browser, API, terminal and the export loop all reach the registry through one shared import module with one parser per format", b))


def fig_registry_sources() -> None:
    W, H = 940, 420
    b = text(W/2, 34, "Three real sources, one registry: each file is described as data, not parsed by hand", 16, INK, "middle", "bold")
    cards = [
        (40, "the Dotmatics export", COLOURS["screening"], ["a spreadsheet, 115 columns", "one row per BATCH of a compound", "rows sharing REG_ID → one entry", "batches folded into a list"], "keyed on REG_ID, merges on DTXSID"),
        (340, "the registry SDF", COLOURS["chemical"], ["V3000 structures, ~50 properties", "RDKit draws and checks each one", "same regulatory columns as the export", "merges with the export on DTXSID"], "the structure joins the identifiers"),
        (640, "the limited list", COLOURS["sample"], ["six columns", "NESTLE_ID = 'Coming from screening'", "registered now, identifier later", "a standing notice until then"], "matched on CAS, then name"),
    ]
    for x, title, col, rows, foot in cards:
        b += box(x, 66, 260, 150, PAPER, col, 10)
        b += text(x + 130, 90, title, 13, col, "middle", "bold")
        b += lines(x + 130, 114, rows, 10.5, INK, "middle", 15)
        b += text(x + 130, 200, foot, 10, MUTED)
        b += path_arrow(f"M {x+130} 218 L {x+130} 246 L 470 246 L 470 266", col)
    b += box(250, 268, 440, 80, "#eef2ff", COLOURS["chemical"], 10)
    b += text(470, 292, "registry_templates.py — a spec per source", 12.5, COLOURS["chemical"], "middle", "bold")
    b += lines(470, 312, ["fingerprint · group_by · match_order · promote · batch_fields", "promoted fields become the registry's own; EVERY column is kept under metadata"], 10.5, INK, "middle", 14)
    b += text(W/2, 376, "a shared CAS is kept and flagged · a batch that disagrees is flagged · a pending identifier is a notice — a person decides, the audit lists them", 11, INK)
    b += text(W/2, 398, "everyday version: three suppliers deliver in three kinds of crate; the stockroom has one form per crate type, and nothing on the delivery note is thrown away", 10.5, MUTED)
    write("fig_registry_sources.svg", svg(W, H, "The Dotmatics export, the registry SDF and the limited list, each described as a template spec, feeding one registry through the shared import module", b))


def fig_container_lunchbox() -> None:
    W, H = 940, 320
    b = text(W/2, 34, "The container is the isolation — the same sealed lunchbox on every platform", 16, INK, "middle", "bold")
    for i, host in enumerate(["macOS", "Windows (Docker Desktop / WSL 2)", "RHEL 8 VM (rootless podman)"]):
        x = 30 + i * 300
        b += box(x, 66, 280, 40, PANEL, LINE, 8)
        b += text(x + 140, 91, host, 12, ACCENT, "middle", "bold")
    b += box(230, 130, 480, 120, "#eef2ff", COLOURS["chemical"], 12, sw=2)
    b += text(470, 156, "crucible-py image", 14, COLOURS["chemical"], "middle", "bold")
    b += lines(470, 180, ["Python 3.12 · FastAPI · SQLAlchemy · RDKit · openpyxl", "the built React page · the Alembic migrations", "identical bytes on all three machines"], 11, INK, "middle", 17)
    b += box(30, 130, 170, 120, PAPER, COLOURS["sample"], 8)
    b += text(115, 154, "mounted IN", 12, COLOURS["sample"], "middle", "bold")
    b += lines(115, 176, ["data/crucible.db", "certs/ (read-only)", ".env.local values", "— stay on the host,", "never inside the image"], 10.5, MUTED, "middle", 15)
    b += arrow(202, 190, 228, 190, COLOURS["sample"])
    b += box(740, 130, 170, 120, PAPER, COLOURS["screening"], 8)
    b += text(825, 154, "answers OUT", 12, COLOURS["screening"], "middle", "bold")
    b += lines(825, 176, ["port 49160", "HTTP on a laptop,", "HTTPS in production", "(CRUCIBLE_PORT to change)"], 10.5, MUTED, "middle", 15)
    b += arrow(712, 190, 738, 190, COLOURS["screening"])
    b += text(W/2, 282, "no virtual environment for the app: the lunchbox already holds every library; backend/.venv exists only to run the tests outside it", 11, INK)
    b += text(W/2, 302, "delete the lunchbox and every trace of the app goes with it — your data, certificates and settings stay because they were never inside", 11, MUTED)
    write("fig_container_lunchbox.svg", svg(W, H, "One container image runs identically on macOS, Windows and RHEL 8; the database, certificates and settings are mounted in from the host and answers come out on port 49160", b))


def fig_setup_flow() -> None:
    W, H = 940, 230
    b = text(W/2, 34, "Set up once per machine, then a short loop forever", 16, INK, "middle", "bold")
    once = [("install the runtime", "podman or Docker"), ("clone", "the public repository"), ("one command", "./setup-after-clone-py.sh"), ("checklist", "V1–V7 / V1–V9")]
    x = 30
    for i, (t, sub) in enumerate(once):
        b += box(x, 70, 150, 56, PAPER, COLOURS["sample"], 8)
        b += text(x + 75, 92, t, 12, COLOURS["sample"], "middle", "bold")
        b += text(x + 75, 112, sub, 10, MUTED)
        if i < 3:
            b += arrow(x + 152, 98, x + 166, 98, LINE)
        x += 168
    b += text(30 + 2 * 168 + 75 - 84, 150, "ONCE — never again on this machine", 11, COLOURS["sample"], "middle", "bold")
    loop = [("edit", ""), ("test", "pytest"), ("rebuild", "if code changed"), ("verify", "curl · checklist"), ("publish", "gate → push → mirror")]
    b += arrow(706, 98, 722, 98, LINE)
    b += box(724, 62, 190, 74, "#eef2ff", COLOURS["chemical"], 10)
    b += text(819, 86, "the loop", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(819, 106, ["edit → test → rebuild →", "verify → publish"], 11, INK, "middle", 15)
    b += text(819, 150, "EVERY change, minutes each", 11, COLOURS["chemical"], "middle", "bold")
    b += text(W/2, 190, "the loop never needs the install guide again: it fits on the handbook's cheat sheet", 12, INK)
    b += text(W/2, 210, "everyday version: fit the kitchen once; after that, cooking is the same short routine every evening", 11, MUTED)
    write("fig_setup_flow.svg", svg(W, H, "Four one-time setup steps, then a five-step loop for every change", b))


def fig_timeline() -> None:
    W, H = 940, 260
    b = text(W/2, 34, "The story so far, on one line", 16, INK, "middle", "bold")
    b += f"<line x1='40' y1='130' x2='900' y2='130' stroke='{LINE}' stroke-width='2'/>\n"
    marks = [
        (60, "2026-05", ["Node.js", "prototype"], ACCENT, True),
        (190, "not recorded", ["Python rewrite", "same API"], COLOURS["chemical"], False),
        (310, "not recorded", ["PostgreSQL", "+ Alembic"], COLOURS["chemical"], True),
        (430, "2026-08-06", ["v2.0.0", "publishable"], COLOURS["sample"], False),
        (540, "2026-08-17→25", ["v2.0.x–2.1.0", "guides walked"], COLOURS["sample"], True),
        (660, "2026-08-25", ["v2.2.0", "real data"], COLOURS["screening"], False),
        (770, "2026-08-31", ["v2.2.1", "registry audited"], COLOURS["screening"], True),
        (880, "2026-09-07", ["v2.3 · v2.4", "handbook · CI"], COLOURS["toxicology"], False),
    ]
    for x, date, rows, col, up in marks:
        b += f"<circle cx='{x}' cy='130' r='7' fill='{col}'/>\n"
        ty = 80 if up else 168
        b += text(x, ty - 22 if up else ty + 40, date, 10, MUTED)
        b += lines(x, ty, rows, 11, INK, "middle", 15, "bold")
    b += text(W/2, 236, "phases 00–04 are reconstructed tutorials; 05 is this documentation; from v2.8 the plan runs as six tracks (05-roadmap.md)", 11, MUTED)
    write("fig_timeline.svg", svg(W, H, "Milestones from the Node prototype in May 2026 through the Python rewrite, publication, verification, real data, the audit and the handbook", b))


def fig_requirements_lock() -> None:
    W, H = 940, 330
    b = text(W/2, 34, "What you asked for, and what you got — why there is a lock file", 16, INK, "middle", "bold")
    b += box(40, 66, 330, 150, PAPER, COLOURS["sample"], 10)
    b += text(205, 92, "requirements.txt — the shopping list", 13, COLOURS["sample"], "middle", "bold")
    b += lines(205, 116, ["fastapi>=0.115,<1.0", "SQLAlchemy>=2.0,<3.0", "rdkit>=2024.3.1", "… 12 lines, ranges: the INTENT"], 11.5, INK, "middle", 17, "normal")
    b += text(205, 202, "edited by a person", 10.5, MUTED)
    b += arrow(372, 140, 428, 140, LINE)
    b += box(430, 100, 120, 80, PANEL, LINE, 8)
    b += lines(490, 126, ["pip resolves", "inside", "python:3.12"], 11, ACCENT, "middle", 15, "bold")
    b += text(490, 194, "./container-py.sh lock", 10, MUTED, "middle", "normal", "monospace")
    b += arrow(552, 140, 608, 140, LINE)
    b += box(610, 66, 300, 150, "#eef2ff", COLOURS["chemical"], 10)
    b += text(760, 92, "requirements.lock — the receipt", 13, COLOURS["chemical"], "middle", "bold")
    b += lines(760, 116, ["fastapi==0.141.1", "SQLAlchemy==2.0.x · rdkit==2025.9.3", "pydantic-core==… (a dependency's dependency)", "… 44 lines, exact: what was GOT"], 11.5, INK, "middle", 17, "normal")
    b += text(760, 202, "generated, never edited by hand", 10.5, MUTED)
    for i, (who, col) in enumerate([("Dockerfile → the image", COLOURS["toxicology"]), ("CI on Linux + macOS", COLOURS["screening"]), ("backend/.venv for tests", COLOURS["sample"])]):
        x = 130 + i * 300
        b += path_arrow(f"M 760 218 L 760 236 L {x+110} 236 L {x+110} 250", COLOURS["chemical"], dash=True) if i != 2 else path_arrow("M 760 218 L 760 250", COLOURS["chemical"], dash=True)
        b += box(x, 252, 220, 36, PAPER, col, 6)
        b += text(x + 110, 275, who, 11.5, col, "middle", "bold")
    b += text(W/2, 314, "everyday version: the list says “bread, milk”; the receipt says exactly which loaf and which carton — and everyone gets the same receipt", 11, MUTED)
    write("fig_requirements_lock.svg", svg(W, H, "requirements.txt states version ranges; pip resolves them inside the Python 3.12 image into requirements.lock with exact versions; the Dockerfile, CI and the test environment all install from the lock", b))


def cover() -> None:
    W, H = 1200, 300
    b = ("<defs><linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
         "<stop offset='0' stop-color='#1e1b4b'/><stop offset='1' stop-color='#312e81'/></linearGradient>"
         "<linearGradient id='bowl' x1='0' y1='0' x2='0' y2='1'>"
         "<stop offset='0' stop-color='#fcd34d'/><stop offset='1' stop-color='#f59e0b'/></linearGradient></defs>\n")
    b += f"<rect x='0' y='0' width='{W}' height='{H}' rx='16' fill='url(#bg)'/>\n"
    # the mark: a crucible with sparks
    b += "<path d='M 88 104 L 212 104 L 192 196 Q 150 218 108 196 Z' fill='url(#bowl)'/>\n"
    b += "<rect x='122' y='210' width='56' height='12' rx='3' fill='#f59e0b'/>\n"
    b += "<circle cx='150' cy='72' r='7' fill='#fde68a'/><circle cx='128' cy='56' r='4.5' fill='#fde68a'/><circle cx='174' cy='52' r='5.5' fill='#fde68a'/>\n"
    b += text(262, 120, "Crucible", 58, "#ffffff", "start", "bold")
    b += text(263, 162, "a chemical and sample registry for a research laboratory", 21, "#e0e7ff", "start")
    b += text(263, 194, "one identity per compound · every measurement attached to it · spreadsheets in, an API out", 15, "#c7d2fe", "start")
    b += text(263, 250, "one machine · one container · one database file · macOS · Windows · RHEL 8", 13, "#a5b4fc", "start")
    # record-type symbols on a light card so they read on the dark ground
    b += box(958, 206, 212, 74, "#f8fafc", "#f8fafc", 10)
    for i, kind in enumerate(["chemical", "sample", "screening", "toxicology"]):
        b += symbol(kind, 985 + i * 52, 236, 13)
    b += text(1064, 272, "chemical · sample · screening · toxicology", 10.5, "#1f2937")
    write("cover_crucible.svg", svg(W, H, "Crucible: a chemical and sample registry for a research laboratory", b).replace(f"fill='{PAPER}' stroke='#e5e7eb'", "fill='#1e1b4b' stroke='#1e1b4b'"))


def logo() -> None:
    W, H = 120, 120
    b = ("<defs><linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
         "<stop offset='0' stop-color='#1e1b4b'/><stop offset='1' stop-color='#312e81'/></linearGradient></defs>\n")
    b += f"<rect x='0' y='0' width='{W}' height='{H}' rx='20' fill='url(#bg)'/>\n"
    b += "<path d='M 25 40 L 95 40 L 84 92 Q 60 104 36 92 Z' fill='#fbbf24'/>\n"
    b += "<rect x='46' y='100' width='28' height='8' rx='2' fill='#f59e0b'/>\n"
    b += "<circle cx='60' cy='24' r='5' fill='#fde68a'/><circle cx='46' cy='14' r='3' fill='#fde68a'/><circle cx='75' cy='13' r='4' fill='#fde68a'/>\n"
    write("logo_crucible.svg", svg(W, H, "Crucible logo: a crucible with sparks", b).replace(f"fill='{PAPER}' stroke='#e5e7eb'", "fill='#1e1b4b' stroke='#1e1b4b'"))


if __name__ == "__main__":
    for f in (fig_record_types, fig_doc_is_truth, fig_machine_layout, fig_change_travels, fig_request_path,
              fig_two_stage, fig_tracks, fig_registry_first, fig_module_names, fig_auth_ladder, fig_delete_gate, fig_every_way_in, fig_registry_sources, fig_container_lunchbox, fig_setup_flow, fig_timeline,
              fig_requirements_lock, fig_attention_page, fig_source_tags, fig_two_instances, fig_publish_promote, fig_instance_name, fig_instance_label, fig_two_doors, fig_six_blocks, cover, logo):
        f()

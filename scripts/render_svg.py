"""Render every SVG asset from data/profile.json.

Design constraints that shaped this file:

* GitHub serves README images through a proxy, so there is no JavaScript and no
  external font or stylesheet. Everything is one self-contained SVG.
* Animation is CSS `@keyframes` inside the SVG. That works when the file is
  rendered as an <img>, which is how GitHub embeds it.
* Every animated property starts from its *authored* value and ends at the
  final state (`animation-fill-mode: both`), so a renderer that ignores the
  animation still shows the finished frame. Nothing is only visible mid-tween.
* `prefers-reduced-motion` disables all of it.
* Two themes are emitted per asset and paired with <picture> in the README.

Run:  python scripts/render_svg.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "profile.json")
ASSET_DIR = os.path.join(ROOT, "assets")

MONO = ("ui-monospace,'SF Mono','Cascadia Code','Roboto Mono',"
        "Menlo,Consolas,'Liberation Mono',monospace")
SANS = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,"
        "'Helvetica Neue',Arial,sans-serif")

# GitHub's own palette, so the assets sit naturally in both themes.
THEMES = {
    "dark": {
        "bg0": "#0d1117", "bg1": "#0b0f14", "panel": "#10151c",
        "border": "#232b36", "grid": "#161c24", "rule": "#1c232d",
        "fg": "#e6edf3", "fg2": "#9198a1", "fg3": "#636c76",
        "accent": "#58a6ff", "green": "#3fb950", "amber": "#d29922",
        "muted": "#6e7681", "violet": "#a371f7",
        "cell0": "#161b22", "shadow": "0.35",
    },
    "light": {
        "bg0": "#ffffff", "bg1": "#f6f8fa", "panel": "#ffffff",
        "border": "#d1d9e0", "grid": "#eaeef2", "rule": "#e4e8ed",
        "fg": "#1f2328", "fg2": "#59636e", "fg3": "#818b98",
        "accent": "#0969da", "green": "#1a7f37", "amber": "#9a6700",
        "muted": "#6e7781", "violet": "#8250df",
        "cell0": "#eff2f5", "shadow": "0.10",
    },
}

STATUS_COLOR = {
    config.STATUS_ACTIVE: "green",
    config.STATUS_IMPROVING: "amber",
    config.STATUS_EXPLORING: "accent",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def e(value) -> str:
    return escape(str(value))


def mono_width(text: str, size: float) -> float:
    """Monospace advance is a reliable 0.6em; used for chip and box widths."""
    return len(text) * size * 0.6


def clip(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def svg_open(width: int, height: int, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-labelledby="t">\n  <title id="t">{e(title)}</title>\n'
    )


BASE_CSS = """
    text {{ font-family: {sans}; }}
    .m {{ font-family: {mono}; }}
    .fg {{ fill: {fg}; }} .fg2 {{ fill: {fg2}; }} .fg3 {{ fill: {fg3}; }}
    .ac {{ fill: {accent}; }} .gr {{ fill: {green}; }} .am {{ fill: {amber}; }}
    .b {{ font-weight: 650; }}
    .card {{ fill: {panel}; stroke: {border}; stroke-width: 1; }}
    .rule {{ stroke: {rule}; stroke-width: 1; }}
    .wire {{ fill: none; stroke: {border}; stroke-width: 1.25; }}
    .flow {{ fill: none; stroke: {accent}; stroke-width: 1.25;
             stroke-opacity: .5; stroke-dasharray: 3 7;
             animation: flow 1.9s linear infinite; }}
    @keyframes flow {{ to {{ stroke-dashoffset: -20; }} }}
    .rise {{ opacity: 1; animation: rise .7s cubic-bezier(.2,.7,.3,1) both; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }}
                       to   {{ opacity: 1; transform: translateY(0); }} }}
    .fade {{ opacity: 1; animation: fade .8s ease-out both; }}
    @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .pulse {{ animation: pulse 2.8s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100% {{ opacity: .95; }} 50% {{ opacity: .35; }} }}
    .halo {{ animation: halo 2.8s ease-in-out infinite; }}
    @keyframes halo {{ 0% {{ r: 4; opacity: .55; }}
                       70%,100% {{ r: 11; opacity: 0; }} }}
    .draw {{ stroke-dasharray: 1200; stroke-dashoffset: 0;
             animation: draw 1.6s ease-out both; }}
    @keyframes draw {{ from {{ stroke-dashoffset: 1200; }}
                       to {{ stroke-dashoffset: 0; }} }}
    .caret {{ animation: caret 1.05s steps(1) infinite; }}
    @keyframes caret {{ 0%,49% {{ opacity: 1; }} 50%,100% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .flow, .rise, .fade, .pulse, .halo, .draw, .caret, .sweep, .typer, .dot
        {{ animation: none !important; }}
      .halo {{ opacity: 0; }}
    }}
"""


def style_block(theme: dict, extra: str = "") -> str:
    css = BASE_CSS.format(sans=SANS, mono=MONO, **theme) + extra
    return "  <style>\n" + css + "\n  </style>\n"


def defs(theme: dict, width: int, height: int, extra: str = "") -> str:
    """Panel background, hairline dot grid and a slow top-edge light sweep."""
    return f"""  <defs>
    <linearGradient id="pg" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="{theme['bg0']}"/>
      <stop offset="1" stop-color="{theme['bg1']}"/>
    </linearGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{theme['accent']}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{theme['accent']}" stop-opacity=".9"/>
      <stop offset="1" stop-color="{theme['accent']}" stop-opacity="0"/>
    </linearGradient>
    <pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">
      <circle cx="1" cy="1" r="1" fill="{theme['grid']}"/>
    </pattern>
{extra}  </defs>
  <rect width="{width}" height="{height}" rx="10" fill="url(#pg)"/>
  <rect width="{width}" height="{height}" rx="10" fill="url(#dots)"/>
  <rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="9.5"
        fill="none" stroke="{theme['border']}"/>
  <g clip-path="inset(0 round 10px)">
    <rect class="sweep" x="-320" y="0" width="320" height="1.5" fill="url(#sweep)"/>
  </g>
"""


SWEEP_CSS = """
    .sweep {{ animation: sweep 7s cubic-bezier(.4,0,.2,1) infinite; }}
    @keyframes sweep {{ 0% {{ transform: translateX(0); }}
                        60%,100% {{ transform: translateX({dist}px); }} }}
"""


def section_head(label: str, right: str, width: int, theme: dict, y: int = 30) -> str:
    out = (
        f'  <text class="m b fg2" x="22" y="{y}" font-size="11.5" '
        f'letter-spacing="2.4">{e(label.upper())}</text>\n'
    )
    if right:
        out += (
            f'  <text class="m fg3" x="{width - 22}" y="{y}" font-size="10.5" '
            f'text-anchor="end">{e(right)}</text>\n'
        )
    out += f'  <line class="rule" x1="22" y1="{y + 12}" x2="{width - 22}" y2="{y + 12}"/>\n'
    return out


def chip(x: float, y: float, label: str, theme: dict, size: float = 9.5,
         color: str = "fg3", pad: float = 7) -> tuple[str, float]:
    """Small outlined tag. Returns (markup, width)."""
    w = mono_width(label, size) + pad * 2
    markup = (
        f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="17" rx="4" '
        f'fill="none" stroke="{theme["border"]}"/>\n'
        f'  <text class="m {color}" x="{x + pad:.1f}" y="{y + 12:.1f}" '
        f'font-size="{size}">{e(label)}</text>\n'
    )
    return markup, w


def status_dot(x: float, y: float, color: str, theme: dict, delay: float = 0) -> str:
    """Filled dot with an expanding halo, used for live status."""
    fill = theme[color]
    return (
        f'  <circle class="halo" cx="{x}" cy="{y}" r="4" fill="{fill}" '
        f'style="animation-delay:{delay}s"/>\n'
        f'  <circle class="pulse" cx="{x}" cy="{y}" r="3.2" fill="{fill}" '
        f'style="animation-delay:{delay}s"/>\n'
    )


def write(name: str, markup: str) -> None:
    os.makedirs(ASSET_DIR, exist_ok=True)
    path = os.path.join(ASSET_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(markup)


# ---------------------------------------------------------------------------
# 1. hero
# ---------------------------------------------------------------------------

def hero(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    W, H = 1000, 246
    ident = data["identity"]
    act = data["activity"]
    contrib = act.get("contributions")

    subline = ident["subline"]
    type_w = mono_width(subline, 13) + 4

    facts = [
        f"{act['tracked_repos']} repositories",
        f"{act['technologies_detected']} technologies detected",
        f"{act['active_repos_30d']} active in {config.ACTIVE_WINDOW_DAYS}d",
    ]
    if contrib:
        facts.insert(0, f"{contrib['total']:,} contributions / 365d")

    extra = SWEEP_CSS.format(dist=W + 320) + f"""
    .typer {{ animation: typer 2.2s steps(48,end) .35s both; }}
    @keyframes typer {{ from {{ width: 0; }} to {{ width: {type_w:.0f}px; }} }}
    .dot {{ animation: run 3.4s cubic-bezier(.45,0,.55,1) infinite; }}
    @keyframes run {{ 0% {{ cx: 706; opacity: 0; }} 8% {{ opacity: 1; }}
                      92% {{ opacity: 1; }} 100% {{ cx: 946; opacity: 0; }} }}
"""

    out = svg_open(W, H, f"{data['user']['name']} - {ident['tagline']}")
    out += style_block(th, extra)
    out += defs(th, W, H)

    # left column ----------------------------------------------------------
    out += (f'  <rect class="rise" x="22" y="40" width="3" height="34" rx="1.5" '
            f'fill="{th["accent"]}"/>\n')
    out += (f'  <text class="b rise" x="40" y="68" font-size="34" fill="{th["fg"]}" '
            f'letter-spacing="1.5" style="animation-delay:.05s">'
            f'{e(data["user"]["name"].upper())}</text>\n')
    out += (f'  <text class="m rise" x="41" y="95" font-size="12.5" fill="{th["accent"]}" '
            f'letter-spacing="1.2" style="animation-delay:.12s">'
            f'{e(ident["tagline"].lower())}</text>\n')

    # typed subline, revealed by an expanding mask
    out += '  <defs>\n    <mask id="typemask">\n'
    out += (f'      <rect class="typer" x="41" y="112" width="{type_w:.0f}" '
            f'height="22" fill="#fff"/>\n')
    out += '    </mask>\n  </defs>\n'
    out += '  <g mask="url(#typemask)">\n'
    out += (f'    <text class="m" x="41" y="128" font-size="13" fill="{th["fg2"]}">'
            f'{e(subline)}</text>\n  </g>\n')
    out += (f'  <rect class="caret" x="{41 + type_w:.0f}" y="117" width="7" height="14" '
            f'fill="{th["accent"]}" style="animation-delay:2.6s"/>\n')

    rule_end = max(640, 41 + type_w + 24)
    out += f'  <line class="rule" x1="41" y1="156" x2="{rule_end:.0f}" y2="156"/>\n'

    x = 41.0
    for i, fact in enumerate(facts):
        markup, w = chip(x, 172, fact, th, 10, "fg2")
        out += markup.replace('<rect x=', '<rect class="rise" style="animation-delay:'
                              f'{0.2 + i * 0.07:.2f}s" x=', 1)
        x += w + 8

    link_line = " / ".join(
        "{}: {}".format(name, url.split("://")[-1]) for name, url in ident["links"]
    )
    out += (f'  <text class="m fg3" x="41" y="216" font-size="10">'
            f'{e(link_line)}</text>\n')

    # right column: request pipeline glyph ---------------------------------
    nodes = [("client", 706), ("api", 786), ("worker", 866), ("store", 946)]
    out += f'  <g class="fade" style="animation-delay:.5s">\n'
    out += (f'    <text class="m fg3" x="{W - 22}" y="68" font-size="9.5" '
            f'text-anchor="end" letter-spacing="1.6">REQUEST PATH</text>\n')
    out += f'    <path class="wire" d="M706 96 H946"/>\n'
    out += f'    <path class="flow" d="M706 96 H946"/>\n'
    for i, (label, cx) in enumerate(nodes):
        out += (f'    <rect x="{cx - 26}" y="82" width="52" height="28" rx="6" '
                f'fill="{th["panel"]}" stroke="{th["border"]}"/>\n')
        out += (f'    <text class="m fg2" x="{cx}" y="100" font-size="8.5" '
                f'text-anchor="middle">{e(label)}</text>\n')
    out += (f'    <circle class="dot" cx="706" cy="96" r="3" fill="{th["accent"]}"/>\n')
    out += (f'    <circle class="dot" cx="706" cy="96" r="3" fill="{th["green"]}" '
            f'style="animation-delay:1.7s"/>\n')
    out += (f'    <text class="m fg3" x="826" y="132" font-size="9" '
            f'text-anchor="middle">queue work off the request path</text>\n')
    out += '  </g>\n'

    # a small real-data sparkline of recent push days
    pushes = act.get("recent_pushes") or []
    if pushes:
        by_day: dict[str, int] = {}
        for push in pushes:
            by_day[push["at"][:10]] = by_day.get(push["at"][:10], 0) + 1
        days = sorted(by_day)[-14:]
        peak = max(by_day[d] for d in days) or 1
        bar_w, gap = 12, 5
        base_x = W - 22 - (len(days) * (bar_w + gap) - gap)
        out += f'  <g class="fade" style="animation-delay:.7s">\n'
        out += (f'    <text class="m fg3" x="{W - 22}" y="176" font-size="9" '
                f'text-anchor="end" letter-spacing="1.4">RECENT PUSH DAYS</text>\n')
        for i, day in enumerate(days):
            h = 6 + (by_day[day] / peak) * 26
            bx = base_x + i * (bar_w + gap)
            out += (f'    <rect x="{bx:.1f}" y="{216 - h:.1f}" width="{bar_w}" '
                    f'height="{h:.1f}" rx="2" fill="{th["accent"]}" '
                    f'fill-opacity="{0.30 + 0.55 * by_day[day] / peak:.2f}"/>\n')
        out += '  </g>\n'

    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 2. currently building
# ---------------------------------------------------------------------------

def currently_building(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    items = data["currently_building"][:3]
    W = 1000
    CARD_H = 152
    H = 56 + CARD_H + 18

    out = svg_open(W, H, "Currently building")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320))
    out += defs(th, W, H)
    out += section_head("currently building", f"live from push activity", W, th)

    card_w = (W - 20 - 2 * 16 - 20) / 3
    for i, item in enumerate(items):
        x = 20 + i * (card_w + 16)
        y = 56
        color = STATUS_COLOR.get(item["status"], "accent")
        out += (f'  <g class="rise" style="animation-delay:{0.08 * i:.2f}s">\n')
        out += (f'    <rect class="card" x="{x:.1f}" y="{y}" width="{card_w:.1f}" '
                f'height="{CARD_H}" rx="9"/>\n')
        out += (f'    <rect x="{x:.1f}" y="{y}" width="3" height="{CARD_H}" rx="1.5" '
                f'fill="{th[color]}" fill-opacity=".8"/>\n')

        out += status_dot(x + 22, y + 24, color, th, 0.35 * i).replace("  <", "    <")
        out += (f'    <text class="m b" x="{x + 34:.1f}" y="{y + 28}" font-size="9.5" '
                f'fill="{th[color]}" letter-spacing="1.5">'
                f'{e(item["status"].upper())}</text>\n')
        age = item["days_since_push"]
        age_txt = "today" if age == 0 else f"{age}d ago"
        out += (f'    <text class="m fg3" x="{x + card_w - 14:.1f}" y="{y + 28}" '
                f'font-size="9.5" text-anchor="end">{e(age_txt)}</text>\n')

        out += (f'    <text class="b" x="{x + 20:.1f}" y="{y + 56}" font-size="16" '
                f'fill="{th["fg"]}">{e(clip(item["repo"], 24))}</text>\n')

        words, line, lines = item["description"].split(), "", []
        limit = int((card_w - 40) / (10.5 * 0.53))
        for word in words:
            trial = (line + " " + word).strip()
            if len(trial) > limit and line:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
        for j, text_line in enumerate(lines[:3]):
            out += (f'    <text x="{x + 20:.1f}" y="{y + 78 + j * 15}" font-size="10.5" '
                    f'fill="{th["fg2"]}">{e(text_line)}</text>\n')

        cx = x + 20
        for tech in item["tech"][:3]:
            markup, w = chip(cx, y + CARD_H - 34, tech, th, 9, "fg3")
            if cx + w > x + card_w - 14:
                break
            out += markup.replace("  <", "    <")
            cx += w + 6
        out += '  </g>\n'

    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 3. system map
# ---------------------------------------------------------------------------

def system_map(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    smap = data["system_map"]
    branches = smap["branches"]
    W, H = 1000, 418

    out = svg_open(W, H, "Developer system map")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320) + """
    .node { animation: node 3.6s ease-in-out infinite; }
    @keyframes node { 0%,100% { stroke-opacity: 1; } 50% { stroke-opacity: .45; } }
""")
    out += defs(th, W, H)
    out += section_head("developer system map", "derived from repository contents", W, th)

    root_w, root_h = 210, 36
    root_x, root_y = (W - root_w) / 2, 58
    bus_y = 126
    box_y, box_h = 142, 34
    leaf_y0 = 200
    bus2_y = 276
    sink_w, sink_h = 300, 40
    sink_x, sink_y = (W - sink_w) / 2, 300

    span = W - 2 * 44
    col_w = span / len(branches)
    centers = [44 + col_w * (i + 0.5) for i in range(len(branches))]
    box_w = min(col_w - 18, 178)

    # root ------------------------------------------------------------------
    out += (f'  <rect class="card fade" x="{root_x}" y="{root_y}" width="{root_w}" '
            f'height="{root_h}" rx="8"/>\n')
    out += (f'  <text class="m b" x="{W / 2}" y="{root_y + 23}" font-size="11.5" '
            f'text-anchor="middle" fill="{th["fg"]}" letter-spacing="2">'
            f'{e(smap["root"])}</text>\n')

    # root -> bus -> columns ------------------------------------------------
    out += (f'  <path class="wire draw" d="M{W / 2} {root_y + root_h} V{bus_y} '
            f'H{centers[0]:.1f} M{centers[0]:.1f} {bus_y} H{centers[-1]:.1f}"/>\n')
    out += (f'  <path class="flow" d="M{W / 2} {root_y + root_h} V{bus_y}"/>\n')
    for i, cx in enumerate(centers):
        out += (f'  <path class="wire" d="M{cx:.1f} {bus_y} V{box_y}"/>\n')
        out += (f'  <path class="flow" d="M{cx:.1f} {bus_y} V{box_y}" '
                f'style="animation-delay:{0.18 * i:.2f}s"/>\n')
        out += (f'  <circle cx="{cx:.1f}" cy="{bus_y}" r="2.6" fill="{th["accent"]}" '
                f'fill-opacity=".75"/>\n')

    for i, (branch, cx) in enumerate(zip(branches, centers)):
        bx = cx - box_w / 2
        delay = 0.1 + 0.08 * i
        out += f'  <g class="rise" style="animation-delay:{delay:.2f}s">\n'
        out += (f'    <rect class="card node" x="{bx:.1f}" y="{box_y}" '
                f'width="{box_w:.1f}" height="{box_h}" rx="7" '
                f'style="animation-delay:{0.4 * i:.2f}s"/>\n')
        label = clip(branch["name"], int(box_w / 6.4))
        out += (f'    <text class="m b" x="{cx:.1f}" y="{box_y + 22}" font-size="9.8" '
                f'text-anchor="middle" fill="{th["fg"]}" letter-spacing="1.1">'
                f'{e(label)}</text>\n')

        for j, leaf in enumerate(branch["leaves"]):
            ly = leaf_y0 + j * 22
            out += (f'    <circle class="pulse" cx="{cx - box_w / 2 + 10:.1f}" cy="{ly - 4}" '
                    f'r="2" fill="{th["accent"]}" '
                    f'style="animation-delay:{0.3 * (i + j):.2f}s"/>\n')
            out += (f'    <text class="m" x="{cx - box_w / 2 + 20:.1f}" y="{ly}" '
                    f'font-size="10" fill="{th["fg2"]}">'
                    f'{e(clip(leaf, int(box_w / 5.6)))}</text>\n')

        out += (f'    <text class="m fg3" x="{cx - box_w / 2 + 20:.1f}" y="{leaf_y0 + 74}" '
                f'font-size="8.5">{e(str(len(branch["evidence"])))} repos</text>\n')
        out += (f'    <path class="wire" d="M{cx:.1f} {leaf_y0 + 84} V{bus2_y}"/>\n')
        out += '  </g>\n'

    # columns -> bus -> sink ------------------------------------------------
    out += (f'  <path class="wire draw" d="M{centers[0]:.1f} {bus2_y} '
            f'H{centers[-1]:.1f}" style="animation-delay:.3s"/>\n')
    out += (f'  <path class="wire" d="M{W / 2} {bus2_y} V{sink_y}"/>\n')
    out += (f'  <path class="flow" d="M{W / 2} {bus2_y} V{sink_y}"/>\n')

    out += (f'  <rect class="card fade" x="{sink_x}" y="{sink_y}" width="{sink_w}" '
            f'height="{sink_h}" rx="8" style="animation-delay:.45s"/>\n')
    out += (f'  <rect x="{sink_x}" y="{sink_y}" width="{sink_w}" height="2" rx="1" '
            f'fill="{th["green"]}" fill-opacity=".7"/>\n')
    out += (f'  <text class="m b" x="{W / 2}" y="{sink_y + 25}" font-size="11.5" '
            f'text-anchor="middle" fill="{th["fg"]}" letter-spacing="2">'
            f'{e(smap["sink"])}</text>\n')

    platforms = [
        item["name"] for item in data["tech_by_category"].get("Infrastructure", [])
        if item["name"] in ("Render", "Vercel", "Fly.io", "Docker", "Kubernetes")
    ]
    if platforms:
        out += (f'  <text class="m fg3" x="{W / 2}" y="{sink_y + 62}" font-size="9.5" '
                f'text-anchor="middle" letter-spacing=".6">'
                f'{e("  ".join(platforms))}</text>\n')

    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 4. activity dashboard
# ---------------------------------------------------------------------------

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def activity(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    act = data["activity"]
    contrib = act.get("contributions")
    W, H = 1000, 318
    synced = data["generated_at"][:10]

    out = svg_open(W, H, "Developer activity")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320) + """
    .cell { animation: cellin .5s ease-out both; }
    @keyframes cellin { from { opacity: 0; } to { opacity: 1; } }
    .bar { animation: grow .9s cubic-bezier(.2,.7,.3,1) both; }
    @keyframes grow { from { opacity: .2; } to { opacity: 1; } }
""")
    out += defs(th, W, H)
    out += section_head("developer activity", f"synced {synced}", W, th)

    ramp = [th["cell0"], th["accent"], th["accent"], th["accent"], th["accent"]]
    opac = [1, 0.28, 0.5, 0.72, 1]

    grid_x, grid_y = 34, 78
    cell, gap = 9, 2.6
    step = cell + gap

    if contrib and contrib.get("weeks"):
        weeks = contrib["weeks"][-53:]
        peak = max((max(w) for w in weeks if w), default=1) or 1

        out += (f'  <text class="m fg3" x="22" y="{grid_y - 12}" font-size="9" '
                f'letter-spacing="1.4">CONTRIBUTIONS / LAST 365 DAYS</text>\n')

        start = dt.date.fromisoformat(synced) - dt.timedelta(days=7 * (len(weeks) - 1))
        last_month = None
        for wi in range(len(weeks)):
            month = (start + dt.timedelta(days=7 * wi)).strftime("%b")
            if month != last_month and wi % 4 == 0:
                out += (f'  <text class="m fg3" x="{grid_x + wi * step:.1f}" '
                        f'y="{grid_y - 2}" font-size="8">{month}</text>\n')
                last_month = month
        for di, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            out += (f'  <text class="m fg3" x="{grid_x - 6}" '
                    f'y="{grid_y + di * step + 7.5:.1f}" font-size="7.5" '
                    f'text-anchor="end">{label}</text>\n')

        for wi, week in enumerate(weeks):
            for di, count in enumerate(week):
                if count == 0:
                    level = 0
                else:
                    level = min(4, 1 + int(3 * count / max(peak, 1)))
                out += (f'  <rect class="cell" x="{grid_x + wi * step:.1f}" '
                        f'y="{grid_y + di * step:.1f}" width="{cell}" height="{cell}" '
                        f'rx="2" fill="{ramp[level]}" fill-opacity="{opac[level]}" '
                        f'style="animation-delay:{0.004 * wi:.3f}s"/>\n')

        legend_x = grid_x
        out += (f'  <text class="m fg3" x="{legend_x}" y="{grid_y + 7 * step + 18:.1f}" '
                f'font-size="8.5">less</text>\n')
        for level in range(5):
            out += (f'  <rect x="{legend_x + 30 + level * 13:.1f}" '
                    f'y="{grid_y + 7 * step + 9:.1f}" width="9" height="9" rx="2" '
                    f'fill="{ramp[level]}" fill-opacity="{opac[level]}"/>\n')
        out += (f'  <text class="m fg3" x="{legend_x + 99}" '
                f'y="{grid_y + 7 * step + 18:.1f}" font-size="8.5">more</text>\n')
        kpi_y0 = 78
    else:
        # No token available: say so rather than draw an empty year.
        out += (f'  <text class="m fg3" x="22" y="{grid_y - 12}" font-size="9" '
                f'letter-spacing="1.4">CONTRIBUTION CALENDAR</text>\n')
        out += (f'  <rect x="34" y="{grid_y}" width="560" height="86" rx="8" '
                f'fill="none" stroke="{th["border"]}" stroke-dasharray="4 4"/>\n')
        out += (f'  <text class="m fg3" x="314" y="{grid_y + 40}" font-size="10.5" '
                f'text-anchor="middle">calendar populates on the next scheduled sync'
                f'</text>\n')
        out += (f'  <text class="m fg3" x="314" y="{grid_y + 58}" font-size="9" '
                f'text-anchor="middle">(needs GITHUB_TOKEN, supplied by the workflow)'
                f'</text>\n')
        kpi_y0 = 78

    # KPI column ------------------------------------------------------------
    kpis = [
        (f"{act['public_repos']}", "public repos"),
        (f"{act['active_repos_30d']}", f"active / {config.ACTIVE_WINDOW_DAYS}d"),
        (f"{act['technologies_detected']}", "technologies"),
        (f"{act['languages_detected']}", "languages"),
    ]
    if contrib:
        kpis = [
            (f"{contrib['total']:,}", "contributions / 365d"),
            (f"{contrib['commits']:,}", "commits / 365d"),
            (f"{act['public_repos']}", "public repos"),
            (f"{act['active_repos_30d']}", f"active / {config.ACTIVE_WINDOW_DAYS}d"),
        ]

    kx, kw = 646, 164
    for i, (value, label) in enumerate(kpis):
        col, row = i % 2, i // 2
        x = kx + col * (kw + 12)
        y = kpi_y0 + row * 56
        out += (f'  <g class="rise" style="animation-delay:{0.1 + 0.06 * i:.2f}s">\n')
        out += (f'    <rect class="card" x="{x}" y="{y}" width="{kw}" height="46" '
                f'rx="7"/>\n')
        out += (f'    <text class="m b" x="{x + 12}" y="{y + 26}" font-size="20" '
                f'fill="{th["fg"]}">{e(value)}</text>\n')
        out += (f'    <text class="m fg3" x="{x + 12}" y="{y + 40}" font-size="9">'
                f'{e(label)}</text>\n')
        out += '  </g>\n'

    # language distribution -------------------------------------------------
    langs = [l for l in data["language_share"] if l["pct"] >= 1.0][:6]
    bar_y = 228
    out += (f'  <text class="m fg3" x="22" y="{bar_y - 10}" font-size="9" '
            f'letter-spacing="1.4">LANGUAGE SHARE BY BYTES</text>\n')
    excluded = data.get("language_share_note", {}).get("excluded_repos") or []
    if excluded:
        noun = "repo" if len(excluded) == 1 else "repos"
        out += (f'  <text class="m fg3" x="{W - 22}" y="{bar_y - 10}" font-size="8.5" '
                f'text-anchor="end">{len(excluded)} {noun} with vendored deps excluded'
                f'</text>\n')

    palette = [th["accent"], th["green"], th["violet"], th["amber"],
               th["fg2"], th["muted"]]
    total = sum(l["pct"] for l in langs) or 1
    bx, bw = 22.0, float(W - 44)
    for i, lang in enumerate(langs):
        seg = bw * lang["pct"] / total
        out += (f'  <rect class="bar" x="{bx:.1f}" y="{bar_y}" width="{max(seg - 2, 2):.1f}" '
                f'height="14" rx="3" fill="{palette[i % len(palette)]}" '
                f'fill-opacity=".85" style="animation-delay:{0.1 + 0.07 * i:.2f}s"/>\n')
        bx += seg

    lx = 22.0
    for i, lang in enumerate(langs):
        out += (f'  <circle cx="{lx + 4:.1f}" cy="{bar_y + 36}" r="4" '
                f'fill="{palette[i % len(palette)]}" fill-opacity=".85"/>\n')
        label = f'{lang["name"]} {lang["pct"]:.0f}%'
        out += (f'  <text class="m fg2" x="{lx + 14:.1f}" y="{bar_y + 39}" '
                f'font-size="10">{e(label)}</text>\n')
        lx += 14 + mono_width(label, 10) + 22

    last = act.get("last_push") or {}
    if last.get("repo"):
        note = "last push  {}  ->  {}".format(last["at"], last["repo"])
        out += (f'  <text class="m fg3" x="22" y="{H - 14}" font-size="9.5">'
                f'{e(note)}</text>\n')
    window = act.get("event_window") or {}
    if window.get("from"):
        note = "{} push events  {} .. {}".format(
            window["push_events"], window["from"], window["to"])
        out += (f'  <text class="m fg3" x="{W - 22}" y="{H - 14}" font-size="9.5" '
                f'text-anchor="end">{e(note)}</text>\n')

    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 5. timeline
# ---------------------------------------------------------------------------

def timeline(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    years = data["timeline"]
    rows: list[tuple[str, dict | None]] = []
    for block in years:
        rows.append(("year", {"year": block["year"]}))
        for entry in block["entries"]:
            rows.append(("entry", entry))

    W = 1000
    top = 62
    H = top + sum(30 if kind == "entry" else 34 for kind, _ in rows) + 52
    spine_x = 132

    out = svg_open(W, H, "Developer timeline")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320) + f"""
    .spine {{ stroke-dasharray: {H}; animation: spine 1.8s ease-out both; }}
    @keyframes spine {{ from {{ stroke-dashoffset: {H}; }}
                        to {{ stroke-dashoffset: 0; }} }}
    .slide {{ animation: slide .6s cubic-bezier(.2,.7,.3,1) both; }}
    @keyframes slide {{ from {{ opacity: 0; transform: translateX(-8px); }}
                        to {{ opacity: 1; transform: translateX(0); }} }}
""")
    out += defs(th, W, H)
    out += section_head("developer timeline", "from repository create / push dates",
                        W, th)

    out += (f'  <path class="wire spine" d="M{spine_x} {top - 8} V{H - 34}" '
            f'stroke-width="1.5"/>\n')

    y = top
    delay = 0.0
    for kind, item in rows:
        delay += 0.05
        if kind == "year":
            out += (f'  <g class="slide" style="animation-delay:{delay:.2f}s">\n')
            out += (f'    <text class="m b" x="{spine_x - 24}" y="{y + 6}" '
                    f'font-size="15" text-anchor="end" fill="{th["fg"]}" '
                    f'letter-spacing="1">{e(item["year"])}</text>\n')
            out += (f'    <rect x="{spine_x - 5}" y="{y - 4}" width="10" height="10" '
                    f'rx="2" fill="{th["accent"]}"/>\n')
            out += (f'    <line class="rule" x1="{spine_x + 18}" y1="{y + 1}" '
                    f'x2="{W - 24}" y2="{y + 1}"/>\n  </g>\n')
            y += 34
            continue

        kinds = {"started": ("started", "accent"), "advanced": ("advanced", "green")}
        verb, color = kinds.get(item["kind"], ("touched", "muted"))
        out += (f'  <g class="slide" style="animation-delay:{delay:.2f}s">\n')
        out += (f'    <text class="m fg3" x="{spine_x - 24}" y="{y + 4}" font-size="9.5" '
                f'text-anchor="end">{e(item["date"][5:])}</text>\n')
        out += (f'    <circle cx="{spine_x}" cy="{y}" r="3.4" fill="{th["panel"]}" '
                f'stroke="{th[color]}" stroke-width="1.6"/>\n')
        out += (f'    <path class="wire" d="M{spine_x + 6} {y} H{spine_x + 22}"/>\n')
        out += (f'    <text class="m b" x="{spine_x + 30}" y="{y + 4}" font-size="9" '
                f'fill="{th[color]}" letter-spacing="1.1">{e(verb.upper())}</text>\n')
        out += (f'    <text class="m" x="{spine_x + 108}" y="{y + 4}" font-size="11.5" '
                f'fill="{th["fg"]}">{e(item["repo"])}</text>\n')
        desc = config.SHORT_DESC.get(item["repo"], "")
        if desc:
            out += (f'    <text x="{spine_x + 108 + mono_width(item["repo"], 11.5) + 18:.0f}" '
                    f'y="{y + 4}" font-size="10" fill="{th["fg3"]}">'
                    f'{e(clip(desc, 58))}</text>\n')
        out += '  </g>\n'
        y += 30

    live = data["currently_building"][:1]
    if live:
        item = live[0]
        out += (f'  <g class="slide" style="animation-delay:{delay + 0.1:.2f}s">\n')
        out += (f'    <text class="m b fg2" x="{spine_x - 24}" y="{y + 6}" font-size="10" '
                f'text-anchor="end" letter-spacing="1.4">NOW</text>\n')
        out += status_dot(spine_x, y + 1, "green", th).replace("  <", "    <")
        out += (f'    <path class="wire" d="M{spine_x + 8} {y + 1} H{spine_x + 22}"/>\n')
        out += (f'    <text class="m" x="{spine_x + 30}" y="{y + 5}" font-size="11.5" '
                f'fill="{th["fg"]}">{e(item["repo"])}</text>\n')
        out += (f'    <text x="{spine_x + 30 + mono_width(item["repo"], 11.5) + 18:.0f}" '
                f'y="{y + 5}" font-size="10.5" fill="{th["fg2"]}">'
                f'{e(clip(item["description"], 66))}</text>\n')
        out += '  </g>\n'

    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 6. terminal
# ---------------------------------------------------------------------------

def terminal_lines(data: dict) -> list[tuple[str, str]]:
    """(kind, text) pairs. Every value here comes from the fetched data."""
    act = data["activity"]
    lines: list[tuple[str, str]] = []

    lines.append(("cmd", "whoami"))
    lines.append(("out", f'{data["user"]["login"]}  ({data["identity"]["tagline"]})'))
    lines.append(("gap", ""))

    lines.append(("cmd", "ls domains/"))
    names = [b["name"].lower().replace(" / ", "-").replace(" & ", "-").replace(" ", "-")
             for b in data["system_map"]["branches"]]
    for i in range(0, len(names), 3):
        lines.append(("out", "   ".join(f"{n}/" for n in names[i:i + 3])))
    lines.append(("gap", ""))

    lines.append(("cmd", "cat current_work"))
    for item in data["currently_building"][:3]:
        tag = f'[{item["status"].upper()}]'
        tech = " . ".join(item["tech"][:3]) or (item["primary_language"] or "")
        lines.append(("status", f'{tag:<12}{item["repo"]:<22}{tech}'))
    lines.append(("gap", ""))

    lines.append(("cmd", "git log --all --oneline -1"))
    last = act.get("last_push") or {}
    if last.get("repo"):
        lines.append(("out", f'{last["at"]}  {last["repo"]}  (most recent public push)'))
    lines.append(("gap", ""))

    lines.append(("cmd", "git status"))
    contrib = act.get("contributions")
    summary = (f'{act["active_repos_30d"]} repositories touched in the last '
               f'{config.ACTIVE_WINDOW_DAYS} days')
    if contrib:
        summary += f' . {contrib["total"]:,} contributions in the last 365'
    lines.append(("out", summary))
    lines.append(("out", "working tree: building"))
    return lines


def terminal(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    lines = terminal_lines(data)
    W = 1000
    top = 78
    row = 20
    H = top + sum(10 if k == "gap" else row for k, _ in lines) + 34

    out = svg_open(W, H, "Terminal summary")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320) + """
    .ln { animation: fade .5s ease-out both; }
""")
    out += defs(th, W, H)

    # window chrome
    out += (f'  <path class="wire" d="M1 34 H{W - 1}"/>\n')
    for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        out += (f'  <circle cx="{24 + i * 17}" cy="18" r="5" fill="{color}" '
                f'fill-opacity=".85"/>\n')
    out += (f'  <text class="m fg3" x="{W / 2}" y="22" font-size="10.5" '
            f'text-anchor="middle">{e(data["user"]["login"])}@github: ~/profile</text>\n')
    out += (f'  <text class="m fg3" x="{W - 22}" y="22" font-size="9.5" '
            f'text-anchor="end">bash</text>\n')

    y = top - 24
    delay = 0.1
    last_x = 42.0
    for kind, text in lines:
        if kind == "gap":
            y += 10
            continue
        delay += 0.09
        if kind == "cmd":
            out += (f'  <g class="ln" style="animation-delay:{delay:.2f}s">\n')
            out += (f'    <text class="m b" x="22" y="{y}" font-size="12" '
                    f'fill="{th["green"]}">$</text>\n')
            out += (f'    <text class="m" x="42" y="{y}" font-size="12" '
                    f'fill="{th["fg"]}">{e(text)}</text>\n  </g>\n')
            last_x = 42 + mono_width(text, 12)
        elif kind == "status":
            out += (f'  <g class="ln" style="animation-delay:{delay:.2f}s">\n')
            tag = text[:12]
            color = th["green"] if "ACTIVE" in tag else (
                th["amber"] if "IMPROVING" in tag else th["accent"])
            out += (f'    <text class="m b" x="42" y="{y}" font-size="11" '
                    f'fill="{color}">{e(tag.strip())}</text>\n')
            out += (f'    <text class="m" x="{42 + mono_width("[IMPROVING]  ", 11):.0f}" '
                    f'y="{y}" font-size="11" fill="{th["fg2"]}" '
                    f'xml:space="preserve">{e(text[12:])}</text>\n  </g>\n')
            last_x = 42 + mono_width(text, 11)
        else:
            out += (f'  <text class="m ln" x="42" y="{y}" font-size="11" '
                    f'fill="{th["fg2"]}" xml:space="preserve" '
                    f'style="animation-delay:{delay:.2f}s">{e(text)}</text>\n')
            last_x = 42 + mono_width(text, 11)
        y += row

    out += (f'  <text class="m b" x="22" y="{y}" font-size="12" '
            f'fill="{th["green"]}">$</text>\n')
    out += (f'  <rect class="caret" x="42" y="{y - 11}" width="8" height="14" '
            f'fill="{th["accent"]}"/>\n')
    return out + "</svg>\n"


# ---------------------------------------------------------------------------
# 7. what I build
# ---------------------------------------------------------------------------

def what_i_build(data: dict, theme_name: str) -> str:
    th = THEMES[theme_name]
    cards = data["what_i_build"]
    W = 1000
    H = 122

    out = svg_open(W, H, "What I build")
    out += style_block(th, SWEEP_CSS.format(dist=W + 320))
    out += defs(th, W, H)

    n = len(cards)
    gap = 16
    card_w = (W - 40 - gap * (n - 1)) / n
    accents = [th["accent"], th["green"], th["violet"], th["amber"]]

    for i, (title, sub) in enumerate(cards):
        x = 20 + i * (card_w + gap)
        color = accents[i % len(accents)]
        out += f'  <g class="rise" style="animation-delay:{0.07 * i:.2f}s">\n'
        out += (f'    <rect class="card" x="{x:.1f}" y="24" width="{card_w:.1f}" '
                f'height="74" rx="9"/>\n')
        out += (f'    <rect x="{x:.1f}" y="24" width="{card_w:.1f}" height="2.5" rx="1.2" '
                f'fill="{color}" fill-opacity=".85"/>\n')
        out += (f'    <circle class="pulse" cx="{x + 18:.1f}" cy="50" r="3" '
                f'fill="{color}" style="animation-delay:{0.5 * i:.2f}s"/>\n')
        out += (f'    <text class="m b" x="{x + 30:.1f}" y="54" font-size="11.5" '
                f'fill="{th["fg"]}" letter-spacing="1.2">'
                f'{e(clip(title, int(card_w / 7.2)))}</text>\n')
        out += (f'    <text x="{x + 18:.1f}" y="78" font-size="10.5" '
                f'fill="{th["fg3"]}">{e(clip(sub, int(card_w / 5.4)))}</text>\n')
        out += '  </g>\n'

    return out + "</svg>\n"


# ---------------------------------------------------------------------------

BUILDERS = {
    "hero": hero,
    "currently-building": currently_building,
    "system-map": system_map,
    "activity": activity,
    "timeline": timeline,
    "terminal": terminal,
    "what-i-build": what_i_build,
}


def main() -> int:
    with open(DATA_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    for name, builder in BUILDERS.items():
        for theme in THEMES:
            filename = f"{name}-{theme}.svg"
            write(filename, builder(data, theme))
            print(f"  wrote assets/{filename}")
    print(f"\n{2 * len(BUILDERS)} assets rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

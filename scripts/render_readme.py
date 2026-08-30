"""Inject generated content into README.md.

The README owns its own headings and any hand-written prose. This script only
rewrites what sits between marker pairs:

    <!-- GEN:hero start -->   ... generated ...   <!-- GEN:hero end -->

Anything outside a marker pair is left exactly as written, so the README stays
editable by hand and a regeneration never clobbers prose.

Every generated image is emitted as a <picture> with a dark and a light source
so it follows the reader's GitHub theme, and carries a ?v=<content hash> so
GitHub's image proxy picks up a new render instead of serving a stale cache.

Run:  python scripts/render_readme.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from render_svg import terminal_lines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "profile.json")
README_PATH = os.path.join(ROOT, "README.md")
ASSET_DIR = os.path.join(ROOT, "assets")

# Absolute raw URLs rather than relative paths: GitHub proxies images through
# its camo cache, and an explicit ?v= on a full URL is what reliably invalidates
# it. Branch is pinned so a render never resolves against a stale default.
RAW_BASE = f"https://raw.githubusercontent.com/{config.USER}/{config.USER}/main/assets"


def asset_hash(name: str) -> str:
    """First 8 hex of the SVG's content hash, used as the cache-buster."""
    digest = hashlib.sha256()
    for theme in ("dark", "light"):
        path = os.path.join(ASSET_DIR, f"{name}-{theme}.svg")
        try:
            with open(path, "rb") as fh:
                digest.update(fh.read())
        except OSError:
            digest.update(b"missing")
    return digest.hexdigest()[:8]


def picture(name: str, alt: str) -> str:
    version = asset_hash(name)
    dark = f"{RAW_BASE}/{name}-dark.svg?v={version}"
    light = f"{RAW_BASE}/{name}-light.svg?v={version}"
    return (
        '<picture>\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{dark}">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="{light}">\n'
        f'  <img alt="{alt}" src="{dark}" width="100%">\n'
        '</picture>'
    )


def code(items) -> str:
    return " ".join(f"`{item}`" for item in items)


def dot(items) -> str:
    return " &middot; ".join(items)


# ---------------------------------------------------------------------------
# section builders -- each returns the markdown that goes inside its markers
# ---------------------------------------------------------------------------

def s_hero(data: dict) -> str:
    ident = data["identity"]
    links = dot(f"[{name}]({url})" for name, url in ident["links"])
    return "\n".join([
        picture("hero", f'{data["user"]["name"]} - {ident["tagline"]}. '
                        f'{ident["subline"]}'),
        "",
        links,
    ])


def s_currently_building(data: dict) -> str:
    lines = []
    for item in data["currently_building"]:
        age = item["days_since_push"]
        age_txt = "pushed today" if age == 0 else f"pushed {age}d ago"
        bits = [f"`{item['status']}`", age_txt]
        if item["push_events"]:
            bits.append(f"{item['push_events']} recent push events")
        lines.append(
            f"- **[{item['repo']}]({item['url']})** &mdash; {item['description']}.  \n"
            f"  {dot(bits)}"
            + (f" &middot; [live]({item['homepage']})" if item["homepage"] else "")
        )
    return "\n".join([
        picture("currently-building", "Currently building: " + "; ".join(
            f'{i["repo"]} ({i["status"].lower()})' for i in data["currently_building"]
        )),
        "",
        *lines,
    ])


def s_system_map(data: dict) -> str:
    smap = data["system_map"]
    rows = []
    for branch in smap["branches"]:
        rows.append(f"- **{branch['name'].title()}** &mdash; {dot(branch['leaves'])}  ")
        rows.append(f"  <sub>{dot(f'`{r}`' for r in branch['evidence'])}</sub>")
    return "\n".join([
        picture("system-map", "System map: " + " | ".join(
            f'{b["name"]}: {", ".join(b["leaves"])}' for b in smap["branches"]
        )),
        "",
        "<details>",
        "<summary>Same map as text, with the repositories each branch is drawn "
        "from</summary>",
        "",
        *rows,
        "",
        "</details>",
    ])


def s_featured(data: dict) -> str:
    blocks = []
    for i, project in enumerate(data["featured"], 1):
        meta = [f"`{project['primary_language'] or 'polyglot'}`"]
        if project["file_count"]:
            meta.append(f"{project['file_count']} files")
        meta.append(f"last push {project['pushed_at'][:10]}")
        if project["stars"]:
            meta.append(f"{project['stars']}&#9733;")

        links = [f"**[View repository &rarr;]({project['url']})**"]
        if project["homepage"]:
            links.append(f"[Live]({project['homepage']})")

        blocks.append("\n".join([
            f"### {i:02d} &middot; {project['title']}",
            "",
            f"{project['what']}",
            "",
            f"**Built with** &nbsp;{code(project['tech'])}",
            "",
            f"> **Why it is interesting** &nbsp; {project['why']}",
            "",
            f"{dot(links)}  ",
            f"<sub>{dot(meta)}</sub>",
        ]))
    return "\n\n---\n\n".join(blocks)


def s_activity(data: dict) -> str:
    act = data["activity"]
    contrib = act.get("contributions")
    stats = []
    if contrib:
        stats.append(f"**{contrib['total']:,}** contributions in the last 365 days")
        stats.append(f"**{contrib['commits']:,}** commits")
    stats.append(f"**{act['public_repos']}** public repositories")
    stats.append(f"**{act['active_repos_30d']}** touched in the last "
                 f"{config.ACTIVE_WINDOW_DAYS} days")
    stats.append(f"**{act['technologies_detected']}** technologies detected in code")

    note = data.get("language_share_note", {})
    excluded = note.get("excluded_repos") or []
    tail = [f"<sub>Language share is measured in bytes reported by GitHub."]
    if excluded:
        tail.append(f"{dot(f'`{r}`' for r in excluded)} "
                    f"{'is' if len(excluded) == 1 else 'are'} left out of that one "
                    f"figure &mdash; committed dependency directories would count "
                    f"vendored bytes as authored code.")
    tail.append("Everything on this page is generated from the GitHub API by "
                "[`scripts/`](scripts) and refreshed on a schedule.</sub>")

    return "\n".join([
        picture("activity", "Developer activity: " + "; ".join(
            s.replace("**", "") for s in stats)),
        "",
        dot(stats),
        "",
        " ".join(tail),
    ])


def s_tech_stack(data: dict) -> str:
    # Deliberately not a table: a two-column table with one long cell collapses
    # badly on a phone, and the brief calls for categorised text over a badge
    # wall. The superscript is real usage - repo count, or byte share for
    # languages.
    rows = []
    for category in config.CATEGORY_ORDER:
        entries = data["tech_by_category"].get(category)
        if not entries:
            continue
        cells = []
        for entry in entries:
            if "pct" in entry:
                marker = f"{entry['pct']:.0f}%"
            else:
                marker = str(entry["repo_count"])
            cells.append(f"{entry['name']} <sup>{marker}</sup>")
        rows.append(f"`{category.upper()}` &nbsp; {dot(cells)}")
    return "\n\n".join([
        *rows,
        "<sub>Nothing here is self-reported. Each entry was found by parsing the "
        "real dependency manifests and file trees of the repositories above; the "
        "small number is how many of them it appears in, and percentages are byte "
        "share. Only technologies with working code behind them are listed.</sub>",
    ])


def s_timeline(data: dict) -> str:
    rows = []
    for block in data["timeline"]:
        rows.append(f"**{block['year']}**  ")
        for entry in block["entries"]:
            desc = config.SHORT_DESC.get(entry["repo"], "")
            suffix = f" &mdash; {desc}" if desc else ""
            rows.append(f"&nbsp;&nbsp;`{entry['date']}` {entry['kind']} "
                        f"[{entry['repo']}]({entry['url']}){suffix}  ")
        rows.append("")
    return "\n".join([
        picture("timeline", "Timeline of repository starts and pushes by year"),
        "",
        "<details>",
        "<summary>Same timeline as text</summary>",
        "",
        *rows,
        "</details>",
    ])


def s_terminal(data: dict) -> str:
    body = []
    for kind, text in terminal_lines(data):
        if kind == "gap":
            body.append("")
        elif kind == "cmd":
            body.append(f"$ {text}")
        else:
            body.append(f"  {text}")
    return "\n".join([
        picture("terminal", "Terminal summary of who I am and what I am "
                            "currently working on"),
        "",
        "<details>",
        "<summary>Same output as selectable text</summary>",
        "",
        "```console",
        *body,
        "```",
        "",
        "</details>",
    ])


def s_what_i_build(data: dict) -> str:
    alt = "; ".join(f"{title}: {sub}" for title, sub in data["what_i_build"])
    return picture("what-i-build", "What I build - " + alt)


def s_footer(data: dict) -> str:
    act = data["activity"]
    return (
        f"<sub>Generated {data['generated_at'][:10]} from the GitHub API &middot; "
        f"{act['tracked_repos']} repositories in scope of "
        f"{act['public_repos']} public &middot; "
        f"regenerated by "
        f"[`update-profile.yml`](.github/workflows/update-profile.yml)</sub>"
    )


SECTIONS = {
    "currently-building": s_currently_building,
}


def inject(readme: str, name: str, body: str) -> tuple[str, bool]:
    pattern = re.compile(
        r"(<!--\s*GEN:" + re.escape(name) + r"\s+start\s*-->)"
        r".*?"
        r"(<!--\s*GEN:" + re.escape(name) + r"\s+end\s*-->)",
        re.S,
    )
    if not pattern.search(readme):
        return readme, False
    return pattern.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(2),
                       readme, count=1), True


def main() -> int:
    with open(DATA_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    with open(README_PATH, "r", encoding="utf-8") as fh:
        readme = fh.read()

    missing = []
    for name, builder in SECTIONS.items():
        readme, ok = inject(readme, name, builder(data))
        if ok:
            print(f"  filled GEN:{name}")
        else:
            missing.append(name)

    if missing:
        print("\n  ! no marker pair found for: " + ", ".join(missing))
        print("    add  <!-- GEN:name start -->  /  <!-- GEN:name end -->  "
              "to README.md")

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(readme)
    print(f"\nwrote README.md ({len(readme):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

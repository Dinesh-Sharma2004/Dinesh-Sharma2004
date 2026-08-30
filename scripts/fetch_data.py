"""Build data/profile.json from the public GitHub API.

Nothing here invents facts. Every value is either returned by the API or
derived from real repository contents (dependency manifests and file trees).

Run:  python scripts/fetch_data.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import gh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "profile.json")

NOW = dt.datetime.now(dt.timezone.utc)


def parse_ts(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc
    )


def days_since(value: str) -> int:
    return (NOW - parse_ts(value)).days


def load_previous() -> dict:
    """Previous snapshot, used to keep values that a rate-limited run misses."""
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Dependency + tree parsing
# ---------------------------------------------------------------------------

def parse_requirements(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # strip environment markers, extras and version specifiers
        line = line.split(";", 1)[0]
        match = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if match:
            names.add(match.group(1).lower())
    return names


def parse_package_json(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except ValueError:
        return set()
    names = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(key) or {}
        if isinstance(block, dict):
            names.update(name.lower() for name in block)
    return names


def parse_pyproject(text: str) -> set[str]:
    names = set()
    # Covers both [project].dependencies and poetry-style tables well enough for
    # detection purposes; we only need package names, not resolution.
    for raw in re.findall(r'"([A-Za-z0-9_.\-]+)\s*[<>=!~\[]?[^"]*"', text):
        names.add(raw.lower())
    for raw in re.findall(r"^\s*([A-Za-z0-9_.\-]+)\s*=\s*[\"{]", text, re.M):
        names.add(raw.lower())
    return names


MANIFEST_PARSERS = {
    "requirements.txt": parse_requirements,
    "requirements-dev.txt": parse_requirements,
    "package.json": parse_package_json,
    "pyproject.toml": parse_pyproject,
}

# Paths we never treat as evidence: vendored dependencies and build output.
NOISE = re.compile(
    r"(^|/)(node_modules|\.venv|venv|site-packages|dist|build|\.next|"
    r"vendor|third_party|__pycache__)(/|$)"
)


def fetch_tree(full_name: str, branch: str) -> tuple[list[str], bool]:
    """Return (usable blob paths, vendored?).

    `vendored` means the repo has committed dependency directories. GitHub's
    /languages endpoint counts those bytes, which would badly skew an aggregate
    language share, so callers drop such repos from that one statistic.
    """
    try:
        data = gh.api(f"/repos/{full_name}/git/trees/{branch}", {"recursive": "1"})
    except gh.GitHubError as exc:
        print(f"    tree unavailable: {exc}")
        return [], False
    paths, vendored = [], False
    for node in data.get("tree", []):
        path = node.get("path", "")
        if node.get("type") != "blob":
            continue
        if NOISE.search(path):
            vendored = True
            continue
        paths.append(path)
    if data.get("truncated"):
        print("    tree truncated by API (large repo)")
    return paths, vendored


def collect_evidence(full_name: str, branch: str, paths: list[str]) -> tuple[set[str], list[str]]:
    """Return (dependency tokens, lowercased paths) for one repo."""
    lower_paths = [p.lower() for p in paths]
    manifests = [
        p for p in paths
        if os.path.basename(p).lower() in MANIFEST_PARSERS
    ][: config.MAX_MANIFESTS_PER_REPO]

    tokens: set[str] = set()
    for path in manifests:
        text = gh.raw(full_name, branch, path)
        if not text:
            continue
        parser = MANIFEST_PARSERS[os.path.basename(path).lower()]
        tokens |= parser(text)
    return tokens, lower_paths


COMPILED_DETECT = [
    (name, category, [re.compile(p, re.I) for p in patterns])
    for name, category, patterns in config.DETECT
]


def detect_tech(tokens: set[str], paths: list[str]) -> list[str]:
    found = []
    for name, _category, patterns in COMPILED_DETECT:
        for pattern in patterns:
            if any(pattern.search(t) for t in tokens) or any(
                pattern.search(p) for p in paths
            ):
                found.append(name)
                break
    return found


TECH_CATEGORY = {name: category for name, category, _ in config.DETECT}


# ---------------------------------------------------------------------------
# Main fetch
# ---------------------------------------------------------------------------

def fetch_repos() -> list[dict]:
    repos = gh.api(
        f"/users/{config.USER}/repos",
        {"per_page": "100", "sort": "pushed", "direction": "desc"},
    )
    return [
        r for r in repos
        if not r["fork"] and not r["archived"] and r["name"] not in config.EXCLUDE_REPOS
    ]


CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


def fetch_contributions() -> dict | None:
    to = NOW
    frm = to - dt.timedelta(days=364)
    data = gh.graphql(
        CONTRIB_QUERY,
        {
            "login": config.USER,
            "from": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    if not data or not data.get("user"):
        return None
    coll = data["user"]["contributionsCollection"]
    cal = coll["contributionCalendar"]
    weeks = [
        [day["contributionCount"] for day in week["contributionDays"]]
        for week in cal["weeks"]
    ]
    return {
        "total": cal["totalContributions"],
        "commits": coll["totalCommitContributions"],
        "pull_requests": coll["totalPullRequestContributions"],
        "issues": coll["totalIssueContributions"],
        "repositories_created": coll["totalRepositoryContributions"],
        "weeks": weeks,
        "window_days": 365,
    }


def fetch_events() -> list[dict]:
    try:
        return gh.api(f"/users/{config.USER}/events/public", {"per_page": "100"})
    except gh.GitHubError as exc:
        print("  events unavailable:", exc)
        return []


def status_for(repo: dict, event_counts: dict) -> str:
    pushed = days_since(repo["pushed_at"])
    created = days_since(repo["created_at"])
    if pushed <= config.ACTIVE_WINDOW_DAYS:
        # Newly created and lightly touched reads as exploration, not delivery.
        if created <= 60 and event_counts.get(repo["name"], 0) <= 2:
            return config.STATUS_EXPLORING
        return config.STATUS_ACTIVE
    if created > 120 and pushed <= 90:
        return config.STATUS_IMPROVING
    return config.STATUS_EXPLORING


def build() -> dict:
    previous = load_previous()
    prev_repos = {r["name"]: r for r in previous.get("repos", [])}

    print("fetching profile ...", gh.rate_limit_note())
    user = gh.api(f"/users/{config.USER}")
    repos = fetch_repos()
    print(f"  {len(repos)} repositories in scope")

    events = fetch_events()
    push_counts: dict[str, int] = {}
    recent_pushes: list[dict] = []
    for event in events:
        name = event["repo"]["name"].split("/")[-1]
        if name in config.EXCLUDE_REPOS:
            continue
        if event["type"] == "PushEvent":
            push_counts[name] = push_counts.get(name, 0) + 1
            recent_pushes.append({"repo": name, "at": event["created_at"]})

    lang_totals: dict[str, int] = {}
    lang_excluded: list[str] = []
    tech_repos: dict[str, set[str]] = {}
    out_repos = []

    for repo in repos:
        name = repo["name"]
        print(f"  - {name}")
        prev = prev_repos.get(name, {})

        try:
            languages = gh.api(f"/repos/{repo['full_name']}/languages")
        except gh.GitHubError as exc:
            print(f"    languages unavailable: {exc}")
            languages = prev.get("languages", {})

        paths, vendored = fetch_tree(repo["full_name"], repo["default_branch"])
        if paths:
            tokens, lower_paths = collect_evidence(
                repo["full_name"], repo["default_branch"], paths
            )
            tech = detect_tech(tokens, lower_paths)
            file_count = len(paths)
        else:
            tech = prev.get("tech", [])
            file_count = prev.get("file_count", 0)
            vendored = prev.get("vendored", False)

        if vendored:
            # Committed dependency trees make the byte counts meaningless.
            lang_excluded.append(name)
            print("    excluded from language share (vendored dependencies)")
        else:
            for lang, size in (languages or {}).items():
                lang_totals[lang] = lang_totals.get(lang, 0) + size
        for item in tech:
            tech_repos.setdefault(item, set()).add(name)

        out_repos.append({
            "name": name,
            "url": repo["html_url"],
            "homepage": (repo.get("homepage") or "").strip() or None,
            "description": repo.get("description"),
            "primary_language": repo.get("language"),
            "languages": languages or {},
            "vendored": vendored,
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "topics": repo.get("topics") or [],
            "created_at": repo["created_at"],
            "pushed_at": repo["pushed_at"],
            "days_since_push": days_since(repo["pushed_at"]),
            "file_count": file_count,
            "tech": tech,
            "push_events_30d": push_counts.get(name, 0),
        })

    # Aggregate language share across the repos in scope.
    total_bytes = sum(lang_totals.values()) or 1
    language_share = sorted(
        ({"name": k, "bytes": v, "pct": round(100 * v / total_bytes, 1)}
         for k, v in lang_totals.items()),
        key=lambda d: -d["bytes"],
    )

    # Group detected technologies by category, ordered by how many repos use them.
    tech_by_category: dict[str, list[dict]] = {}
    for item, repo_names in tech_repos.items():
        category = TECH_CATEGORY[item]
        tech_by_category.setdefault(category, []).append({
            "name": item,
            "repo_count": len(repo_names),
            "repos": sorted(repo_names),
        })
    for entries in tech_by_category.values():
        entries.sort(key=lambda d: (-d["repo_count"], d["name"].lower()))

    # Languages become their own display category, ordered by real byte share.
    tech_by_category[config.LANGUAGE_CATEGORY] = [
        {"name": item["name"],
         "repo_count": sum(
             1 for r in out_repos
             if not r["vendored"] and item["name"] in (r["languages"] or {})
         ),
         "pct": item["pct"]}
        for item in language_share if item["pct"] >= 0.5
    ]

    # Currently building: recency first, then how much real push traffic there was.
    ranked = sorted(
        out_repos,
        key=lambda r: (r["days_since_push"], -r["push_events_30d"]),
    )
    currently_building = []
    for repo in ranked:
        desc = config.SHORT_DESC.get(repo["name"]) or repo["description"]
        if not desc:
            continue
        currently_building.append({
            "repo": repo["name"],
            "url": repo["url"],
            "homepage": repo["homepage"],
            "description": desc.strip().rstrip("."),
            "tech": repo["tech"][:4],
            "primary_language": repo["primary_language"],
            "status": status_for(
                {"name": repo["name"], "pushed_at": repo["pushed_at"],
                 "created_at": repo["created_at"]},
                push_counts,
            ),
            "days_since_push": repo["days_since_push"],
            "push_events": repo["push_events_30d"],
        })
        if len(currently_building) >= max(config.CURRENTLY_BUILDING_COUNT, 3):
            break

    contributions = fetch_contributions() or previous.get("activity", {}).get(
        "contributions"
    )

    active_30d = sum(
        1 for r in out_repos if r["days_since_push"] <= config.ACTIVE_WINDOW_DAYS
    )

    # Timeline: real create/update moments, grouped by year.
    featured_names = {f["repo"] for f in config.FEATURED}
    moments = []
    for repo in out_repos:
        weight = 2 if repo["name"] in featured_names else 1
        moments.append({
            "date": repo["created_at"][:10],
            "kind": "started",
            "repo": repo["name"],
            "url": repo["url"],
            "weight": weight,
        })
        if repo["created_at"][:4] != repo["pushed_at"][:4]:
            moments.append({
                "date": repo["pushed_at"][:10],
                "kind": "advanced",
                "repo": repo["name"],
                "url": repo["url"],
                "weight": weight,
            })
    moments.sort(key=lambda m: m["date"])

    years: dict[str, list[dict]] = {}
    for moment in moments:
        years.setdefault(moment["date"][:4], []).append(moment)
    timeline = []
    for year in sorted(years):
        entries = sorted(years[year], key=lambda m: (-m["weight"], m["date"]))[:4]
        timeline.append({
            "year": year,
            "entries": sorted(entries, key=lambda m: m["date"]),
        })

    # Featured projects, refreshed against live repo data.
    by_name = {r["name"]: r for r in out_repos}
    featured = []
    for entry in config.FEATURED:
        repo = by_name.get(entry["repo"])
        if not repo:
            print(f"  ! featured repo missing from scope: {entry['repo']}")
            continue
        featured.append({
            "repo": entry["repo"],
            "title": entry["title"],
            "what": entry["what"],
            "why": entry["why"],
            "tech": entry.get("tech") or repo["tech"][:8],
            "detected_tech": repo["tech"],
            "url": repo["url"],
            "homepage": repo["homepage"],
            "stars": repo["stars"],
            "pushed_at": repo["pushed_at"],
            "days_since_push": repo["days_since_push"],
            "primary_language": repo["primary_language"],
            "file_count": repo["file_count"],
        })

    return {
        "generated_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user": {
            "login": user["login"],
            "name": config.DISPLAY_NAME,
            "url": user["html_url"],
            "avatar": user["avatar_url"],
            "public_repos": user["public_repos"],
            "followers": user["followers"],
            "created_at": user["created_at"],
            "years_on_github": round((NOW - parse_ts(user["created_at"])).days / 365.25, 1),
        },
        "identity": {
            "tagline": config.TAGLINE,
            "subline": config.SUBLINE,
            "links": config.LINKS,
        },
        "repos": out_repos,
        "language_share": language_share,
        "language_share_note": {
            "basis": "bytes reported by the GitHub /languages endpoint",
            "excluded_repos": lang_excluded,
            "reason": "repos with committed dependency directories are excluded "
                      "because their byte counts measure vendored code, not authored code",
        },
        "tech_by_category": tech_by_category,
        "currently_building": currently_building,
        "featured": featured,
        "system_map": config.SYSTEM_MAP,
        "what_i_build": config.WHAT_I_BUILD,
        "timeline": timeline,
        "activity": {
            "contributions": contributions,
            "tracked_repos": len(out_repos),
            "public_repos": user["public_repos"],
            "active_repos_30d": active_30d,
            "languages_detected": len([l for l in language_share if l["pct"] >= 0.5]),
            "technologies_detected": len(tech_repos),
            "recent_pushes": recent_pushes[:12],
            "event_window": {
                "from": events[-1]["created_at"][:10] if events else None,
                "to": events[0]["created_at"][:10] if events else None,
                "push_events": sum(push_counts.values()),
            },
            "last_push": {
                "repo": ranked[0]["name"] if ranked else None,
                "at": ranked[0]["pushed_at"][:10] if ranked else None,
            },
        },
    }


def main() -> int:
    data = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=False)
        fh.write("\n")
    print(f"\nwrote {os.path.relpath(OUT_PATH, ROOT)}  ({gh.rate_limit_note()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

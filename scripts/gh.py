"""Minimal GitHub client: stdlib only, disk-cached, token-aware.

Kept deliberately small so it stays readable. Two entry points:

    gh.api("/users/x/repos", params={...})   -> parsed JSON from api.github.com
    gh.raw("owner/repo", "path")            -> file text from raw.githubusercontent

Responses are cached under .cache/ keyed by URL so re-running the generator
locally costs no rate limit. Set PROFILE_NO_CACHE=1 to bypass, or delete
.cache/ to force a cold refresh.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
RAW_ROOT = "https://raw.githubusercontent.com"

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
CACHE_TTL_SECONDS = int(os.environ.get("PROFILE_CACHE_TTL", 6 * 3600))
USE_CACHE = os.environ.get("PROFILE_NO_CACHE", "") not in ("1", "true", "yes")

TOKEN = (
    os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GH_TOKEN")
    or ""
).strip()

_USER_AGENT = "dinesh-profile-generator (+https://github.com/Dinesh-Sharma2004)"


class GitHubError(RuntimeError):
    """Raised for non-retryable API failures."""


def _cache_path(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return os.path.join(CACHE_DIR, digest + ".json")


def _cache_read(key: str):
    if not USE_CACHE:
        return None
    path = _cache_path(key)
    try:
        if time.time() - os.path.getmtime(path) > CACHE_TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)["body"]
    except (OSError, ValueError, KeyError):
        return None


def _cache_write(key: str, body) -> None:
    if not USE_CACHE:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = _cache_path(key) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"key": key, "body": body}, fh)
        os.replace(tmp, _cache_path(key))
    except OSError:
        pass


def _request(url: str, *, data: bytes | None = None, accept: str) -> str:
    headers = {"Accept": accept, "User-Agent": _USER_AGENT}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    if data is not None:
        headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            # 403/429 with a rate-limit reset is worth one short wait, not a
            # long sleep -- the workflow runs on a schedule and can retry later.
            if exc.code in (403, 429) and attempt < 2:
                reset = exc.headers.get("X-RateLimit-Reset")
                remaining = exc.headers.get("X-RateLimit-Remaining")
                if remaining == "0" and reset:
                    wait = min(60, max(0, int(reset) - int(time.time()) + 2))
                    print(f"  rate limited, waiting {wait}s")
                    time.sleep(wait)
                    continue
            if exc.code == 404:
                raise GitHubError(f"404 {url}") from exc
            last_error = GitHubError(f"HTTP {exc.code} for {url}: {body}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
        except urllib.error.URLError as exc:
            last_error = GitHubError(f"network error for {url}: {exc.reason}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
    raise last_error or GitHubError(f"failed: {url}")


def api(path: str, params: dict | None = None, *, cache: bool = True):
    """GET a REST endpoint and return parsed JSON."""
    url = API_ROOT + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if cache:
        cached = _cache_read(url)
        if cached is not None:
            return cached
    body = json.loads(_request(url, accept="application/vnd.github+json"))
    if cache:
        _cache_write(url, body)
    return body


def graphql(query: str, variables: dict):
    """POST a GraphQL query. Requires a token; returns None without one."""
    if not TOKEN:
        return None
    payload = json.dumps({"query": query, "variables": variables})
    key = "graphql:" + hashlib.sha256(payload.encode()).hexdigest()
    cached = _cache_read(key)
    if cached is not None:
        return cached
    body = json.loads(
        _request(GRAPHQL_URL, data=payload.encode("utf-8"), accept="application/json")
    )
    if body.get("errors"):
        print("  graphql errors:", body["errors"][:1])
        return None
    _cache_write(key, body.get("data"))
    return body.get("data")


def raw(full_name: str, ref: str, path: str) -> str | None:
    """Fetch a file's text from raw.githubusercontent (no API rate limit)."""
    url = f"{RAW_ROOT}/{full_name}/{ref}/{urllib.parse.quote(path)}"
    cached = _cache_read(url)
    if cached is not None:
        return cached
    try:
        text = _request(url, accept="text/plain")
    except GitHubError:
        _cache_write(url, "")
        return None
    _cache_write(url, text)
    return text


def rate_limit_note() -> str:
    try:
        core = api("/rate_limit", cache=False)["resources"]["core"]
        return f"{core['remaining']}/{core['limit']} API calls left"
    except Exception:
        return "rate limit unknown"

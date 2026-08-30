"""Run the whole pipeline: fetch data, render SVGs, inject the README.

    python scripts/build.py              # normal run (uses .cache/)
    python scripts/build.py --no-fetch   # re-render from the existing data file
    PROFILE_NO_CACHE=1 python scripts/build.py   # ignore the local cache

Set GITHUB_TOKEN to lift the API rate limit and to enable the contribution
calendar, which the unauthenticated REST API cannot provide.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_data
import render_readme
import render_svg


def main(argv: list[str]) -> int:
    if "--no-fetch" not in argv:
        print("[1/3] fetch")
        if fetch_data.main() != 0:
            return 1
    else:
        print("[1/3] fetch  (skipped)")

    print("\n[2/3] render svg")
    if render_svg.main() != 0:
        return 1

    print("\n[3/3] render readme")
    return render_readme.main()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

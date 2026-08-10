#!/usr/bin/env python3
"""churn — deterministic recent-churn scoping for an architecture scan.

Part of praxis-core. An architecture-scan phase's first step, scoping by recent churn, is the one
deterministic sliver of an otherwise all-judgment process: "walk `git log` for a good stretch of
history to find hot spots, and let those paths pull attention first." That is a fact computable from
git alone — file/directory change frequency over a window — so it is a script, and the phase spends
its judgment on reading the modules the hot spots point at, not on tallying commits.

No engine coupling at all: this reads git, nothing else. It is pure filesystem/VCS fact, like
`root_tree`.

Commands:
  files [--repo DIR] [--since REV|--max-count N] [--top K] [--json]   hottest files by change count
  dirs  [--repo DIR] [--depth N] [...]                                hottest directories (rolled up)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _git_log_files(repo: Path, since: str | None, max_count: int | None) -> list[str] | None:
    """Every changed-file path across the selected commit window (one line per file-change).
    Returns None when the directory is not a git repo or git is unavailable."""
    cmd = ["git", "-C", str(repo), "log", "--no-merges", "--name-only", "--pretty=format:"]
    if since:
        cmd.append(f"{since}..HEAD")
    if max_count:
        cmd += ["--max-count", str(max_count)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError):
        return None
    if p.returncode != 0:
        return None
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def churn_files(repo: Path, since: str | None, max_count: int | None, top: int) -> dict:
    paths = _git_log_files(repo, since, max_count)
    if paths is None:
        return {"repo": str(Path(repo).resolve()), "available": False,
                "note": "not a git repository, or git unavailable", "hot": []}
    counts = Counter(paths)
    hot = [{"path": p, "changes": n} for p, n in counts.most_common(top)]
    return {"repo": str(Path(repo).resolve()), "available": True, "commits_window": max_count,
            "since": since, "hot": hot}


def churn_dirs(repo: Path, since: str | None, max_count: int | None, top: int, depth: int) -> dict:
    paths = _git_log_files(repo, since, max_count)
    if paths is None:
        return {"repo": str(Path(repo).resolve()), "available": False,
                "note": "not a git repository, or git unavailable", "hot": []}
    counts: Counter = Counter()
    for p in paths:
        parts = Path(p).parts
        key = "/".join(parts[:depth]) if len(parts) > depth else str(Path(p).parent) or "."
        counts[key] += 1
    hot = [{"dir": d, "changes": n} for d, n in counts.most_common(top)]
    return {"repo": str(Path(repo).resolve()), "available": True, "depth": depth, "hot": hot}


def _print(result: dict, key: str) -> None:
    if not result["available"]:
        print(f"churn: {result['note']}")
        return
    if not result["hot"]:
        print("churn: no changes in the selected window.")
        return
    print("recent churn (hottest first):")
    for row in result["hot"]:
        print(f"  {row['changes']:>4}  {row[key]}")


def cmd_files(args) -> int:
    r = churn_files(Path(args.repo), args.since or None, args.max_count, args.top)
    print(json.dumps(r, indent=2)) if args.json else _print(r, "path")
    return 0


def cmd_dirs(args) -> int:
    r = churn_dirs(Path(args.repo), args.since or None, args.max_count, args.top, args.depth)
    print(json.dumps(r, indent=2)) if args.json else _print(r, "dir")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="churn", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--repo", default=".", help="repository directory (default cwd)")
        p.add_argument("--since", default="", help="a git rev; window is <rev>..HEAD")
        p.add_argument("--max-count", type=int, default=200, help="commits to look back (default 200)")
        p.add_argument("--top", type=int, default=15, help="how many hot spots to report")
        p.add_argument("--json", action="store_true")

    f = sub.add_parser("files", help="hottest files by change count")
    common(f)
    f.set_defaults(func=cmd_files)

    d = sub.add_parser("dirs", help="hottest directories (paths rolled up to --depth)")
    common(d)
    d.add_argument("--depth", type=int, default=2, help="directory depth to roll paths up to")
    d.set_defaults(func=cmd_dirs)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

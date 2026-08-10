#!/usr/bin/env python3
"""deferred_queue — the non-blocking UI/UX decision queue for a project (the uiux plugin's praxis face).

`corpora/deferred-decisions.md` is a project working queue for unresolved DESIGN questions that do not
block current implementation. It is a UI/UX concern — it exists only for projects with a UI — so it
ships with the uiux plugin rather than the judgment core. It is not a substitute for a handoff or a
place to hide blockers; every queued item names a narrow reversible provisional treatment so the coder
can proceed without turning that treatment into settled direction.

Schema (deliberately flat, so it validates without a YAML dependency):

    # Deferred decisions

    Only non-blocking UI/UX questions belong here. Blocking questions are surfaced immediately.

    ```yaml
    decisions:
      - id: results-empty-state
        stance: convergent                 # convergent | divergent
        domain: validation-feedback
        question: "Should an empty filtered result preserve filters or offer a reset action?"
        context: "Results panel introduced by the search workstream."
        source-workstream: search
        created: 2026-07-14                 # YYYY-MM-DD
        blocking: no                        # always 'no' — surface blockers immediately
        provisional-treatment: "Preserve filters; add no reset action yet."
        related-files: [src/components/results.tsx]
        status: queued                      # queued | resolved
    ```

Group items by stance and related surface, not count alone. A design workstream is warranted when
several items need coherent judgment, an item becomes blocking, provisional work would create material
rework, or the operator requests it. `resolve` an item only after the operator's review settles it (a
ratified principle, or an accepted design decision at design-decision-review) — recording HOW it was
settled (`resolution:` + `resolved:` date).

**A resolved item is kept, not deleted — the backward spine.** Durable direction still lives in the
UI/UX libraries and the corpus (that is where a later spawn LOADS it), but the queue retains the
resolved decision as a legible trace: a later design pass sees the question was raised and how it was
settled, rather than re-raising it from scratch (the same discipline planning.md applies to
out-of-scope decisions — a trace for legibility, never a queue to resume from). `list` shows only the
still-open (queued) items; the resolved ones are the trace beneath them.

Commands:
  lint    --root DIR                          validate the queue (exit 1 on problems); a UI project must have one
  list    --root DIR [--all]                  list queued (unresolved) decisions; --all also shows the resolved trace
  resolve --root DIR --id ID --resolution T   mark a decision resolved in place, keeping it as a trace
"""
from __future__ import annotations

import argparse
import os
import re
import sys

STANCE_ENUM = {"convergent", "divergent"}
STATUS_ENUM = {"queued", "resolved"}
REQUIRED = ("id", "stance", "domain", "question", "context", "source-workstream",
            "created", "blocking", "provisional-treatment", "status")


def state_dir(root: str) -> str:
    """`.corpora` is the standard project-state dir; bare `corpora` is the legacy fallback —
    same resolution order as corpus.py's Project.__init__."""
    return ".corpora" if os.path.isfile(os.path.join(root, ".corpora", "config.md")) else "corpora"


def queue_path(root: str) -> str:
    return os.path.join(root, state_dir(root), "deferred-decisions.md")


def parse_deferred(path: str) -> list:
    """Parse the queue's deliberately flat YAML subset without a YAML dependency."""
    entries: list = []
    item = None
    in_decisions = False
    for raw in open(path):
        line = raw.rstrip()
        stripped = line.strip()
        if in_decisions and stripped == "```":
            break
        if stripped == "decisions:" or stripped == "decisions: []":
            in_decisions = True
            continue
        if not in_decisions or not stripped or stripped.startswith(("#", "```")):
            continue
        if re.match(r"^\s*-\s+id:\s*", line):
            item = {}
            entries.append(item)
            stripped = re.sub(r"^-\s+", "", stripped)
        if item is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            item[key.strip()] = value.strip().strip('"').strip("'")
    return entries


def deferred_problems(entries: list) -> list:
    problems: list = []
    seen: set = set()
    for index, entry in enumerate(entries, 1):
        label = entry.get("id") or f"entry {index}"
        for field in REQUIRED:
            if not entry.get(field):
                problems.append(f"{label}: missing {field}")
        if entry.get("id") in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(entry.get("id"))
        if entry.get("stance") not in STANCE_ENUM:
            problems.append(f"{label}: stance must be one of {sorted(STANCE_ENUM)}")
        if entry.get("status") not in STATUS_ENUM:
            problems.append(f"{label}: status must be one of {sorted(STATUS_ENUM)}")
        if entry.get("blocking") != "no":
            problems.append(f"{label}: blocking must be 'no' — surface blockers immediately")
        created = entry.get("created", "")
        if created and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", created):
            problems.append(f"{label}: created must be YYYY-MM-DD")
        # A resolved entry is a kept trace — it must record HOW it was settled, else it is just a
        # dangling 'resolved' with no legibility value (the whole point of keeping it).
        if entry.get("status") == "resolved":
            if not entry.get("resolution"):
                problems.append(f"{label}: resolved but missing resolution (how it was settled)")
            resolved_date = entry.get("resolved", "")
            if resolved_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", resolved_date):
                problems.append(f"{label}: resolved must be YYYY-MM-DD")
    return problems


def has_ui(root: str) -> bool:
    config = os.path.join(root, state_dir(root), "config.md")
    text = open(config).read() if os.path.exists(config) else ""
    return bool(re.search(r"^has-ui:\s*yes\s*$", text, re.MULTILINE))


def cmd_lint(args) -> int:
    path = queue_path(args.root)
    if not os.path.exists(path):
        if has_ui(args.root):
            print(f"UI project has no {path} — create it from the schema (see this script's header)",
                  file=sys.stderr)
            return 1
        print("no deferred-decision queue needed (project has no UI)")
        return 0
    entries = parse_deferred(path)
    problems = deferred_problems(entries)
    if problems:
        print(f"FAIL {path}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    resolved = [e["id"] for e in entries if e.get("status") == "resolved"]
    queued = [e["id"] for e in entries if e.get("status") == "queued"]
    print(f"PASS {path} ({len(queued)} open, {len(resolved)} resolved trace)")
    return 0


def cmd_list(args) -> int:
    path = queue_path(args.root)
    if not os.path.exists(path):
        print("deferred decision queue: absent")
        return 0
    entries = parse_deferred(path)
    if deferred_problems(entries):
        print("deferred decision queue is invalid; run `lint`", file=sys.stderr)
        return 1
    queued = [e for e in entries if e.get("status") == "queued"]
    if not queued:
        print("deferred decision queue: empty (no open decisions)")
    else:
        print("deferred non-blocking decisions:")
        for stance in sorted(STANCE_ENUM):
            owned = [e for e in queued if e["stance"] == stance]
            if not owned:
                continue
            print(f"  {stance} ({len(owned)}):")
            for entry in owned:
                print(f"    - {entry['id']}  domain={entry['domain']}  workstream={entry['source-workstream']}")
                print(f"      {entry['question']}")
    if getattr(args, "all", False):
        resolved = [e for e in entries if e.get("status") == "resolved"]
        if resolved:
            print(f"resolved trace ({len(resolved)}):")
            for entry in resolved:
                print(f"    - {entry['id']}  resolved={entry.get('resolved', '?')}  "
                      f"→ {entry.get('resolution', '?')}")
    return 0


def cmd_resolve(args) -> int:
    """Mark a decision resolved IN PLACE, keeping it as a trace: flip its status to resolved and record
    how it was settled (`resolution:` + `resolved:` date). A targeted line edit, so the hand-maintained
    file's formatting survives; the entry is never deleted (the backward spine)."""
    path = queue_path(args.root)
    if not os.path.exists(path):
        print(f"no deferred-decision queue at {path}", file=sys.stderr)
        return 1
    ids = [e.get("id") for e in parse_deferred(path)]
    if args.id not in ids:
        print(f"no deferred decision with id '{args.id}' (have: {', '.join(ids) or 'none'})", file=sys.stderr)
        return 1
    out: list = []
    in_entry = False
    status_done = False
    today = __import__("datetime").date.today().isoformat()
    for raw in open(path):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if re.match(r"^\s*-\s+id:\s*", line):
            # entering a new entry; the one we want starts here
            in_entry = (stripped.split(":", 1)[1].strip().strip('"').strip("'") == args.id)
            status_done = False
        if in_entry and not status_done and re.match(r"^\s*status\s*:", line):
            indent = line[:len(line) - len(line.lstrip())]
            out.append(f"{indent}status: resolved")
            out.append(f"{indent}resolved: {today}")
            out.append(f'{indent}resolution: "{args.resolution}"')
            status_done = True
            continue
        out.append(line)
    open(path, "w").write("\n".join(out) + "\n")
    print(f"resolved '{args.id}' in place (kept as trace): {path}")
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="deferred_queue", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    li = sub.add_parser("lint", help="validate the deferred UI/UX decision queue")
    li.add_argument("--root", default=".", help="the project root (holds corpora/deferred-decisions.md)")
    li.set_defaults(func=cmd_lint)
    ls = sub.add_parser("list", help="list queued decisions grouped by stance")
    ls.add_argument("--root", default=".")
    ls.add_argument("--all", action="store_true", help="also show the resolved trace beneath the open items")
    ls.set_defaults(func=cmd_list)
    rs = sub.add_parser("resolve", help="mark a decision resolved in place, keeping it as a trace")
    rs.add_argument("--root", default=".")
    rs.add_argument("--id", required=True, help="the decision id to resolve")
    rs.add_argument("--resolution", required=True, help="how it was settled (kept as the trace)")
    rs.set_defaults(func=cmd_resolve)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

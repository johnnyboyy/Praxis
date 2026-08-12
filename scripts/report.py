#!/usr/bin/env python3
"""report — deterministic rendering of a praxis root's journal into human-readable text (or JSON).

The journal (`<root>/.praxis/journal.jsonl`) is an append-only event log; `journal.py` folds it into
per-unit state, an analytics rollup, and gap tallies. This script is the READ surface over that fold:
it turns those structures into aligned, one-screen text so reporting is a pure function of the log,
not a thing the model has to reconstruct by inference. Every subcommand also emits the underlying
structured data with `--json`.

Commands:
  summary  [--root R] [--json]            one-screen overview (default): unit state counts, top gap
                                          candidates, per-phase metrics, open units
  journal  [--root R] [--json]            recent journal entries (--limit N, --unit UID, --event TYPE)
  gaps     [--root R] [--json]            recurring gap-vocabulary candidates (+ recent raw gaps)
  metrics  [--root R] [--json]            analytics rollup: by-phase / by-workflow runs, pass-rate,
                                          stalls, and unit state counts

A root with no journal yet degrades gracefully: a friendly note and exit 0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# journal.py lives at the repo ROOT (parent of scripts/); root_tree.py lives beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal  # noqa: E402
import root_tree as rt  # noqa: E402


# ── shared helpers ────────────────────────────────────────────────────────────

def has_journal(root: Path) -> bool:
    return journal.journal_path(root).is_file()


def no_journal_msg(root: Path) -> str:
    return f"no journal yet ({journal.journal_path(root)} absent) — nothing to report"


def fmt_ts(ts) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
    except (TypeError, ValueError):
        return str(ts)


_PAYLOAD_SKIP = {"ts", "seq", "event", "unit"}


def payload_summary(ev: dict, width: int = 80) -> str:
    """A compact key=value digest of an event's payload (everything but the structural keys)."""
    parts = []
    for k, v in ev.items():
        if k in _PAYLOAD_SKIP:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(",", ":"))
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    out = " ".join(parts)
    return out if len(out) <= width else out[: width - 3] + "..."


def state_counts(fold: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for u in fold["units"].values():
        counts[u["state"] or "?"] = counts.get(u["state"] or "?", 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def pass_rate(bucket: dict) -> float:
    runs = bucket.get("runs", 0)
    return (bucket.get("result", 0) / runs) if runs else 0.0


def _pad(rows: list[list[str]], headers: list[str]) -> list[str]:
    """Render aligned columns; returns a list of lines (header + separator + rows)."""
    cols = len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))
    line = lambda cells: "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    out = [line(headers), "  ".join("-" * widths[i] for i in range(cols))]
    out.extend(line(r) for r in rows)
    return out


# ── journal ───────────────────────────────────────────────────────────────────

def cmd_journal(args) -> int:
    root = Path(args.root).resolve()
    if not has_journal(root):
        print(no_journal_msg(root))
        return 0
    events = journal.read(root)
    if args.unit:
        events = [e for e in events if e.get("unit") == args.unit]
    if args.event:
        events = [e for e in events if e.get("event") == args.event]
    recent = events[-args.limit:] if args.limit and args.limit > 0 else events

    if args.json:
        print(json.dumps(recent, indent=2))
        return 0

    if not recent:
        print("no matching journal entries")
        return 0
    rows = [[fmt_ts(e.get("ts")), str(e.get("seq", "")), e.get("event", ""),
             e.get("unit", "") or "-", payload_summary(e)] for e in recent]
    for l in _pad(rows, ["time", "seq", "event", "unit", "payload"]):
        print(l)
    print(f"\nshowing {len(recent)} of {len(events)} entries")
    return 0


# ── gaps ──────────────────────────────────────────────────────────────────────

def cmd_gaps(args) -> int:
    root = Path(args.root).resolve()
    if not has_journal(root):
        print(no_journal_msg(root))
        return 0
    candidates = journal.gap_candidates(root)
    raw = journal.gaps(root)

    if args.json:
        print(json.dumps({"candidates": candidates, "recent_gaps": raw[-10:]}, indent=2))
        return 0

    if not candidates:
        print("no gap candidates yet — no conductor.gap events with a suggested vocabulary")
    else:
        print("recurring gap candidates (by count):\n")
        rows = [[c["suggested"], c["vocabulary"], str(c["count"]),
                 ", ".join(c["chosen_as"]) or "-"] for c in candidates]
        for l in _pad(rows, ["suggested", "vocabulary", "count", "chosen-as"]):
            print(l)
    if raw:
        print(f"\nrecent raw gaps ({min(len(raw), 5)} of {len(raw)}):")
        for e in raw[-5:]:
            sug = e.get("suggested") or "?"
            chosen = e.get("chosen") or "-"
            print(f"  [{fmt_ts(e.get('ts'))}] {e.get('vocabulary', 'task_kind')}: "
                  f"{sug} -> {chosen}")
    return 0


# ── metrics ─────────────────────────────────────────────────────────────────

def _metrics_rows(by: dict) -> list[list[str]]:
    rows = []
    for name, b in sorted(by.items(), key=lambda kv: (-kv[1].get("runs", 0), kv[0])):
        rows.append([name, str(b.get("runs", 0)), str(b.get("result", 0)),
                     str(b.get("stall", 0)), f"{pass_rate(b) * 100:.0f}%"])
    return rows


def cmd_metrics(args) -> int:
    root = Path(args.root).resolve()
    if not has_journal(root):
        print(no_journal_msg(root))
        return 0
    fold = journal.fold(root)
    summary = fold["summary"]

    if args.json:
        print(json.dumps({"state_counts": state_counts(fold),
                          "total_units": len(fold["units"]),
                          "summary": summary}, indent=2))
        return 0

    counts = state_counts(fold)
    print(f"units: {len(fold['units'])} total  ("
          + ", ".join(f"{k}={v}" for k, v in counts.items()) + ")\n")

    print("by phase:")
    if summary["by_phase"]:
        for l in _pad(_metrics_rows(summary["by_phase"]),
                      ["phase", "runs", "result", "stall", "pass"]):
            print("  " + l)
    else:
        print("  (no concluded units yet)")

    print("\nby workflow:")
    if summary["by_workflow"]:
        for l in _pad(_metrics_rows(summary["by_workflow"]),
                      ["workflow", "runs", "result", "stall", "pass"]):
            print("  " + l)
    else:
        print("  (none)")

    stalls = summary["recent_stalls"]
    print(f"\nrecent stalls ({len(stalls)}):")
    if stalls:
        for s in stalls:
            print(f"  {s.get('unit')}  phase={s.get('phase')}  "
                  f"workflow={s.get('workflow') or '-'}  status={s.get('status') or '-'}")
    else:
        print("  (none)")
    return 0


# ── summary (default) ─────────────────────────────────────────────────────────

def cmd_summary(args) -> int:
    root = Path(args.root).resolve()
    if not has_journal(root):
        print(no_journal_msg(root))
        return 0
    fold = journal.fold(root)
    summary = fold["summary"]
    candidates = journal.gap_candidates(root)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "total_units": len(fold["units"]),
            "state_counts": state_counts(fold),
            "open_units": fold["open_units"],
            "gap_candidates": candidates[:5],
            "by_phase": summary["by_phase"],
            "recent_stalls": summary["recent_stalls"],
        }, indent=2))
        return 0

    counts = state_counts(fold)
    print(f"praxis report — {root}\n")
    print(f"units: {len(fold['units'])} total  ("
          + ", ".join(f"{k}={v}" for k, v in counts.items()) + ")")

    print("\ntop gap candidates:")
    if candidates:
        for c in candidates[:5]:
            chosen = ", ".join(c["chosen_as"]) or "-"
            print(f"  {c['count']}x  {c['suggested']}  ({c['vocabulary']} -> {chosen})")
    else:
        print("  (none)")

    print("\nper-phase metrics:")
    if summary["by_phase"]:
        for l in _pad(_metrics_rows(summary["by_phase"]),
                      ["phase", "runs", "result", "stall", "pass"]):
            print("  " + l)
    else:
        print("  (no concluded units yet)")

    print("\nopen units:")
    if fold["open_units"]:
        for uid in fold["open_units"]:
            u = fold["units"][uid]
            print(f"  {uid}  [{u['state']}]  workflow={u.get('workflow') or '-'}")
    else:
        print("  (none)")

    stalls = summary["recent_stalls"]
    if stalls:
        print(f"\nrecent stalls ({len(stalls)}):")
        for s in stalls:
            print(f"  {s.get('unit')}  phase={s.get('phase')}  status={s.get('status') or '-'}")
    return 0


# ── argparse ──────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="report", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def add_root(p):
        p.add_argument("--root", default=".", help="praxis root (default: cwd)")
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    p_sum = sub.add_parser("summary", help="one-screen overview (default)")
    add_root(p_sum)
    p_sum.set_defaults(func=cmd_summary)

    p_jrn = sub.add_parser("journal", help="recent journal entries")
    add_root(p_jrn)
    p_jrn.add_argument("--limit", type=int, default=20, help="max entries, most recent last")
    p_jrn.add_argument("--unit", help="filter to one unit UID")
    p_jrn.add_argument("--event", help="filter to one event type")
    p_jrn.set_defaults(func=cmd_journal)

    p_gap = sub.add_parser("gaps", help="recurring gap-vocabulary candidates")
    add_root(p_gap)
    p_gap.set_defaults(func=cmd_gaps)

    p_met = sub.add_parser("metrics", help="analytics rollup")
    add_root(p_met)
    p_met.set_defaults(func=cmd_metrics)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        # default subcommand: summary against cwd
        args = ap.parse_args(["summary", *argv])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""library_state — the deterministic state + phase-eligibility fact for a root's design libraries.

Part of praxis. The six corpora library processes (ui/ux/screenshot × init/sync) share one large
deterministic surface that is pure filesystem + config: *does this root have UI, which library
documents already exist, and therefore which init/sync phase is eligible and in what order*. That
question is a fact, computed before any design judgment — the same "fact prior to routing" role
`root_tree` plays for roots. The judgment (what to actually document, how deep, is a discrepancy a
finding or a change) stays in the phase files that consume this.

The eligibility rules are transcribed straight from the processes' own trigger prose:

  ui-library-init         has-ui AND no ui-library.md            bootstrap Phase 2, divergent
  screenshot-library-init has-ui AND ui-library.md AND no manifest   bootstrap Phase 3, mechanical
  ux-library-init         has-ui AND ui-library.md AND no ux-library.md  bootstrap Phase 4, convergent
  ui-library-sync         has-ui AND ui-library.md exists         ongoing, divergent  (drift-gated)
  ux-library-sync         has-ui AND ux-library.md exists         ongoing, convergent (drift-gated)
  screenshot-library-sync has-ui AND manifest exists              ongoing, mechanical (every drift)

Ordering (bootstrap): Phase 2 (ui-init) precedes Phase 3 (screenshot-init) and Phase 4 (ux-init),
which are independent of each other — both a content dependency on the ratified ui-library, proxied
here by ui-library.md *existing* (existence is the deterministic proxy for "ui-init ratified"; the
ratified-vs-drafted distinction is a corpora gate fact praxis does not read).

Drift thresholds (`library-drift.since-last-sync >= 3`) and ratified state are corpora counters, not
filesystem facts — this script marks a sync `drift_gated: true` and does not invent the count.

Commands:
  state [--root DIR] [--json]   the full library-state fact and eligible phases for the root
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HAS_UI_RE = re.compile(r"^\s*has-ui:\s*(\S+)", re.MULTILINE)
# a config may relocate a library; honor the declared path, else the corpora default.
UI_PATH_RE = re.compile(r"^\s*ui-library:\s*(\S+)", re.MULTILINE)
UX_PATH_RE = re.compile(r"^\s*ux-library:\s*(\S+)", re.MULTILINE)


def state_dir(root: Path) -> str:
    """`.corpora` is the standard project-state dir; bare `corpora` is the legacy fallback —
    same resolution order as corpus.py's Project.__init__."""
    return ".corpora" if (root / ".corpora" / "config.md").is_file() else "corpora"


def _cfg_value(text: str, pattern: re.Pattern, default: str) -> str:
    m = pattern.search(text)
    return m.group(1) if m else default


def build_state(root: Path) -> dict:
    root = Path(root).resolve()
    base = state_dir(root)
    config = root / base / "config.md"
    cfg_text = config.read_text(encoding="utf-8", errors="replace") if config.is_file() else ""

    has_ui = _cfg_value(cfg_text, HAS_UI_RE, "no").lower() in ("yes", "true")
    ui_rel = _cfg_value(cfg_text, UI_PATH_RE, f"{base}/ui-library.md")
    ux_rel = _cfg_value(cfg_text, UX_PATH_RE, f"{base}/ux-library.md")

    ui_exists = (root / ui_rel).is_file()
    ux_exists = (root / ux_rel).is_file()
    manifest_exists = (root / base / "screenshots" / "manifest.md").is_file()

    phases: list[dict] = []

    def add(name, eligible, unit_of_work, stance, mechanical, phase, drift_gated=False, blocked_by=None):
        phases.append({
            "phase": name, "eligible": eligible, "unit_of_work": unit_of_work, "stance": stance,
            "mechanical": mechanical, "bootstrap_phase": phase, "drift_gated": drift_gated,
            "blocked_by": blocked_by,
        })

    # init phases — gated on absence, ordered by the ui -> {screenshot, ux} content dependency.
    add("ui-library-init", has_ui and not ui_exists, "bootstrap-ui-surface", "divergent", False, 2)
    add("screenshot-library-init", has_ui and ui_exists and not manifest_exists,
        None, None, True, 3, blocked_by=None if ui_exists else "ui-library-init")
    add("ux-library-init", has_ui and ui_exists and not ux_exists,
        "bootstrap-ux-surface", "convergent", False, 4,
        blocked_by=None if ui_exists else "ui-library-init")
    # sync phases — gated on presence; drift-gated (a corpora counter praxis does not compute).
    add("ui-library-sync", has_ui and ui_exists, "design-ui-surface", "divergent", False, None, drift_gated=True)
    add("ux-library-sync", has_ui and ux_exists, "design-ux-flow", "convergent", None, None, drift_gated=True)
    add("screenshot-library-sync", has_ui and manifest_exists, None, None, True, None, drift_gated=False)

    eligible = [p for p in phases if p["eligible"]]
    # next bootstrap step: lowest-numbered eligible init phase (deterministic pipeline order).
    inits = sorted((p for p in eligible if p["bootstrap_phase"]), key=lambda p: p["bootstrap_phase"])
    next_step = inits[0]["phase"] if inits else None

    return {
        "root": str(root),
        "has_ui": has_ui,
        "libraries": {"ui": ui_exists, "ux": ux_exists, "screenshots": manifest_exists},
        "phases": phases,
        "eligible": [p["phase"] for p in eligible],
        "next_bootstrap_step": next_step,
    }


def print_state(s: dict) -> None:
    print(f"library state · {s['root']}")
    print(f"  has-ui: {'yes' if s['has_ui'] else 'no'}")
    libs = s["libraries"]
    print(f"  ui-library: {'present' if libs['ui'] else 'absent'} · "
          f"ux-library: {'present' if libs['ux'] else 'absent'} · "
          f"screenshots: {'present' if libs['screenshots'] else 'absent'}")
    if not s["has_ui"]:
        print("  no UI surface — no library phase applies.")
        return
    print("  eligible phases:")
    for p in s["phases"]:
        if not p["eligible"]:
            continue
        bits = []
        if p["mechanical"]:
            bits.append("mechanical")
        else:
            bits.append(f"{p['stance']}, uow={p['unit_of_work']}")
        if p["drift_gated"]:
            bits.append("drift-gated (corpora counter)")
        print(f"    • {p['phase']}  ({', '.join(bits)})")
    if s["next_bootstrap_step"]:
        print(f"  next bootstrap step: {s['next_bootstrap_step']}")


def cmd_state(args) -> int:
    s = build_state(Path(args.root))
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print_state(s)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="library_state", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("state", help="library-state fact + eligible phases for a root")
    s.add_argument("--root", default=".", help="the root to inspect (default cwd)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_state)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""library_state — the deterministic state + phase-eligibility fact for a root's design libraries.

Ported into the uiux plugin from the OLD corpora praxis face. The six library processes
(ui/ux/screenshot × init/sync) share one large deterministic surface that is pure filesystem +
config: *does this root have UI, which library documents already exist, and therefore which
init/sync phase is eligible and in what order*. That question is a fact, computed before any
design judgment. The judgment (what to actually document, how deep, is a discrepancy a finding or
a change) stays in the phase files that consume this.

The eligibility rules are transcribed straight from the processes' own trigger prose:

  ui-library-init         has-ui AND no ui-library.md            bootstrap Phase 2, divergent
  screenshot-library-init has-ui AND ui-library.md AND no manifest   bootstrap Phase 3, mechanical
  ux-library-init         has-ui AND ui-library.md AND no ux-library.md  bootstrap Phase 4, convergent
  ui-library-sync         has-ui AND ui-library.md exists         ongoing, divergent  (drift-gated)
  ux-library-sync         has-ui AND ux-library.md exists         ongoing, convergent (drift-gated)
  screenshot-library-sync has-ui AND manifest exists              ongoing, mechanical (every drift)

Ordering (bootstrap): Phase 2 (ui-init) precedes Phase 3 (screenshot-init) and Phase 4 (ux-init),
which are independent of each other — both a content dependency on the ratified ui-library, proxied
here by ui-library.md *existing*.

Two things differ from the OLD CLI (spec §6, §2):
  * State no longer lives under `.corpora/`; the plugin owns a typed config scope `"uiux"` and a
    working-state dir `.praxis/uiux/`. `has-ui` and library paths are read from `config.read(root,
    "uiux")` rather than regex-parsing `.corpora/config.md`. `build_state`'s existence checks, phase
    table, and ordering are unchanged.
  * The drift counter is owned by uiux (`config.read(root,"uiux")["library_drift"]`), not an external
    corpora counter. `evaluate` exposes it as the `drift` fact; the regime/routing decision belongs to
    the workflow's fact-predicate edges (IMPL-SPEC-fact-routing §4/§5), not to this module.

Commands:
  state [--root DIR] [--json]   the full library-state fact and eligible phases for the root
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import config

# The plugin's owned config scope and working-state dir (spec §6).
SCOPE = "uiux"
DEFAULT_UI_LIBRARY = "docs/design/ui-library.md"
DEFAULT_UX_LIBRARY = "docs/design/ux-library.md"
DRIFT_THRESHOLD = 3


def _state_dir(root) -> Path:
    """The plugin's working-state dir. Replaces the OLD `.corpora`/`corpora` resolution."""
    return Path(root) / ".praxis" / "uiux"


def _lib_paths(root):
    """Absolute paths to the ui/ux libraries, honoring a config relocation (spec §6)."""
    cfg = config.read(root, SCOPE)
    ui = Path(root) / cfg.get("ui_library", DEFAULT_UI_LIBRARY)
    ux = Path(root) / cfg.get("ux_library", DEFAULT_UX_LIBRARY)
    return ui, ux


def manifest_path(root) -> Path:
    return _state_dir(root) / "screenshots" / "manifest.md"


def screenshots_dir(root) -> Path:
    return _state_dir(root) / "screenshots"


# --- screenshot manifest (a small, flat, YAML-free markdown store) --------------
# Each catalogued screen is one entry the plugin owns; `contribute` reads it for
# freshness references and the `close` hook marks entries stale (spec §3, §4).
#
#     # Screenshots
#
#     - screen: settings
#       file: settings.png
#       status: fresh              # fresh | stale
#       components: button, input  # optional, comma-separated

_MANIFEST_KEYS = ("screen", "file", "status", "components")


def read_manifest(root) -> list[dict]:
    """Parse the screenshot manifest into `{screen,file,status,components[]}` entries. Fail-soft."""
    path = manifest_path(root)
    if not path.is_file():
        return []
    entries: list[dict] = []
    item: dict | None = None
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^-\s+screen:\s*(.*)$", stripped)
        if m:
            item = {"screen": m.group(1).strip(), "file": "", "status": "fresh", "components": []}
            entries.append(item)
            continue
        if item is None or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "components":
            item["components"] = [c.strip() for c in value.split(",") if c.strip()]
        elif key in _MANIFEST_KEYS:
            item[key] = value
    return entries


def write_manifest(root, entries: list[dict]) -> None:
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Screenshots", ""]
    for e in entries:
        lines.append(f"- screen: {e.get('screen', '')}")
        lines.append(f"  file: {e.get('file', '')}")
        lines.append(f"  status: {e.get('status', 'fresh')}")
        comps = e.get("components") or []
        if comps:
            lines.append(f"  components: {', '.join(comps)}")
    path.write_text("\n".join(lines) + "\n")


def mark_stale(root, screens=None, components=None, all_surfaces=False) -> bool:
    """Mark the named screens (and every screen tagged with a named component) stale.

    `all_surfaces=True` is the global/blast-radius fan-out (token/theme/shell changes):
    every catalogued manifest surface is marked stale regardless of `screens`/`components`.
    This is also the full-recapture escape hatch — the surgical sync phase then reshoots
    exactly this set, which when all are stale *is* a full recapture (spec §5).

    A screen named but not yet catalogued is appended as a stale entry so the next
    `screenshot-capture` shoots it (spec §4 action 2). Fail-soft: returns False when
    nothing changed. Called from the close hook."""
    screens = set(screens or [])
    components = set(components or [])
    if not screens and not components and not all_surfaces:
        return False
    entries = read_manifest(root)
    changed = False
    seen = set()
    for e in entries:
        seen.add(e["screen"])
        tagged = bool(components & set(e.get("components") or []))
        if (all_surfaces or e["screen"] in screens or tagged) and e.get("status") != "stale":
            e["status"] = "stale"
            changed = True
    # brand-new screens with no capture yet → append a stale placeholder to be shot.
    for screen in screens - seen:
        entries.append({"screen": screen, "file": f"{screen}.png", "status": "stale",
                        "components": []})
        changed = True
    if changed:
        write_manifest(root, entries)
    return changed


def mark_fresh(root, screens=None) -> bool:
    """Clear the stale flag on the named screens (default: ALL currently-stale).

    Inverse of `mark_stale`. Called from the close hook after a screenshot-library-sync
    recapture (spec §2.4). Fail-soft: returns False when nothing changed."""
    entries = read_manifest(root)
    target = set(screens) if screens else None
    changed = False
    for e in entries:
        if e.get("status") == "stale" and (target is None or e["screen"] in target):
            e["status"] = "fresh"
            changed = True
    if changed:
        write_manifest(root, entries)
    return changed


def build_state(root: Path) -> dict:
    root = Path(root).resolve()
    cfg = config.read(root, SCOPE)

    has_ui = str(cfg.get("has_ui", "no")).lower() in ("yes", "true")
    ui_path, ux_path = _lib_paths(root)

    ui_exists = ui_path.is_file()
    ux_exists = ux_path.is_file()
    manifest_exists = manifest_path(root).is_file()

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
    # sync phases — gated on presence; drift-gated (uiux owns the counter now, spec §2).
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


def _drift_counts(root) -> tuple[int, int]:
    """(ui_drift, ux_drift). Migrates the OLD `since_last_sync` scalar fail-soft:
    a legacy value seeds BOTH counters so no accumulated drift is dropped."""
    d = config.read(root, SCOPE).get("library_drift", {})
    if not isinstance(d, dict):
        return 0, 0
    legacy = int(d.get("since_last_sync", 0) or 0)
    ui_d = int(d.get("ui_drift", legacy) or 0)
    ux_d = int(d.get("ux_drift", legacy) or 0)
    return ui_d, ux_d


def evaluate(root, unit=None, composed=None) -> dict:
    """Deterministic `Phase.run` callable for the `library-state` phase — FACTS ONLY, no `next`.

    Always `passed=True` — this is a fact, never a failure. The phase emits facts and does NOT name
    a route: routing is owned by the workflow's fact-predicate edges (IMPL-SPEC-fact-routing §4/§5).
    `design-bootstrap` predicates on library-absence; `feature-design` predicates on drift.

    `facts.library_state` carries the whole build_state dict (a superset: it adds `drift` and a flat
    `eligibility` map) for downstream disclosure and the workflow predicates; `produces` carries the
    same dict forward as `composed["carry"]` for the init/sync spawn phases.
    """
    s = build_state(Path(root))
    manifest = read_manifest(root)
    stale = [e["screen"] for e in manifest if e.get("status") == "stale"]
    ui_d, ux_d = _drift_counts(root)          # (ui_drift, ux_drift)
    s = {
        **s,
        # --- backward-compat scalar (kept; == max of the two counters) -----------
        "drift": max(ui_d, ux_d),
        # --- per-library staleness -----------------------------------------------
        "ui_drift": ui_d,
        "ux_drift": ux_d,
        "screenshots": {
            "stale": stale,                    # list[str] of screen names
            "stale_count": len(stale),         # int
            "any_stale": bool(stale),          # bool
        },
        "eligibility": {p["phase"]: bool(p["eligible"]) for p in s["phases"]},
    }
    return {"passed": True, "facts": {"library_state": s}, "produces": s}


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
            bits.append("drift-gated (uiux counter)")
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

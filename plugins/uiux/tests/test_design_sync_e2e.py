"""End-to-end verification of the uiux design-sync flow through the LIVE praxis run path.

This suite proves the whole feature -> staleness -> recommend -> surgical-sync loop and
the blast-radius hop against throwaway praxis roots with `uiux` registered as a contributor
via `.praxis/config.json` (exactly as a live root would), driven through the same seams a
real conductor drives:

  * `run.run_unit` -> `registry.resolve_workflows` -> `workflow_run.run_workflow` for all
    routing (fully live: real fact-predicate edges over `library_state.evaluate`).
  * `contributors.fire(contribs, "unit-close", ctx)` for the per-unit hook — the EXACT
    dispatch `run.run_unit`/`run_workflow` use as each unit finishes, threading the unit's
    final receipt. The receipt is `Receipt.to_dict()`-shaped: the drift/decision/screenshot
    payload lives under `receipt["evidence"]` (the single-dispatch receipt and the workflow
    aggregate deliver it there). The contributor is the real config-registered one from
    `contributors_for(root)`; nothing is stubbed.

Scenarios (spec §1-§5):
  1. feature -> staleness -> recommend: a feature-design unit walks live; its close receipt
     (drift touching one surface) marks that surface stale, bumps ui+ux drift, and surfaces
     a "design-sync due" cadence note.
  2. design-sync surgical + eager: one stale surface, sub-threshold ui/ux -> routes to
     screenshot-library-sync (EAGER); the composed contribution names ONLY the stale
     surface (surgical); an accepted screenshot-sync close freshens it. Zero route_unmatched.
  3. threshold routing: fresh screenshots + ui/ux drift >= threshold -> ui/ux sync;
     all-clean -> close with no route_unmatched.
  4. piggyback gone: feature-design with ui_drift >= threshold still routes library-state ->
     plan (never ui-library-sync).
  5. blast radius: a `global`/`tokens` close flag marks ALL surfaces stale; design-sync's
     recapture then covers the whole set (full-recapture path).

Run:  python3 -m pytest tests/test_design_sync_e2e.py -q
      python3 tests/test_design_sync_e2e.py     # standalone: PASS summary, non-zero on fail
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- sys.path: praxis skill, praxis/scripts, this plugin ------------------------
_PRAXIS = str(Path(__file__).resolve().parents[3])
_PRAXIS_SCRIPTS = _PRAXIS + "/scripts"
_PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
for _p in (_PRAXIS, _PRAXIS_SCRIPTS, _PLUGIN_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import journal  # noqa: E402
import library_state  # noqa: E402
import run as R  # noqa: E402
from contributors import HookContext, contributors_for, fire  # noqa: E402
from situation import Situation  # noqa: E402

TH = library_state.DRIFT_THRESHOLD


# ── the executor that drives the LIVE walk: records each phase's composed map ────

class RecordingExecutor:
    """A real `run.Executor`: records the per-phase `composed` map and returns a
    `produces` receipt so the walk advances along its `pass`/`fact` edges."""

    def __init__(self, emit=None):
        self.seen: list[dict] = []
        # phase_name -> extra evidence the executor folds into that phase's receipt,
        # so the workflow aggregate carries it into the live `unit-close` fire.
        self.emit = emit or {}

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        ev = {"produces": f"art-{len(self.seen)}"}
        ev.update(self.emit.get(composed.get("phase"), {}))
        return R.Receipt(outcome="result", evidence=ev)

    def uiux_at(self, phase_name):
        """The uiux-sourced contributions the executor saw at `phase_name`."""
        for c in self.seen:
            if c.get("phase") == phase_name:
                return [x for x in c.get("contributions", []) if x.source == "uiux"]
        return None


# ── root builder: registers uiux via config, like a real root ────────────────────

def _build_root(tmp_path, *, ui=True, ux=True, manifest=None, drift=None) -> Path:
    root = Path(tmp_path)
    config.ensure(root)
    config.write(root, "contributors", {"uiux": "uiux_plugin:make"})
    uiux_cfg = {"has_ui": "yes"}
    if drift is not None:
        uiux_cfg["library_drift"] = drift
    config.write(root, "uiux", uiux_cfg)
    if ui:
        p = root / "docs" / "design" / "ui-library.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# UI library\n\n## Button\n- token: color.primary\n")
    if ux:
        p = root / "docs" / "design" / "ux-library.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# UX library\n\n## Onboarding\n- three steps\n")
    if manifest is not None:
        library_state.write_manifest(root, manifest)
    return root


def _fresh(screen, components=None):
    return {"screen": screen, "file": f"{screen}.png", "status": "fresh",
            "components": components or []}


def _stale(screen, components=None):
    return {"screen": screen, "file": f"{screen}.png", "status": "stale",
            "components": components or []}


def _statuses(root):
    return {e["screen"]: e["status"] for e in library_state.read_manifest(root)}


def _sit(root, *, workflow=None, phase_name=None, targets=None):
    return Situation(task_kind="change", intent="design-sync-e2e", subject="design",
                     phase="none", phase_name=phase_name, root=str(root),
                     targets=targets or [], workflow=workflow)


class _Unit:
    """A minimal unit with a `situation` carrying phase_name/targets — what the
    close hook reads off `ctx.unit.situation` (mirrors run's Unit shape)."""

    def __init__(self, uid, phase_name=None, targets=None):
        self.id = uid
        self.situation = Situation(task_kind="change", intent="close", subject="design",
                                   phase="none", phase_name=phase_name, targets=targets or [])


def _run_unit(root, workflow, *, targets=None, emit=None):
    """Drive a workflow through the LIVE run_unit -> run_workflow path. `emit` folds
    extra evidence into a phase's receipt so the workflow aggregate threads it into the
    live `unit-close` fire (proving the per-unit seam delivers the receipt)."""
    ex = RecordingExecutor(emit=emit)
    out = R.run_unit(root, R.Unit(f"u-{workflow}",
                                  _sit(root, workflow=workflow, targets=targets)),
                     contributors_for(root), ex)
    return out, ex


def _fire_close(root, *, phase_name, receipt, targets=None, uid="close-u"):
    """Fire the per-unit `unit-close` hook through the real `contributors.fire` seam —
    the same dispatch `run.run_unit`/`run_workflow` use — with a receipt-bearing
    HookContext whose payload is nested under `evidence`, exactly as core now delivers
    it. The contributor is the live config-registered one from `contributors_for(root)`."""
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit(uid, phase_name=phase_name, targets=targets),
                      receipt={"evidence": receipt})
    fire(contributors_for(root), "unit-close", ctx)


def _unmatched(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.route_unmatched"]


def _verb_line(contribs, needle="Recapture ONLY"):
    """The surgical recapture verb line out of the screenshot-sync contribution."""
    body = "\n".join(c.body for c in contribs)
    return [ln for ln in body.splitlines() if needle in ln][0]


# ════════════════════════════════════════════════════════════════════════════
# Scenario 1 — feature -> staleness -> recommend (LIVE walk + live close seam)
# ════════════════════════════════════════════════════════════════════════════

def test_feature_close_marks_stale_bumps_drift_and_recommends(tmp_path):
    # a couple of FRESH surfaces; drift at 0.
    root = _build_root(tmp_path, manifest=[_fresh("settings"), _fresh("home")],
                       drift={"ui_drift": 0, "ux_drift": 0})

    # drive feature-design LIVE: library-state -> plan (never a sync piggyback). The
    # implement phase emits a drift receipt touching ONE surface; the workflow aggregate
    # threads it into the LIVE per-unit `unit-close` fire — no hook is fired by hand,
    # proving the real seam delivers the receipt under `receipt["evidence"]`.
    out, _ = _run_unit(
        root, "feature-design", targets=["Button"],
        emit={"implement": {"ui-drift": {"screens": ["settings"],
                                         "components": ["Button"]}}})
    assert out.get("workflow") == "feature-design"
    assert out["phases"][:2] == ["library-state", "plan"]
    assert "ui-library-sync" not in out["phases"]
    assert _unmatched(root) == []

    # that surface is now stale; the untouched sibling stays fresh.
    st = _statuses(root)
    assert st["settings"] == "stale"
    assert st["home"] == "fresh"

    # both drift counters bumped (ui-drift receipt carries no ux signal -> conservative).
    ui_d, ux_d = library_state._drift_counts(root)
    assert (ui_d, ux_d) == (1, 1)

    # a "design-sync due" cadence note was surfaced (per-library, screenshots N stale).
    due = [n for n in journal.notes(root) if n.get("body", "").startswith("design-sync due")]
    assert due, journal.notes(root)
    note = due[-1]
    assert "screenshots (1 stale)" in note["body"]
    assert note["screenshots_stale"] == 1
    assert note["ui_drift"] == 1 and note["ux_drift"] == 1


# ════════════════════════════════════════════════════════════════════════════
# Scenario 2 — design-sync surgical + eager (LIVE routing + composed disclosure)
# ════════════════════════════════════════════════════════════════════════════

def test_design_sync_eager_surgical_then_freshens(tmp_path):
    # one stale surface, a fresh sibling; ui/ux drift BELOW threshold.
    root = _build_root(tmp_path, manifest=[_stale("settings"), _fresh("home")],
                       drift={"ui_drift": 1, "ux_drift": 1})

    out, ex = _run_unit(root, "design-sync")
    assert out.get("workflow") == "design-sync"

    # EAGER: routes library-state -> screenshot-library-sync (NOT ui/ux — sub-threshold).
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "screenshot-library-sync"
    assert "ui-library-sync" not in out["phases"]
    assert "ux-library-sync" not in out["phases"]

    # the composed screenshot-sync contribution is SURGICAL: the recapture line names
    # ONLY the stale surface, never the fresh sibling.
    sync_c = ex.uiux_at("screenshot-library-sync")
    assert sync_c, "uiux must compose at screenshot-library-sync"
    verb = _verb_line(sync_c)
    assert "settings" in verb
    assert "home" not in verb          # surgical — the fresh sibling is NOT recaptured

    # an accepted screenshot-sync close freshens exactly the reshot surface.
    _fire_close(root, phase_name="screenshot-library-sync",
                receipt={"decision": {"accept": True},
                         "screenshots": {"captured": ["settings"]}})
    assert _statuses(root) == {"settings": "fresh", "home": "fresh"}

    # the loop produced no unmatched fact route.
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 3 — threshold routing (ui / ux / all-clean) through the LIVE path
# ════════════════════════════════════════════════════════════════════════════

def test_design_sync_ui_threshold_routes_ui(tmp_path):
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": TH, "ux_drift": 0})
    out, _ = _run_unit(root, "design-sync")
    assert out["phases"][:2] == ["library-state", "ui-library-sync"]


def test_design_sync_ux_threshold_routes_ux(tmp_path):
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": 0, "ux_drift": TH})
    out, _ = _run_unit(root, "design-sync")
    assert out["phases"][:2] == ["library-state", "ux-library-sync"]


def test_design_sync_all_clean_exits_close_no_unmatched(tmp_path):
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": 0, "ux_drift": 0})
    out, _ = _run_unit(root, "design-sync")
    assert out["phases"] == ["library-state", "close"]
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 4 — piggyback gone: feature-design never branches to a sync
# ════════════════════════════════════════════════════════════════════════════

def test_feature_design_over_threshold_still_routes_plan(tmp_path):
    # ui_drift well over threshold — under the OLD piggyback this would sync.
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": TH + 2, "ux_drift": TH + 2})
    out, _ = _run_unit(root, "feature-design", targets=["Button"])
    assert out["phases"][:2] == ["library-state", "plan"]     # NOT ui-library-sync
    assert "ui-library-sync" not in out["phases"]
    assert "ux-library-sync" not in out["phases"]
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 5 — blast radius: a global/tokens flag fans out to EVERY surface
# ════════════════════════════════════════════════════════════════════════════

def test_blast_radius_global_flag_full_recapture(tmp_path):
    # three FRESH surfaces, drift below threshold.
    root = _build_root(tmp_path,
                       manifest=[_fresh("settings"), _fresh("home"), _fresh("profile")],
                       drift={"ui_drift": 0, "ux_drift": 0})

    # a close carrying a `global` flag marks ALL manifest surfaces stale (blast radius).
    _fire_close(root, phase_name="implement", receipt={"ui-drift": {"global": True}})
    assert set(_statuses(root).values()) == {"stale"}          # every surface stale

    # design-sync then routes EAGER and the recapture set covers the WHOLE surface set
    # (full-recapture path — all surfaces named in the surgical verb line).
    out, ex = _run_unit(root, "design-sync")
    assert out["phases"][:2] == ["library-state", "screenshot-library-sync"]
    verb = _verb_line(ex.uiux_at("screenshot-library-sync"))
    for screen in ("settings", "home", "profile"):
        assert screen in verb, verb

    # a `tokens` flag is the same blast-radius trigger.
    root2 = _build_root(tmp_path / "r2",
                        manifest=[_fresh("a"), _fresh("b")], drift={"ui_drift": 0, "ux_drift": 0})
    _fire_close(root2, phase_name="implement", receipt={"ui-drift": {"tokens": True}})
    assert set(_statuses(root2).values()) == {"stale"}


# ── standalone runner: PASS summary + non-zero exit on failure ──────────────────

if __name__ == "__main__":
    import pytest
    code = pytest.main([__file__, "-q"])
    if code == 0:
        print("\nPASS: uiux design-sync flow verified end-to-end through the LIVE praxis "
              "run path — feature close marks surfaces stale + bumps drift + surfaces the "
              "'design-sync due' cadence note; design-sync routes EAGER to a SURGICAL "
              "screenshot recapture (stale-only) and an accepted sync freshens it; ui/ux "
              "threshold + all-clean routing hold with zero route_unmatched; the feature "
              "piggyback is gone (always -> plan); and a global/tokens close flag fans the "
              "blast radius across EVERY surface into a full recapture.")
    else:
        print("\nFAIL: see pytest output above.")
    sys.exit(code)

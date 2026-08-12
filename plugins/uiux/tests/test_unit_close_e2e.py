"""End-to-end proof that the per-unit `unit-close` hook delivers a unit's receipt
to plugins through the LIVE praxis run path — NO hand-fired hooks.

This closes the gap the prior design-sync verify had to work around: that suite
had to call `contributors.fire(..., "unit-close", ...)` BY HAND because there was
no per-unit close seam wired into the run path. Core now fires `unit-close` once
per unit from `run.run_unit` (single-dispatch via `_finish`) and from
`run_workflow`'s return (with the walked phases' AGGREGATE receipt under
`receipt["evidence"]`). Here every fire is the REAL one core emits as a unit
finishes — the test never fires a hook itself.

Scenarios:
  1. Receipt reaches uiux for real. A `feature-design` unit walks live against a
     throwaway root (uiux registered, has_ui, libraries + a couple FRESH surfaces).
     Its `implement` phase EMITS `ui-drift` evidence touching ONE surface via the
     RecordingExecutor `emit` seam; the workflow aggregate threads it into the live
     `unit-close` fire, and uiux's real `_on_close` (a) flips that surface stale
     (sibling stays fresh), (b) bumps ui/ux drift, (c) surfaces the "design-sync
     due" note — all with NO hand-fired hook.
  2. A second plugin rides the same event. A minimal `_close_recorder` contributor
     is registered ALONGSIDE uiux in the same root's config; driving a unit fires
     ITS `unit-close` hook once too, with the same unit id + a receipt carrying the
     evidence. Proves `unit-close` is a general per-unit seam.
  3. Batch close unaffected. `run.run` still fires the run-level `close` exactly
     once (unchanged).
  4. Exactly-once. `unit-close` fires exactly once for a workflow unit — no
     duplicate across the run_unit -> run_workflow path (run_unit returns the
     run_workflow result before its own `_finish`, so only one fire happens).

Run:  python3 -m pytest tests/test_unit_close_e2e.py -q
      python3 tests/test_unit_close_e2e.py    # standalone: PASS summary, non-zero on fail
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- sys.path: praxis skill, praxis/scripts, this plugin, this tests dir ---------
_PRAXIS = str(Path(__file__).resolve().parents[3])
_PRAXIS_SCRIPTS = _PRAXIS + "/scripts"
_PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
_TESTS_DIR = str(Path(__file__).resolve().parent)   # so `contributors_for` can import _close_recorder
for _p in (_PRAXIS, _PRAXIS_SCRIPTS, _PLUGIN_ROOT, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _close_recorder  # noqa: E402  (the throwaway second contributor)
import config  # noqa: E402
import journal  # noqa: E402
import library_state  # noqa: E402
import run as R  # noqa: E402
from contributors import contributors_for  # noqa: E402
from situation import Situation  # noqa: E402

TH = library_state.DRIFT_THRESHOLD


# ── the executor that drives the LIVE walk (records composed, folds emit) ─────────

class RecordingExecutor:
    """A real `run.Executor`: returns a `produces` receipt so the walk advances, and
    folds `emit[phase]` evidence into that phase's receipt so the workflow aggregate
    threads it into the LIVE `unit-close` fire."""

    def __init__(self, emit=None):
        self.seen: list[dict] = []
        self.emit = emit or {}

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        ev = {"produces": f"art-{len(self.seen)}"}
        ev.update(self.emit.get(composed.get("phase"), {}))
        return R.Receipt(outcome="result", evidence=ev)


# ── root builder: registers uiux (and optionally the recorder) via config ─────────

def _build_root(tmp_path, *, manifest=None, drift=None, with_recorder=False) -> Path:
    root = Path(tmp_path)
    config.ensure(root)
    contribs = {"uiux": "uiux_plugin:make"}
    if with_recorder:
        contribs["recorder"] = "_close_recorder:make"
    config.write(root, "contributors", contribs)
    uiux_cfg = {"has_ui": "yes"}
    if drift is not None:
        uiux_cfg["library_drift"] = drift
    config.write(root, "uiux", uiux_cfg)
    for name, body in (("ui-library.md", "# UI library\n\n## Button\n- token: color.primary\n"),
                       ("ux-library.md", "# UX library\n\n## Onboarding\n- three steps\n")):
        p = root / "docs" / "design" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    if manifest is not None:
        library_state.write_manifest(root, manifest)
    return root


def _fresh(screen, components=None):
    return {"screen": screen, "file": f"{screen}.png", "status": "fresh",
            "components": components or []}


def _statuses(root):
    return {e["screen"]: e["status"] for e in library_state.read_manifest(root)}


def _sit(root, *, workflow=None, targets=None):
    return Situation(task_kind="change", intent="unit-close-e2e", subject="design",
                     phase="none", root=str(root), targets=targets or [], workflow=workflow)


def _run_unit(root, workflow, *, targets=None, emit=None):
    """Drive a workflow through the LIVE run_unit -> run_workflow path (no hand-fired hooks)."""
    ex = RecordingExecutor(emit=emit)
    out = R.run_unit(root, R.Unit(f"u-{workflow}",
                                  _sit(root, workflow=workflow, targets=targets)),
                     contributors_for(root), ex)
    return out, ex


def _unmatched(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.route_unmatched"]


# ════════════════════════════════════════════════════════════════════════════
# Scenario 1 — the receipt reaches uiux's real hook through the LIVE fire.
# (The closed gap: the prior verify had to hand-fire this hook.)
# ════════════════════════════════════════════════════════════════════════════

def test_unit_close_delivers_receipt_to_uiux_live(tmp_path):
    root = _build_root(tmp_path, manifest=[_fresh("settings"), _fresh("home")],
                       drift={"ui_drift": 0, "ux_drift": 0})

    # feature-design walks LIVE (library-state -> plan -> implement -> verify -> close);
    # implement EMITS ui-drift touching ONE surface. NO hook is fired by hand.
    out, _ = _run_unit(
        root, "feature-design", targets=["Button"],
        emit={"implement": {"ui-drift": {"screens": ["settings"], "components": ["Button"]}}})

    assert out.get("workflow") == "feature-design"
    assert out["phases"][:2] == ["library-state", "plan"]
    # (a) the workflow AGGREGATE actually carries the emitted drift under evidence —
    #     this is what core threaded into the live unit-close fire.
    assert out["receipt"]["evidence"]["ui-drift"]["screens"] == ["settings"]

    # (b) uiux's real _on_close flipped exactly that surface stale; sibling stays fresh.
    st = _statuses(root)
    assert st["settings"] == "stale"
    assert st["home"] == "fresh"

    # (c) both drift counters bumped (ui-drift receipt carries no ux signal -> conservative).
    assert library_state._drift_counts(root) == (1, 1)

    # (d) the "design-sync due" cadence note was surfaced by the live hook.
    due = [n for n in journal.notes(root) if n.get("body", "").startswith("design-sync due")]
    assert due, journal.notes(root)
    note = due[-1]
    assert "screenshots (1 stale)" in note["body"]
    assert note["screenshots_stale"] == 1
    assert note["ui_drift"] == 1 and note["ux_drift"] == 1

    # nothing misrouted.
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 2 — a SECOND plugin rides the same per-unit event.
# ════════════════════════════════════════════════════════════════════════════

def test_second_contributor_rides_unit_close(tmp_path):
    _close_recorder.reset()
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": 0, "ux_drift": 0}, with_recorder=True)

    out, _ = _run_unit(
        root, "feature-design", targets=["Button"],
        emit={"implement": {"ui-drift": {"screens": ["settings"]}}})

    # the recorder's unit-close hook fired exactly once, with the driven unit + a
    # receipt carrying the same evidence uiux got.
    closes = [r for r in _close_recorder.RECEIVED if r["step"] == "unit-close"]
    assert len(closes) == 1, _close_recorder.RECEIVED
    got = closes[0]
    assert got["unit"] == out["unit"] == "u-feature-design"
    assert (got["receipt"] or {}).get("evidence", {}).get("ui-drift", {}).get("screens") == ["settings"]


# ════════════════════════════════════════════════════════════════════════════
# Scenario 3 — the run-level batch `close` still fires exactly once (unchanged).
# ════════════════════════════════════════════════════════════════════════════

def test_batch_close_still_fires_once(tmp_path):
    _close_recorder.reset()
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": 0, "ux_drift": 0}, with_recorder=True)

    plan = R.Plan(units=[R.Unit("u1", _sit(root, workflow="feature-design", targets=["Button"]))])
    R.run(plan, contributors_for(root), RecordingExecutor(), root)

    close_fires = [r for r in _close_recorder.RECEIVED if r["step"] == "close"]
    unit_close_fires = [r for r in _close_recorder.RECEIVED if r["step"] == "unit-close"]
    assert len(close_fires) == 1, _close_recorder.RECEIVED       # batch close: exactly once
    assert len(unit_close_fires) == 1                            # one unit -> one unit-close


# ════════════════════════════════════════════════════════════════════════════
# Scenario 4 — unit-close fires EXACTLY once for a workflow unit (no duplicate
# across the run_unit -> run_workflow path).
# ════════════════════════════════════════════════════════════════════════════

def test_unit_close_fires_exactly_once(tmp_path):
    _close_recorder.reset()
    root = _build_root(tmp_path, manifest=[_fresh("settings")],
                       drift={"ui_drift": 0, "ux_drift": 0}, with_recorder=True)

    _run_unit(root, "feature-design", targets=["Button"])

    unit_close = [r for r in _close_recorder.RECEIVED if r["step"] == "unit-close"]
    assert len(unit_close) == 1, _close_recorder.RECEIVED        # not 2 (no run_unit+run_workflow dup)
    # run_unit alone does NOT fire the run-level batch close.
    assert [r for r in _close_recorder.RECEIVED if r["step"] == "close"] == []


# ── standalone runner: PASS summary + non-zero exit on failure ──────────────────

if __name__ == "__main__":
    import pytest
    code = pytest.main([__file__, "-q"])
    if code == 0:
        print("\nPASS: the per-unit `unit-close` hook delivers a unit's receipt to plugins "
              "through the LIVE praxis run path with NO hand-fired hooks — a feature-design "
              "unit's emitted ui-drift reaches uiux's real _on_close (surface flipped stale, "
              "sibling fresh, drift bumped, 'design-sync due' note surfaced); a second "
              "config-registered contributor rides the same event once with the same unit + "
              "receipt; the run-level batch `close` still fires exactly once; and `unit-close` "
              "fires exactly once per unit (no run_unit/run_workflow duplicate).")
    else:
        print("\nFAIL: see pytest output above.")
    sys.exit(code)

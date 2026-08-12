"""End-to-end proof that the fact-predicate routing fix works through the LIVE
praxis `run.run_unit` path — the same seam a real conductor drives.

Three scenarios, all against throwaway praxis roots with `uiux` registered as a
contributor via `.praxis/config.json` (exactly as a live root would), driven
through `run.run_unit` -> `registry.resolve_workflows` -> `workflow_run.run_workflow`:

  1. THE REGRESSION (must be GREEN): the original regime error was a feature unit
     with UI/UX libraries present but NO screenshot manifest misrouting into
     `screenshot-capture`. With the fact-predicate edges + facts-only
     `library_state.evaluate`, `feature-design` must route library-state -> plan and
     emit ZERO `phase.route_unmatched` events.

  2. BOOTSTRAP ORDERING via fact predicates: bare `has_ui:yes` root walks
     ui-library-init -> (ui present) screenshot-capture -> (manifest present)
     ux-library-init -> (all present) the explicit `pass -> close` exit, with NO
     `phase.route_unmatched` at the terminal step.

  3. FAILURES STILL ANNOUNCED (negative): a throwaway workflow with a facts-emitting
     deterministic phase whose facts match no predicate edge and that has no
     default/pass edge journals `phase.route_unmatched` kind="no-match"; with
     `stall-on-unmatched-route:true` the walk STALLS (`phase.stalled`).

Run:  python3 -m pytest tests/test_fact_routing_e2e.py -q
      python3 tests/test_fact_routing_e2e.py       # standalone: PASS summary, non-zero on fail
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
from contributors import contributors_for  # noqa: E402
from situation import Situation  # noqa: E402
from workflow import EdgeType, Phase, Workflow  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


# ── the executor that drives the LIVE walk: records phases, advances via receipts ──

class RecordingExecutor:
    """A real `run.Executor`: records each phase's `composed` map and returns a
    `produces` receipt so the walk advances along its `pass`/`fact` edges."""

    def __init__(self):
        self.seen: list[dict] = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result", evidence={"produces": f"art-{len(self.seen)}"})


# ── root builder: registers uiux via config, like a real root ────────────────────

def _build_root(tmp_path, *, ui=False, ux=False, screenshots=False, drift=None,
                stall_on_unmatched=False) -> Path:
    root = Path(tmp_path)
    config.ensure(root)
    config.write(root, "contributors", {"uiux": "uiux_plugin:make"})
    uiux_cfg = {"has_ui": "yes"}
    if drift is not None:
        uiux_cfg["library_drift"] = {"since_last_sync": drift}
    config.write(root, "uiux", uiux_cfg)
    if stall_on_unmatched:
        # the core/unnamed scope flag the run_workflow no-match guard reads.
        config.write(root, None, {"stall-on-unmatched-route": "true"})
    if ui:
        _write_ui(root)
    if ux:
        _write_ux(root)
    if screenshots:
        library_state.write_manifest(root, [
            {"screen": "settings", "file": "settings.png", "status": "fresh",
             "components": ["Button"]}])
    return root


def _write_ui(root):
    p = Path(root) / "docs" / "design" / "ui-library.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# UI library\n\n## Button\n- token: color.primary\n")


def _write_ux(root):
    p = Path(root) / "docs" / "design" / "ux-library.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# UX library\n\n## Onboarding\n- three steps\n")


def _write_manifest(root):
    library_state.write_manifest(root, [
        {"screen": "settings", "file": "settings.png", "status": "fresh",
         "components": ["Button"]}])


def _sit(root, *, workflow=None):
    return Situation(task_kind="change", intent="fact-routing-e2e", subject="design",
                     phase="none", root=str(root), workflow=workflow)


def _unmatched(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.route_unmatched"]


def _stalled(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.stalled"]


def _run_unit(root, workflow):
    ex = RecordingExecutor()
    out = R.run_unit(root, R.Unit(f"u-{workflow}", _sit(root, workflow=workflow)),
                     contributors_for(root), ex)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Scenario 1 — THE REGRESSION: libraries present, NO manifest, low drift.
# The original regime error was this unit misrouting into screenshot-capture.
# ════════════════════════════════════════════════════════════════════════════

def test_regression_feature_libs_present_no_manifest_routes_to_plan(tmp_path):
    root = _build_root(tmp_path, ui=True, ux=True, screenshots=False, drift=0)

    out = _run_unit(root, "feature-design")

    # the workflow actually resolved + walked the LIVE path (not single-dispatch).
    assert out.get("workflow") == "feature-design"
    # library-state -> plan, NOT screenshot-capture (the fixed regime error).
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "plan"
    assert "screenshot-capture" not in out["phases"]
    # the proof the regime error is gone: zero unmatched-route events for the run.
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 2 — BOOTSTRAP ORDERING via fact predicates, driven iteratively.
# Each drive is an independent LIVE run_unit; the library files are created
# between drives (the executor is a recorder and does not author them).
# ════════════════════════════════════════════════════════════════════════════

def test_bootstrap_ordering_via_predicates(tmp_path):
    # step 1: bare root -> ui-library-init FIRST (library absence predicate).
    root = _build_root(tmp_path)
    out = _run_unit(root, "design-bootstrap")
    assert out.get("workflow") == "design-bootstrap"
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "ui-library-init"

    # step 2: ui exists, no manifest -> screenshot-capture next (declaration order).
    _write_ui(root)
    out = _run_unit(root, "design-bootstrap")
    assert out["phases"][1] == "screenshot-capture"

    # step 3: ui + manifest exist, no ux -> ux-library-init next.
    _write_manifest(root)
    out = _run_unit(root, "design-bootstrap")
    assert out["phases"][1] == "ux-library-init"

    # step 4: all present -> the explicit `pass -> close` exit, NO unmatched-route.
    _write_ux(root)
    out = _run_unit(root, "design-bootstrap")
    assert out["phases"] == ["library-state", "close"]
    assert _unmatched(root) == []


# ════════════════════════════════════════════════════════════════════════════
# Scenario 3 — FAILURES STILL ANNOUNCED (the observability the user kept).
# A throwaway workflow: a facts-emitting deterministic phase whose facts match
# NO predicate edge, with NO default/pass edge out of it.
# ════════════════════════════════════════════════════════════════════════════

def _dead_end_phase():
    """A deterministic phase that emits facts (passed) but names no route."""
    def _run(root, unit, composed):
        return {"passed": True, "facts": {"probe": {"value": 1}}, "produces": {"value": 1}}
    return Phase("probe", stance="neutral", delivery="deterministic",
                 intent="emit a fact no predicate matches", produces="probe", run=_run)


def _never(_ev):
    return False


def _dead_end_workflow():
    probe = _dead_end_phase()
    sink = Phase("sink", stance="neutral", delivery="inline",
                 intent="unreachable target", produces="none")
    return Workflow(
        name="dead-end-probe",
        phases=[probe, sink],
        edges=[
            # a predicate that never fires, and NO pass/default edge out of `probe`.
            ("probe", "sink", "fact", EdgeType.create, _never),
        ],
    )


def test_unmatched_fact_route_is_announced(tmp_path):
    root = _build_root(tmp_path)               # no stall flag
    wf = _dead_end_workflow()
    out = run_workflow(root, R.Unit("dead", _sit(root)), wf, contributors_for(root),
                       RecordingExecutor())

    assert out["phases"] == ["probe"]          # walked probe, then nothing matched
    ums = _unmatched(root)
    assert len(ums) == 1
    assert ums[0]["kind"] == "no-match"
    assert ums[0]["phase"] == "probe"
    # without the stall flag the walk does not stall — it just records the miss.
    assert ums[0].get("resolved") is None
    assert _stalled(root) == []


def test_unmatched_fact_route_stalls_when_flag_set(tmp_path):
    root = _build_root(tmp_path, stall_on_unmatched=True)
    wf = _dead_end_workflow()
    out = run_workflow(root, R.Unit("dead2", _sit(root)), wf, contributors_for(root),
                       RecordingExecutor())

    ums = _unmatched(root)
    assert len(ums) == 1 and ums[0]["kind"] == "no-match"
    assert ums[0]["resolved"] == "stall"
    # with the flag the walk STALLS on the unmatched fact route.
    stalls = _stalled(root)
    assert stalls and stalls[-1]["phase"] == "probe"
    assert "unmatched fact route" in (stalls[-1].get("note") or "")


# ── standalone runner: PASS summary + non-zero exit on failure ──────────────────

if __name__ == "__main__":
    import pytest
    code = pytest.main([__file__, "-q"])
    if code == 0:
        print("\nPASS: fact-predicate routing verified end-to-end through the LIVE "
              "run_unit path — the regime error is fixed (feature -> plan, zero "
              "route_unmatched), bootstrap ordering is predicate-driven to a clean "
              "close, and genuine no-match failures are still journaled (and stall "
              "under stall-on-unmatched-route).")
    else:
        print("\nFAIL: see pytest output above.")
    sys.exit(code)

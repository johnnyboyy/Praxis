"""§5 — the two workflows' fact-predicate routing out of `library-state`.

Drives the LIVE `workflow_run.run_workflow` with a stub executor, so the real
`_choose_edge` predicate tier evaluates `library_state.evaluate`'s facts. Asserts
the first hop out of `library-state` for each library/drift configuration, plus the
regression guard for the fixed bug (a missing manifest must NOT misroute a feature).
"""

import config
import journal
import registry
import run as R
import uiux_plugin
from situation import Situation
from workflow_run import run_workflow


class _Capture:
    """A real executor stub: records phases and returns a `produces` receipt so the
    walk advances along its `pass`/`fact` edges."""

    def __init__(self):
        self.seen = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result", evidence={"produces": f"art-{len(self.seen)}"})


def _sit(root):
    return Situation(task_kind="change", intent="route", subject="design",
                     phase="none", root=str(root))


def _setup(root, **uiux_cfg):
    config.ensure(root)
    config.write(root, "uiux", uiux_cfg)


def _write_ui(root):
    p = root / "docs" / "design" / "ui-library.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# UI library\n")


def _write_ux(root):
    p = root / "docs" / "design" / "ux-library.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# UX library\n")


def _write_manifest(root):
    import library_state
    m = library_state.manifest_path(root)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text("# screenshots\n")


def _bootstrap():
    return uiux_plugin.DESIGN_BOOTSTRAP


def _feature():
    return uiux_plugin.FEATURE_DESIGN


def _run(root, wf):
    out = run_workflow(root, R.Unit("u1", _sit(root)), wf, [], _Capture())
    return out


def _unmatched(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.route_unmatched"]


# ── design-bootstrap: route on library-absence ─────────────────────────────────

def test_bootstrap_bare_root_routes_to_ui_init(tmp_path):
    _setup(tmp_path, has_ui="yes")
    out = _run(tmp_path, _bootstrap())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "ui-library-init"


def test_bootstrap_ui_present_no_manifest_routes_to_screenshot(tmp_path):
    _setup(tmp_path, has_ui="yes")
    _write_ui(tmp_path)
    out = _run(tmp_path, _bootstrap())
    # ui present, no manifest, no ux -> screenshot BEFORE ux (declaration order).
    assert out["phases"][1] == "screenshot-capture"


def test_bootstrap_ui_and_screenshots_present_routes_to_ux(tmp_path):
    _setup(tmp_path, has_ui="yes")
    _write_ui(tmp_path)
    _write_manifest(tmp_path)
    out = _run(tmp_path, _bootstrap())
    assert out["phases"][1] == "ux-library-init"


def test_bootstrap_all_present_exits_to_close_no_unmatched(tmp_path):
    _setup(tmp_path, has_ui="yes")
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _write_manifest(tmp_path)
    out = _run(tmp_path, _bootstrap())
    assert out["phases"] == ["library-state", "close"]   # explicit pass -> close exit
    assert _unmatched(tmp_path) == []                    # a real default, not a no-match


# ── feature-design: drift-gated sync, screenshots NOT wired ────────────────────

def test_feature_drift_below_threshold_routes_to_plan(tmp_path):
    _setup(tmp_path, has_ui="yes", library_drift={"since_last_sync": 2})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _write_manifest(tmp_path)
    out = _run(tmp_path, _feature())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "plan"
    assert _unmatched(tmp_path) == []


def test_feature_drift_at_threshold_no_longer_routes_to_ui_sync(tmp_path):
    """Piggyback removed (spec §4): feature-design no longer branches to a ui-sync at
    threshold — library-state's sole route out is `pass -> plan`. The at-threshold sync
    behavior now lives in test_design_sync_routing.py."""
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 3, "ux_drift": 3})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _write_manifest(tmp_path)
    out = _run(tmp_path, _feature())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "plan"
    assert "ui-library-sync" not in out["phases"]
    assert _unmatched(tmp_path) == []


def test_feature_missing_manifest_low_drift_still_routes_to_plan(tmp_path):
    """Regression guard for the fixed bug: a missing screenshot manifest must NOT
    misroute a feature to screenshot-capture, and must not emit route_unmatched."""
    _setup(tmp_path, has_ui="yes", library_drift={"since_last_sync": 0})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    # no manifest written -> libraries.screenshots == False
    out = _run(tmp_path, _feature())
    assert out["phases"][1] == "plan"
    assert "screenshot-capture" not in out["phases"]
    assert _unmatched(tmp_path) == []


# ── both workflows validate against the merged phase table ─────────────────────

def test_both_workflows_validate(tmp_path):
    contributor = uiux_plugin.make(str(tmp_path))
    phases = registry.resolve_phases(str(tmp_path), [contributor])
    for w in contributor.workflows():
        assert registry.validate_workflow(w, phases) == [], w.name

"""§2 — the `design-sync` workflow's fact-predicate routing out of `library-state`.

Drives the LIVE `workflow_run.run_workflow` with a stub executor so the real
`_choose_edge` predicate tier evaluates `library_state.evaluate`'s per-library
staleness facts. Asserts the first hop for each screenshots/ui/ux configuration:
screenshots route EAGER (any stale surface), ui/ux route THRESHOLD-gated, and an
all-clean root exits `library-state -> close` with no `route_unmatched`.

Also covers the surgical recapture mechanism: the disclosure names only the stale
set, and an accepted `screenshot-library-sync` close clears exactly those flags.
"""

import config
import journal
import library_state
import registry
import run as R
import uiux_plugin
from contributors import HookContext
from situation import Situation
from workflow_run import run_workflow


class _Capture:
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


def _manifest(root, *entries):
    library_state.write_manifest(root, list(entries))


def _fresh(screen):
    return {"screen": screen, "file": f"{screen}.png", "status": "fresh", "components": []}


def _stale(screen):
    return {"screen": screen, "file": f"{screen}.png", "status": "stale", "components": []}


def _sync():
    return uiux_plugin.DESIGN_SYNC


def _run(root, wf):
    return run_workflow(root, R.Unit("u1", _sit(root)), wf, [], _Capture())


def _unmatched(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.route_unmatched"]


# ── EAGER: any stale screenshot -> surgical recapture ──────────────────────────

def test_sync_stale_screenshots_route_eager(tmp_path):
    # fresh drift 0, one manifest entry stale, ui/ux below threshold.
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 0, "ux_drift": 0})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _manifest(tmp_path, _stale("settings"))
    out = _run(tmp_path, _sync())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "screenshot-library-sync"


# ── THRESHOLD-gated: ui / ux drift at their own threshold ──────────────────────

def test_sync_ui_drift_at_threshold_routes_ui(tmp_path):
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 3, "ux_drift": 0})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _manifest(tmp_path, _fresh("settings"))   # nothing stale
    out = _run(tmp_path, _sync())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "ui-library-sync"


def test_sync_ux_drift_at_threshold_routes_ux(tmp_path):
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 0, "ux_drift": 3})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _manifest(tmp_path, _fresh("settings"))
    out = _run(tmp_path, _sync())
    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "ux-library-sync"


# ── declaration-order priority: screenshots beat ui/ux thresholds ──────────────

def test_sync_eager_beats_threshold(tmp_path):
    # stale screenshot AND ui_drift over threshold -> screenshots first (priority ladder).
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 5, "ux_drift": 5})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _manifest(tmp_path, _stale("settings"))
    out = _run(tmp_path, _sync())
    assert out["phases"][1] == "screenshot-library-sync"


# ── all clean -> explicit pass -> close, no route_unmatched ─────────────────────

def test_sync_all_clean_exits_to_close_no_unmatched(tmp_path):
    _setup(tmp_path, has_ui="yes", library_drift={"ui_drift": 0, "ux_drift": 0})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _manifest(tmp_path, _fresh("settings"))
    out = _run(tmp_path, _sync())
    assert out["phases"] == ["library-state", "close"]
    assert _unmatched(tmp_path) == []


# ── validation against the merged phase table ──────────────────────────────────

def test_design_sync_validates(tmp_path):
    contributor = uiux_plugin.make(str(tmp_path))
    phases = registry.resolve_phases(str(tmp_path), [contributor])
    assert registry.validate_workflow(uiux_plugin.DESIGN_SYNC, phases) == []


# ── surgical recapture: only the stale set is disclosed / freshened ─────────────

class _Unit:
    def __init__(self, uid, phase_name=None):
        self.id = uid
        self.situation = Situation(task_kind="change", intent="x", subject="design",
                                   phase="none", phase_name=phase_name, targets=[])


def test_recapture_disclosure_names_only_stale_set(tmp_path):
    root = str(tmp_path)
    _setup(root, has_ui="yes")
    _manifest(root, _stale("settings"), _fresh("home"), _stale("profile"))
    u = uiux_plugin.make(root)
    sit = Situation(task_kind="change", intent="x", subject="design",
                    phase="none", phase_name="screenshot-library-sync", targets=[])
    out = u.contribute(sit)
    body = out[0].body
    assert "surgical" in body
    assert "settings" in body and "profile" in body
    # the fresh surface is NOT in the recapture verb line (surgical, stale-only).
    verb_line = [ln for ln in body.splitlines() if "Recapture ONLY" in ln][0]
    assert "home" not in verb_line


def test_close_screenshot_sync_marks_reshot_fresh(tmp_path):
    root = str(tmp_path)
    _setup(root, has_ui="yes")
    _manifest(root, _stale("settings"), _stale("profile"))
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="screenshot-library-sync"),
                      receipt={"evidence": {"decision": {"accept": True},
                               "screenshots": {"captured": ["settings"]}}})
    uiux_plugin.make(root)._on_close(ctx)
    statuses = {e["screen"]: e["status"] for e in library_state.read_manifest(root)}
    assert statuses == {"settings": "fresh", "profile": "stale"}


def test_close_screenshot_sync_default_clears_all_stale(tmp_path):
    root = str(tmp_path)
    _setup(root, has_ui="yes")
    _manifest(root, _stale("settings"), _stale("profile"))
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="screenshot-library-sync"),
                      receipt={"evidence": {"decision": {"accept": True}}})
    uiux_plugin.make(root)._on_close(ctx)
    assert all(e["status"] == "fresh" for e in library_state.read_manifest(root))


def test_close_recommendation_note_surfaces_due(tmp_path):
    root = tmp_path   # Path: add_note journals to root/.praxis (the live path passes a Path)
    _setup(root, has_ui="yes", library_drift={"ui_drift": 2, "ux_drift": 2})
    _manifest(root, _fresh("settings"))
    # an implement close on a drift-touching unit bumps both counters to 3 (== threshold).
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1", phase_name="implement"),
                      receipt={"evidence": {"ui-drift": {"components": ["Button"]}}})
    uiux_plugin.make(root)._on_close(ctx)
    notes = journal.notes(tmp_path)
    due_notes = [n for n in notes if n.get("body", "").startswith("design-sync")]
    assert due_notes, notes
    note = due_notes[-1]
    assert "ui" in note["due"] and "ux" in note["due"]
    assert note["ui_drift"] == 3 and note["ux_drift"] == 3
    assert note["threshold"] == library_state.DRIFT_THRESHOLD

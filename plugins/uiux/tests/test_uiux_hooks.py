"""§4.1 — the `close` hook: drift bump/reset, screenshot-stale, file-accepted-decision."""

import config
import contributors
import deferred_queue as dq
import library_state
import uiux_plugin
from contributors import HookContext
from situation import Situation


UI_LIBRARY = """# UI library

## Button
- token: color.primary #2563eb

## Empty state
- preserve filters, no reset
"""

DEFERRED = """# Deferred decisions

```yaml
decisions:
  - id: results-empty-state
    stance: convergent
    domain: validation-feedback
    question: "Preserve filters or offer reset?"
    context: "Results panel."
    source-workstream: search
    created: 2026-07-14
    blocking: no
    provisional-treatment: "Preserve filters."
    status: queued
```
"""


def _root(tmp_path, **cfg):
    config.ensure(str(tmp_path))
    config.write(str(tmp_path), "uiux", {"has_ui": "yes", **cfg})
    return str(tmp_path)


class _Unit:
    def __init__(self, uid, phase_name=None, targets=None):
        self.id = uid
        self.situation = Situation(task_kind="change", intent="x", subject="design",
                                   phase="none", phase_name=phase_name, targets=targets or [])


def _uiux(root):
    return uiux_plugin.make(root)


def _drift(root):
    ui_d, _ = library_state._drift_counts(root)
    return ui_d


def _drifts(root):
    return library_state._drift_counts(root)


def test_hooks_close_callable_and_validates(tmp_path):
    u = _uiux(_root(tmp_path))
    assert callable(u.hooks()["unit-close"])
    assert contributors.validate_contributor(u) == []


def test_close_bumps_drift_and_marks_screenshot_stale(tmp_path):
    root = _root(tmp_path)
    library_state.write_manifest(root, [{"screen": "settings", "file": "settings.png",
                                         "status": "fresh", "components": []}])
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1", phase_name="implement"),
                      receipt={"evidence": {"ui-drift": {"screens": ["settings"]}}})
    _uiux(root)._on_close(ctx)
    assert _drift(root) == 1
    entries = {e["screen"]: e for e in library_state.read_manifest(root)}
    assert entries["settings"]["status"] == "stale"


def test_close_new_screen_appended_stale(tmp_path):
    root = _root(tmp_path)
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1", phase_name="implement"),
                      receipt={"evidence": {"ui-drift": {"screens": ["brand-new"]}}})
    _uiux(root)._on_close(ctx)
    entries = {e["screen"]: e for e in library_state.read_manifest(root)}
    assert entries["brand-new"]["status"] == "stale"


def test_close_accepted_sync_resets_drift(tmp_path):
    root = _root(tmp_path, library_drift={"since_last_sync": 3})
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="ui-library-sync"),
                      receipt={"evidence": {"decision": {"accept": True, "target": "ui",
                                            "content": "## Button\n- updated\n"}}})
    _uiux(root)._on_close(ctx)
    assert _drift(root) == 0


def test_close_bumps_both_drift_counters(tmp_path):
    root = _root(tmp_path)
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1", phase_name="implement"),
                      receipt={"evidence": {"ui-drift": {"screens": ["settings"]}}})
    _uiux(root)._on_close(ctx)
    assert _drifts(root) == (1, 1)


def test_close_ui_sync_resets_only_ui(tmp_path):
    root = _root(tmp_path, library_drift={"ui_drift": 3, "ux_drift": 3})
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="ui-library-sync"),
                      receipt={"evidence": {"decision": {"accept": True, "target": "ui",
                                            "content": "## Button\n- updated\n"}}})
    _uiux(root)._on_close(ctx)
    assert _drifts(root) == (0, 3)


def test_close_ux_sync_resets_only_ux(tmp_path):
    root = _root(tmp_path, library_drift={"ui_drift": 3, "ux_drift": 3})
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="ux-library-sync"),
                      receipt={"evidence": {"decision": {"accept": True, "target": "ux",
                                            "content": "## Flow\n- updated\n"}}})
    _uiux(root)._on_close(ctx)
    assert _drifts(root) == (3, 0)


def test_legacy_since_last_sync_migrates(tmp_path):
    root = _root(tmp_path, library_drift={"since_last_sync": 2})
    facts = library_state.evaluate(root)["facts"]["library_state"]
    assert facts["ui_drift"] == 2
    assert facts["ux_drift"] == 2
    assert facts["drift"] == 2


def test_evaluate_exposes_per_library_staleness(tmp_path):
    root = _root(tmp_path)
    library_state.write_manifest(root, [
        {"screen": "settings", "file": "settings.png", "status": "stale", "components": []},
        {"screen": "home", "file": "home.png", "status": "fresh", "components": []},
    ])
    facts = library_state.evaluate(root)["facts"]["library_state"]
    assert facts["screenshots"]["stale"] == ["settings"]
    assert facts["screenshots"]["stale_count"] == 1
    assert facts["screenshots"]["any_stale"] is True


def test_mark_stale_all_surfaces_marks_every_surface(tmp_path):
    root = _root(tmp_path)
    library_state.write_manifest(root, [
        {"screen": "settings", "file": "settings.png", "status": "fresh", "components": []},
        {"screen": "home", "file": "home.png", "status": "fresh", "components": []},
    ])
    assert library_state.mark_stale(root, all_surfaces=True) is True
    statuses = {e["screen"]: e["status"] for e in library_state.read_manifest(root)}
    assert statuses == {"settings": "stale", "home": "stale"}


def test_close_global_flag_marks_every_surface_stale(tmp_path):
    root = _root(tmp_path)
    library_state.write_manifest(root, [
        {"screen": "settings", "file": "settings.png", "status": "fresh", "components": []},
        {"screen": "home", "file": "home.png", "status": "fresh", "components": []},
    ])
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1", phase_name="implement"),
                      receipt={"evidence": {"ui-drift": {"global": True}}})
    _uiux(root)._on_close(ctx)
    statuses = {e["screen"]: e["status"] for e in library_state.read_manifest(root)}
    assert statuses == {"settings": "stale", "home": "stale"}


def test_mark_fresh_clears_stale(tmp_path):
    root = _root(tmp_path)
    library_state.write_manifest(root, [
        {"screen": "settings", "file": "settings.png", "status": "stale", "components": []},
        {"screen": "home", "file": "home.png", "status": "stale", "components": []},
    ])
    assert library_state.mark_fresh(root, screens=["settings"]) is True
    statuses = {e["screen"]: e["status"] for e in library_state.read_manifest(root)}
    assert statuses == {"settings": "fresh", "home": "stale"}
    # default: clears all remaining stale.
    assert library_state.mark_fresh(root) is True
    assert all(e["status"] == "fresh" for e in library_state.read_manifest(root))


def test_close_files_accepted_decision_and_resolves_deferred(tmp_path):
    root = _root(tmp_path)
    ui = tmp_path / "docs" / "design" / "ui-library.md"
    ui.parent.mkdir(parents=True, exist_ok=True)
    ui.write_text(UI_LIBRARY)
    qpath = dq.queue_path(root)
    __import__("os").makedirs(__import__("os").path.dirname(qpath), exist_ok=True)
    open(qpath, "w").write(DEFERRED)

    decision = {"accept": True, "target": "ui", "section": "Empty state",
                "content": "## Empty state\n- offer a reset action\n",
                "resolves": "results-empty-state",
                "resolution": "Ratified: add a reset action."}
    ctx = HookContext(root=root, step="unit-close",
                      unit=_Unit("u1", phase_name="design-decision-review"),
                      receipt={"evidence": {"decision": decision}})
    _uiux(root)._on_close(ctx)

    filed = ui.read_text()
    assert "offer a reset action" in filed          # new section filed in
    assert "preserve filters, no reset" not in filed  # superseded section replaced outright
    entry = {e["id"]: e for e in dq.parse_deferred(qpath)}["results-empty-state"]
    assert entry["status"] == "resolved"            # kept as a trace, not deleted
    assert entry["resolution"] == "Ratified: add a reset action."


def test_close_failsoft_no_state(tmp_path):
    root = _root(tmp_path)
    # no manifest, no library, no drift config, no receipt fields — must not raise.
    ctx = HookContext(root=root, step="unit-close", unit=_Unit("u1"), receipt={})
    _uiux(root)._on_close(ctx)  # no exception == pass

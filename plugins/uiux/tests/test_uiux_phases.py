"""§1.4 — the phase/workflow objects resolve and validate through the real registry."""

import registry
import uiux_plugin
from workflow import Phase


def _uiux(root):
    return uiux_plugin.make(str(root))


EIGHT = {
    "library-state", "ui-library-init", "ux-library-init", "ui-library-sync",
    "ux-library-sync", "screenshot-capture", "screenshot-library-sync",
    "design-decision-review",
}


def test_resolve_phases_contains_all_eight_plus_seed_plan(tmp_path):
    phases = registry.resolve_phases(str(tmp_path), [_uiux(tmp_path)])
    assert EIGHT <= set(phases)
    assert "plan" in phases  # seed still present


def test_resolve_workflows_contains_all_three(tmp_path):
    workflows = registry.resolve_workflows(str(tmp_path), [_uiux(tmp_path)])
    assert "design-bootstrap" in workflows
    assert "feature-design" in workflows
    assert "design-sync" in workflows


def test_every_phase_validates(tmp_path):
    for p in _uiux(tmp_path).phases():
        assert registry.validate_phase(p) == []


def test_library_state_phase_carries_run(tmp_path):
    ph = {p.name: p for p in _uiux(tmp_path).phases()}
    ls = ph["library-state"]
    assert ls.delivery == "deterministic"
    assert callable(ls.run)


def test_both_workflows_validate_against_merged_table(tmp_path):
    contributor = _uiux(tmp_path)
    phases = registry.resolve_phases(str(tmp_path), [contributor])
    for w in contributor.workflows():
        assert registry.validate_workflow(w, phases) == [], w.name


def test_a_uiux_plan_phase_does_not_override_seed(tmp_path):
    """Guards the boundary: a plugin phase named `plan` is skipped for the seed."""

    class Shadow:
        source = "shadow"

        def phases(self):
            return [Phase("plan", stance="convergent", intent="not the seed")]

    phases = registry.resolve_phases(str(tmp_path), [Shadow()])
    assert phases["plan"].intent == "extract an open request into units/edges"  # seed wins

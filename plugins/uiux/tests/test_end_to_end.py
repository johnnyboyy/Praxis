"""End-to-end verification that the upgraded `uiux` full plugin works through the
LIVE praxis workflow path.

Everything here is driven through the real seams that just landed:
  * `run.run_unit` resolves `situation.workflow` via `registry.resolve_workflows`
    and hands off to `workflow_run.run_workflow` (the live drive).
  * `library_state.evaluate` is the deterministic `Phase.run` for `library-state`;
    it emits FACTS only and each workflow's fact-predicate edges own routing.
  * `situation.phase_name` is the channel `contribute` keys its disclosure on.
  * `Contributor.surface` produces the docs-only edit lease, journaled by
    `run_unit` at `unit.framed` and enforced by the real `gate.gate_decision`.

Both `uiux` (uiux_plugin:make) and `corpora` (corpora.injector:make) are registered
as contributors on a throwaway praxis root, exactly as a real root would register
them — via `.praxis/config.json` — and loaded through `contributors_for`.

Run:  python3 -m pytest tests/test_end_to_end.py -q
      python3 tests/test_end_to_end.py        # standalone: prints PASS, non-zero on fail
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- sys.path: praxis skill, praxis/scripts (gate/units), this plugin, corpora pkg ---
_PRAXIS = str(Path(__file__).resolve().parents[3])
_PRAXIS_SCRIPTS = _PRAXIS + "/scripts"
_PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
_CORPORA_PKG_PARENT = str(Path(__file__).resolve().parents[2] / "corpora")
for _p in (_PRAXIS, _PRAXIS_SCRIPTS, _PLUGIN_ROOT, _CORPORA_PKG_PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import gate  # noqa: E402
import journal  # noqa: E402
import library_state  # noqa: E402
import run as R  # noqa: E402
from contributors import contributors_for, gather  # noqa: E402
from situation import Situation  # noqa: E402


UI_LIBRARY = """# UI library

## Button
- token: color.primary must stay #2563eb
- radius: 8px, never square

## Empty state
- always offer a reset action
- copy stays under 12 words
"""

UX_LIBRARY = """# UX library

## Onboarding flow
- three steps, never more
"""


# ── the executor that drives the live path: records what each phase saw ─────────

class RecordingExecutor:
    """A real `run.Executor`: records the per-phase `composed` map (phase name +
    the contributions the contributors emitted) and returns a `produces` receipt so
    the workflow advances along its `pass` edges."""

    def __init__(self):
        self.seen: list[dict] = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result",
                         evidence={"produces": f"art-{len(self.seen)}"})

    def uiux_at(self, phase_name):
        """The uiux-sourced contributions the executor saw at `phase_name`."""
        for c in self.seen:
            if c.get("phase") == phase_name:
                return [x for x in c.get("contributions", []) if x.source == "uiux"]
        return None


# ── root builder: registers BOTH contributors via config, like a real root ──────

def _build_root(tmp_path, *, ui=False, ux=False, screenshots=False, drift=None) -> Path:
    root = Path(tmp_path)
    config.ensure(root)
    # Register both process contributors exactly as a live root would.
    config.write(root, "contributors",
                 {"uiux": "uiux_plugin:make", "corpora": "corpora.injector:make"})
    # uiux's own config scope: has_ui, no library files present by default.
    uiux_cfg = {"has_ui": "yes"}
    if drift is not None:
        uiux_cfg["library_drift"] = {"since_last_sync": drift}
    config.write(root, "uiux", uiux_cfg)
    # corpora's scope: a project_shape with has-ui so its prune keeps the uiux
    # design domains (YAML parses `has-ui: yes` -> boolean True in applies-when).
    config.write(root, "corpora", {"project_shape": {"has-ui": True}})

    if ui:
        p = tmp_path / "docs" / "design" / "ui-library.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(UI_LIBRARY)
    if ux:
        p = tmp_path / "docs" / "design" / "ux-library.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(UX_LIBRARY)
    if screenshots:
        library_state.write_manifest(root, [
            {"screen": "settings", "file": "settings.png", "status": "fresh",
             "components": ["Button"]},
        ])
    return root


def _sit(root, *, workflow=None, phase_name=None, targets=None, subject="design"):
    return Situation(task_kind="change", intent="e2e", subject=subject,
                     phase="none", phase_name=phase_name, root=str(root),
                     targets=targets or [], workflow=workflow)


def _phase_facts(root):
    return [e for e in journal.read(root) if e.get("event") == "phase.facts"]


# ════════════════════════════════════════════════════════════════════════════
# Scenario 1 — BOOTSTRAP: the deterministic library-state fact drives routing
# ════════════════════════════════════════════════════════════════════════════

def test_bootstrap_routes_to_ui_library_init_first(tmp_path):
    """No libraries yet: the LIVE run_unit -> run_workflow drive must run the
    deterministic `library-state` phase and route to `ui-library-init` FIRST."""
    root = _build_root(tmp_path)              # has_ui:yes, NO library files
    contribs = contributors_for(root)
    assert {c.source for c in contribs} == {"uiux", "corpora"}

    ex = RecordingExecutor()
    out = R.run_unit(root, R.Unit("boot", _sit(root, workflow="design-bootstrap")),
                     contribs, ex)

    # the workflow actually resolved + walked (not single-dispatch)
    assert out.get("workflow") == "design-bootstrap"
    assert out["phases"][0] == "library-state"      # deterministic gate ran first
    assert out["phases"][1] == "ui-library-init"     # routed to ui FIRST (no ui yet)

    # the deterministic phase emitted the eligibility fact, journaled as phase.facts
    facts = _phase_facts(root)
    assert facts, "library-state must journal its facts"
    ls = facts[0]["facts"]["library_state"]
    assert ls["libraries"] == {"ui": False, "ux": False, "screenshots": False}
    assert ls["next_bootstrap_step"] == "ui-library-init"


def test_bootstrap_reevaluates_to_screenshot_after_ui_exists(tmp_path):
    """Once `ui-library.md` exists, a fresh LIVE drive must re-derive eligibility and
    route to the screenshot init (ordering ui -> {screenshot, ux})."""
    root = _build_root(tmp_path, ui=True)      # ui present, ux + screenshots absent
    contribs = contributors_for(root)

    ex = RecordingExecutor()
    out = R.run_unit(root, R.Unit("boot2", _sit(root, workflow="design-bootstrap")),
                     contribs, ex)

    assert out["phases"][0] == "library-state"
    assert out["phases"][1] == "screenshot-capture"   # ui exists -> screenshot next

    # completeness of the ordering: with ui + manifest present, the only absent
    # library is ux — so the ux-init predicate is the one that will fire next.
    root2 = _build_root(tmp_path / "r2", ui=True, screenshots=True)
    ev = library_state.evaluate(root2)
    assert ev["passed"] is True
    assert "next" not in ev                          # facts-only: routing is the workflow's
    ls = ev["facts"]["library_state"]
    assert ls["libraries"] == {"ui": True, "ux": False, "screenshots": True}  # ux last


def test_design_phase_edit_lease_is_docs_only(tmp_path):
    """During a design/library phase the unit's edit lease (surface) is docs-only.
    Driven through the LIVE run_unit (which journals the lease at unit.framed via
    surface_for), then checked through the same gate praxis tests use."""
    root = _build_root(tmp_path, ui=True)
    contribs = contributors_for(root)

    # A design-phase unit: run_unit journals surface_for(...) into unit.framed, then
    # runs the workflow (which never journals unit.done -> the unit stays OPEN, so
    # gate.gate_decision sees the live lease).
    ex = RecordingExecutor()
    R.run_unit(root, R.Unit("lease",
                            _sit(root, workflow="design-bootstrap",
                                 phase_name="ui-library-sync")),
               contribs, ex)

    # the docs-only lease was journaled from the live surface() claim
    framed = [e for e in journal.read(root) if e.get("event") == "unit.framed"]
    assert framed and framed[-1]["surface"], "surface() lease must be journaled"
    lease = framed[-1]["surface"]
    assert any(g.startswith("docs") for g in lease)
    assert "*.md" in lease

    # a source edit is DENIED; a design-doc edit is ALLOWED — the design->code bar.
    src = str(tmp_path / "src" / "app.py")
    doc = str(tmp_path / "docs" / "design" / "ui-library.md")
    verdict_src, reason = gate.gate_decision(root, src)
    verdict_doc, _ = gate.gate_decision(root, doc)
    assert verdict_src == "deny"
    assert "lease surface" in (reason or "")
    assert verdict_doc == "allow"


# ════════════════════════════════════════════════════════════════════════════
# Scenario 2 — FEATURE: graduated disclosure per phase_name + corpora composition
# ════════════════════════════════════════════════════════════════════════════

def test_feature_design_discloses_per_phase_name(tmp_path):
    """Drive a `feature-design` unit through the LIVE path. The ui-sync piggyback is
    gone (spec §4): feature-design is now the plain feature path, so uiux's disclosure
    is INDEX-only at `plan` and it never branches to `ui-library-sync`."""
    root = _build_root(tmp_path, ui=True, ux=True, screenshots=True)   # libraries present
    contribs = contributors_for(root)

    ex = RecordingExecutor()
    out = R.run_unit(
        root,
        R.Unit("feat", _sit(root, workflow="feature-design", targets=["Button"])),
        contribs, ex)

    assert out.get("workflow") == "feature-design"
    # libraries present + drift low -> library-state passes straight to plan; no sync.
    assert out["phases"][0] == "library-state"
    assert "plan" in out["phases"]
    assert "ui-library-sync" not in out["phases"]      # piggyback removed (spec §4)

    # plan: INDEX only (one uiux contribution, disclosure=index, no library body).
    plan_c = ex.uiux_at("plan")
    assert plan_c is not None and len(plan_c) == 1
    assert plan_c[0].meta["disclosure"] == "index"
    assert "## Button" not in plan_c[0].body           # not a library body


def test_design_sync_discloses_divergent_ui_sync(tmp_path):
    """Drive a `design-sync` unit (ui drift at threshold) through the LIVE path. At the
    divergent `ui-library-sync` the disclosure is a curated pin + anti-mean WITHOUT the
    full library — the sync path that moved off feature-design (spec §2/§4)."""
    root = _build_root(tmp_path, ui=True, ux=True, screenshots=True, drift=3)
    contribs = contributors_for(root)

    ex = RecordingExecutor()
    out = R.run_unit(
        root,
        R.Unit("sync", _sit(root, workflow="design-sync", targets=["Button"])),
        contribs, ex)

    assert out.get("workflow") == "design-sync"
    # screenshots fresh, ui_drift == threshold -> library-state routes to ui-library-sync.
    assert out["phases"][0] == "library-state"
    assert "ui-library-sync" in out["phases"]

    # ui-library-sync (divergent): curated pin + anti-mean, NOT the full library.
    sync_c = ex.uiux_at("ui-library-sync")
    assert sync_c is not None
    kinds = {c.meta["disclosure"] for c in sync_c}
    assert "consistency-pin" in kinds
    assert "anti-mean" in kinds
    pin = next(c for c in sync_c if c.meta["disclosure"] == "consistency-pin")
    assert pin.priority == -5
    full = "\n".join(c.body for c in sync_c)
    assert "## Empty state" not in full                # a non-target section absent
    assert "disclosure" and all(c.meta.get("disclosure") != "full" for c in sync_c)


def test_corpora_still_composes_uiux_design_domains(tmp_path):
    """corpora, registered alongside uiux, still composes the uiux design domains
    (owner `uiux`) for a subject=design situation — the JUDGMENT face, untouched."""
    root = _build_root(tmp_path, ui=True, ux=True, screenshots=True)
    contribs = contributors_for(root)

    composed = gather(contribs, _sit(root, subject="design"), root=None)
    corpora_titles = [c.title for c in composed["contributions"] if c.source == "corpora"]
    # corpora renders each domain as "<owner>/<id> — principles"; owner is uiux.
    assert any(t.startswith("uiux/") for t in corpora_titles), corpora_titles
    # and uiux itself never re-injects a design domain (boundary held).
    for c in composed["contributions"]:
        if c.source == "uiux":
            assert (c.meta or {}).get("owner") is None


# ── standalone runner: PASS summary + non-zero exit on failure ──────────────────

if __name__ == "__main__":
    import pytest
    code = pytest.main([__file__, "-q"])
    if code == 0:
        print("\nPASS: uiux full plugin verified end-to-end through the LIVE praxis "
              "workflow path (bootstrap routing, deterministic fact, docs-only lease, "
              "per-phase_name disclosure, corpora composition).")
    else:
        print("\nFAIL: see pytest output above.")
    sys.exit(code)

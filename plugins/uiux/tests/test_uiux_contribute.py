"""§3.2 — graduated disclosure keyed on `situation.phase_name`."""

import config
import library_state
import uiux_plugin
from situation import Situation


UI_LIBRARY = """# UI library

## Button
- token: color.primary must stay #2563eb
- radius: 8px, never square

## Empty state
- always offer a reset action
- copy stays under 12 words
"""


def _root(tmp_path, **cfg):
    config.ensure(str(tmp_path))
    config.write(str(tmp_path), "uiux", {"has_ui": "yes", **cfg})
    return str(tmp_path)


def _write_ui(tmp_path, text=UI_LIBRARY):
    ui = tmp_path / "docs" / "design" / "ui-library.md"
    ui.parent.mkdir(parents=True, exist_ok=True)
    ui.write_text(text)
    return ui


def _sit(root, phase_name=None, targets=None, stance="none"):
    return Situation(task_kind="change", intent="x", subject="design",
                     phase=stance, phase_name=phase_name, root=root,
                     targets=targets or [])


def _uiux(root):
    return uiux_plugin.make(root)


def test_plan_is_index_only(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    out = _uiux(root).contribute(_sit(root, phase_name="plan"))
    assert len(out) == 1
    c = out[0]
    assert c.title == "Design surface inventory"
    assert "ui-library.md" in c.body           # a path is present
    assert "color.primary" not in c.body        # no library body
    assert "## Button" not in c.body


def test_phase_name_none_is_index_fallback(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    out = _uiux(root).contribute(_sit(root, phase_name=None))
    assert len(out) == 1
    assert out[0].meta["disclosure"] == "index"
    assert "## Button" not in out[0].body       # no full body


def test_ux_library_init_is_full_ui_library(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    out = _uiux(root).contribute(_sit(root, phase_name="ux-library-init", stance="convergent"))
    assert len(out) == 1
    assert out[0].meta["disclosure"] == "full"
    assert out[0].body == UI_LIBRARY             # full inline, equals the file


def test_divergent_sync_is_pin_and_anti_mean_not_full(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    # a catalogued screenshot so the by-reference contribution appears
    library_state.write_manifest(root, [{"screen": "settings", "file": "settings.png",
                                         "status": "fresh", "components": ["Button"]}])
    out = _uiux(root).contribute(
        _sit(root, phase_name="ui-library-sync", stance="divergent", targets=["Button"]))
    kinds = {c.meta["disclosure"] for c in out}
    assert "index" in kinds
    assert "consistency-pin" in kinds
    assert "anti-mean" in kinds
    assert "screenshots-by-reference" in kinds
    # the curated pin sits near the anti-mean anchor
    pin = next(c for c in out if c.meta["disclosure"] == "consistency-pin")
    assert pin.priority == -5
    # a screenshot reference is a PATH, never inlined bytes
    refs = next(c for c in out if c.meta["disclosure"] == "screenshots-by-reference")
    assert "settings.png" in refs.body
    # the FULL ui-library is NOT present anywhere (divergent non-disclosure)
    full = "\n".join(c.body for c in out)
    assert "## Empty state" not in full          # a non-target section is absent
    assert full.count("radius: 8px, never square") <= 1  # pin may hold Button's few lines, not the file


def test_implement_discloses_named_few_only(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    out = _uiux(root).contribute(
        _sit(root, phase_name="implement", stance="convergent", targets=["Button"]))
    assert len(out) == 1
    assert out[0].meta["disclosure"] == "named-few"
    assert "## Button" in out[0].body            # the named section, in full
    assert "## Empty state" not in out[0].body    # not the whole library


def test_design_decision_review_emits_nothing(tmp_path):
    root = _root(tmp_path)
    out = _uiux(root).contribute(_sit(root, phase_name="design-decision-review"))
    assert out == []


def test_contribute_never_tags_a_design_domain(tmp_path):
    root = _root(tmp_path)
    _write_ui(tmp_path)
    for pn in (None, "plan", "ui-library-sync", "implement"):
        for c in _uiux(root).contribute(_sit(root, phase_name=pn, targets=["Button"])):
            assert c.source == "uiux"
            assert (c.meta or {}).get("owner") is None  # corpora owns domains, not this

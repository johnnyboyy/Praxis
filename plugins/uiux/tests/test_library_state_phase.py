"""§4 — the library-state deterministic `evaluate` FACTS-ONLY contract.

`evaluate` emits facts and NO `next`; routing is owned by the workflow's predicate
edges (see test_uiux_routing.py). These tests assert only the fact surface.
"""

import config
import library_state


def _setup(root, **uiux_cfg):
    config.ensure(root)
    config.write(root, "uiux", uiux_cfg)


def _write_ui(root):
    ui = root / "docs" / "design" / "ui-library.md"
    ui.parent.mkdir(parents=True, exist_ok=True)
    ui.write_text("# UI library\n")


def _write_ux(root):
    ux = root / "docs" / "design" / "ux-library.md"
    ux.parent.mkdir(parents=True, exist_ok=True)
    ux.write_text("# UX library\n")


def _write_manifest(root):
    m = library_state.manifest_path(root)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text("# screenshots\n")


def test_evaluate_emits_facts_no_next(tmp_path):
    _setup(tmp_path, has_ui="yes")
    ev = library_state.evaluate(tmp_path)
    assert "next" not in ev
    assert ev["passed"] is True
    ls = ev["facts"]["library_state"]
    assert ls["libraries"] == {"ui": False, "ux": False, "screenshots": False}
    assert ls["drift"] == 0
    # has_ui + no ui-library.md -> ui-library-init eligible.
    assert ls["eligibility"]["ui-library-init"] is True
    # produces IS the same fact dict carried forward.
    assert ev["produces"] is ls


def test_ui_present_toggles_libraries_and_eligibility(tmp_path):
    _setup(tmp_path, has_ui="yes")
    _write_ui(tmp_path)
    ev = library_state.evaluate(tmp_path)
    ls = ev["facts"]["library_state"]
    assert ls["libraries"]["ui"] is True
    # ui present, no manifest -> screenshot-init eligible; ui-init no longer eligible.
    assert ls["eligibility"]["ui-library-init"] is False
    assert ls["eligibility"]["screenshot-library-init"] is True
    assert ls["eligibility"]["ux-library-init"] is True
    assert ls["eligibility"]["ui-library-sync"] is True


def test_drift_is_read_from_config(tmp_path):
    _setup(tmp_path, has_ui="yes", library_drift={"since_last_sync": 3})
    _write_ui(tmp_path)
    _write_ux(tmp_path)
    _write_manifest(tmp_path)
    ev = library_state.evaluate(tmp_path)
    ls = ev["facts"]["library_state"]
    assert ls["drift"] == 3
    assert ls["libraries"] == {"ui": True, "ux": True, "screenshots": True}


def test_no_ui_yields_all_false_eligibility(tmp_path):
    _setup(tmp_path, has_ui="no")
    ev = library_state.evaluate(tmp_path)
    ls = ev["facts"]["library_state"]
    assert ls["has_ui"] is False
    assert ls["eligible"] == []
    assert all(v is False for v in ls["eligibility"].values())


def test_config_relocation_of_ui_library(tmp_path):
    _setup(tmp_path, has_ui="yes", ui_library="design/ui.md")
    ev = library_state.evaluate(tmp_path)
    assert ev["facts"]["library_state"]["libraries"]["ui"] is False  # relocated path absent
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "ui.md").write_text("# ui\n")
    ev = library_state.evaluate(tmp_path)
    assert ev["facts"]["library_state"]["libraries"]["ui"] is True  # relocated path now honored

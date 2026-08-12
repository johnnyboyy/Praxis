"""§5.1 — the docs-only design edit lease."""

import contributors
import uiux_plugin
from situation import Situation


def _sit(phase_name):
    return Situation(task_kind="change", intent="x", subject="design",
                     phase="none", phase_name=phase_name, targets=[])


def _uiux(tmp_path):
    return uiux_plugin.make(str(tmp_path))


def test_design_phase_returns_docs_globs(tmp_path):
    globs = _uiux(tmp_path).surface(_sit("ui-library-sync"))
    assert globs is not None
    assert "docs/**" in globs
    assert ".praxis/**" in globs


def test_surface_for_unions(tmp_path):
    union = contributors.surface_for([_uiux(tmp_path)], _sit("design-decision-review"))
    assert union == sorted(set(uiux_plugin.DESIGN_LEASE))


def test_source_phases_return_none(tmp_path):
    assert _uiux(tmp_path).surface(_sit("implement")) is None
    assert _uiux(tmp_path).surface(_sit(None)) is None


def test_source_path_not_matched_by_design_globs(tmp_path):
    import fnmatch
    globs = _uiux(tmp_path).surface(_sit("ui-library-init"))
    assert not any(fnmatch.fnmatch("src/app.py", g) for g in globs)
    assert any(fnmatch.fnmatch("docs/design/ui-library.md", g) for g in globs)

"""The writing plugin's PROCESS face: contribute by stance, phase/workflow validity.

Writing is process-only (no domains_dir); these tests cover the contribute keying,
the phase objects, and the workflow's validity against the merged registry table.
"""

import registry
import writing_plugin
from situation import Situation
from workflow import Phase


def _writing(root):
    return writing_plugin.make(str(root))


def _prose(*, phase="none", phase_name=None, label=None) -> Situation:
    return Situation(task_kind="create", intent="write a piece", subject="prose",
                     phase=phase, phase_name=phase_name, label=label)


# --- contribute: draft vs revision by stance ------------------------------------

def test_contribute_divergent_stance_returns_draft(tmp_path):
    out = _writing(tmp_path).contribute(_prose(phase="divergent"))
    assert len(out) == 1
    assert "draft" in out[0].title.lower()
    assert out[0].meta["stance"] == "divergent"


def test_contribute_convergent_stance_returns_revision(tmp_path):
    out = _writing(tmp_path).contribute(_prose(phase="convergent"))
    assert len(out) == 1
    assert "revision" in out[0].title.lower()
    assert out[0].meta["stance"] == "convergent"


def test_contribute_phase_name_overrides_stance(tmp_path):
    # phase_name says draft even though the stance field is convergent.
    out = _writing(tmp_path).contribute(
        _prose(phase="convergent", phase_name="writing-draft"))
    assert "draft" in out[0].title.lower()

    out = _writing(tmp_path).contribute(
        _prose(phase="divergent", phase_name="writing-revision"))
    assert "revision" in out[0].title.lower()


def test_contribute_carries_genre_in_meta_and_body(tmp_path):
    out = _writing(tmp_path).contribute(_prose(phase="divergent", label="legal"))
    assert out[0].meta["genre"] == "legal"
    assert "legal" in out[0].body.lower()
    assert set(writing_plugin.GENRES) == {
        "fiction", "nonfiction", "copy", "legal", "documentation"}


def test_contribute_unspecified_genre_is_none(tmp_path):
    out = _writing(tmp_path).contribute(_prose(phase="divergent"))
    assert out[0].meta["genre"] is None


def test_contribute_returns_empty_for_non_prose(tmp_path):
    w = _writing(tmp_path)
    for subject in ("coding", "design", "process"):
        sit = Situation(task_kind="create", intent="x", subject=subject,
                        phase="divergent")
        assert w.contribute(sit) == []


# --- no judgment face -----------------------------------------------------------

def test_no_domains_dir(tmp_path):
    # process-only: corpora must find no judgment to carry.
    assert not hasattr(_writing(tmp_path), "domains_dir")


# --- phases validate ------------------------------------------------------------

def test_every_phase_validates(tmp_path):
    for p in _writing(tmp_path).phases():
        assert registry.validate_phase(p) == []


def test_resolve_phases_contains_writing_phases_plus_seed(tmp_path):
    phases = registry.resolve_phases(str(tmp_path), [_writing(tmp_path)])
    assert {"writing-draft", "writing-revision"} <= set(phases)
    assert "close" in phases  # seed still present


def test_draft_is_divergent_revision_is_convergent(tmp_path):
    ph = {p.name: p for p in _writing(tmp_path).phases()}
    assert ph["writing-draft"].stance == "divergent"
    assert ph["writing-revision"].stance == "convergent"


# --- workflow validates against the merged table --------------------------------

def test_resolve_workflows_contains_writing(tmp_path):
    workflows = registry.resolve_workflows(str(tmp_path), [_writing(tmp_path)])
    assert "writing" in workflows


def test_workflow_validates_against_merged_table(tmp_path):
    contributor = _writing(tmp_path)
    phases = registry.resolve_phases(str(tmp_path), [contributor])
    for w in contributor.workflows():
        assert registry.validate_workflow(w, phases) == [], w.name


# --- the contributor itself is valid to praxis ----------------------------------

def test_contributor_validates(tmp_path):
    from contributors import validate_contributor
    assert validate_contributor(_writing(tmp_path)) == []


def test_a_writing_phase_named_close_would_not_override_seed(tmp_path):
    """Boundary check: the writing workflow reuses the seed `close`, it does not
    ship its own — so the seed `close` remains authoritative."""

    class Shadow:
        source = "shadow"

        def phases(self):
            return [Phase("close", stance="divergent", intent="not the seed")]

    phases = registry.resolve_phases(str(tmp_path), [Shadow()])
    assert phases["close"].intent == "finalize the unit"  # seed wins

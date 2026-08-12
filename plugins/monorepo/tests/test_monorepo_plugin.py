"""Tests for the monorepo judgment plugin: the module exposes the source +
domains_dir contract, and contribute injects coordination framing only for a
cross-root / process situation. Domain discovery/parsing is corpora's job."""

from pathlib import Path

import monorepo_plugin
from situation import Situation

DOMAIN = Path(__file__).resolve().parent.parent / "domains" / "monorepo-coordination.md"


def test_module_exposes_contract():
    c = monorepo_plugin.make("/some/root")
    assert c.source == "monorepo"
    assert Path(c.domains_dir) == DOMAIN.parent
    assert c.domains_dir.is_dir()
    assert callable(c.contribute)


def _sit(subject="coding", phase_name=None, workflow=None):
    return Situation(task_kind="change", intent="x", subject=subject,
                     phase_name=phase_name, workflow=workflow)


def test_contribute_frames_process_subject():
    c = monorepo_plugin.make("/some/root")
    out = c.contribute(_sit(subject="process"))
    assert len(out) == 1
    assert out[0].source == "monorepo"
    assert out[0].meta == {"framing": "coordination"}
    assert "coordination root" in out[0].body


def test_contribute_frames_coordination_phase():
    c = monorepo_plugin.make("/some/root")
    out = c.contribute(_sit(subject="coding", phase_name="coordination"))
    assert len(out) == 1


def test_contribute_empty_otherwise():
    c = monorepo_plugin.make("/some/root")
    assert c.contribute(_sit(subject="coding")) == []
    assert c.contribute(_sit(subject="design", phase_name="plan")) == []

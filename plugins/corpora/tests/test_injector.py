"""Compose-layer tests: reproduce the three worked examples from
injector-design.md by dropping domain files into root/.praxis/domains
(owner=project) and calling make(root).contribute(situation).
"""

import tempfile
import textwrap
from pathlib import Path

import config
from situation import Situation

from corpora import make
from corpora.injector import ANTI_MEAN_ANCHOR_TEXT


def _domains_dir(root: Path) -> Path:
    d = root / ".praxis" / "domains"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_domain(
    root: Path,
    id_,
    *,
    subject,
    posture="neutral",
    task_kinds=None,
    workflows=None,
    labels=None,
    n_conventions=2,
    n_principles=2,
):
    conv = "\n".join(
        f"  - id: c{i}\n    rule: convention {i} for {id_}"
        for i in range(n_conventions)
    )
    princ = "\n".join(
        f"  - id: p{i}\n    rule: principle {i} for {id_}\n"
        f"    condition: cond {i}\n    reason: reason {i}"
        for i in range(n_principles)
    )
    fm = [f"id: {id_}", f"subject: {subject}", f"posture: {posture}"]
    if task_kinds is not None:
        fm.append(f"task-kinds: [{', '.join(task_kinds)}]")
    if workflows is not None:
        fm.append(f"workflows: [{', '.join(workflows)}]")
    if labels is not None:
        fm.append(f"labels: [{', '.join(labels)}]")
    text = (
        "---\n"
        + "\n".join(fm)
        + "\n---\n\nconventions:\n"
        + (conv or "  []")
        + "\n\nprinciples:\n"
        + (princ or "  []")
        + "\n"
    )
    (_domains_dir(root) / f"{id_}.md").write_text(text, encoding="utf-8")


def _by_priority(contribs):
    out = {}
    for c in contribs:
        out.setdefault(c.priority, []).append(c)
    return out


def test_example1_coding_change_convergent_build_verify():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_domain(
            root,
            "coding-general",
            subject="coding",
            posture="convergent",
            task_kinds=["create", "change"],
            workflows=["build-verify"],
        )
        sit = Situation(
            task_kind="change",
            intent="refactor under a build-verify loop",
            subject="coding",
            phase="convergent",
            workflow="build-verify",
        )
        out = make(root).contribute(sit)
        tiers = _by_priority(out)

        # no anti-mean anchor (not divergent)
        assert -10 not in tiers
        # priority 0 conventions preamble present
        assert 0 in tiers
        assert any(c.title == "Conventions" for c in tiers[0])
        # priority 10 domain principles present
        assert 10 in tiers
        assert any("principles" in c.title for c in tiers[10])
        # priority 20 workflow process principles present
        assert 20 in tiers
        assert any("build-verify process" in c.title for c in tiers[20])


def test_example2_design_create_divergent_label_color():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # color-labelled domain (pinned) + a plain convergent design domain
        _write_domain(
            root,
            "color",
            subject="design",
            posture="divergent",
            labels=["color"],
        )
        _write_domain(
            root,
            "layout",
            subject="design",
            posture="convergent",
        )
        sit = Situation(
            task_kind="create",
            intent="design a new palette, push off the default",
            subject="design",
            phase="divergent",
            label="color",
        )
        out = make(root).contribute(sit)
        tiers = _by_priority(out)

        # priority -10 anti-mean anchor present
        assert -10 in tiers
        assert tiers[-10][0].body == ANTI_MEAN_ANCHOR_TEXT

        # convergent-posture conventions suppressed: no priority 0 at all
        assert 0 not in tiers

        # the color-labelled domain leads the principle ordering
        principle_titles = [c.title for c in out if c.priority == 10]
        assert principle_titles[0] == "project/color — principles"
        assert "project/layout — principles" in principle_titles
        assert principle_titles.index("project/color — principles") < principle_titles.index(
            "project/layout — principles"
        )


def test_example3_coding_explore_none():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_domain(
            root,
            "coding-general",
            subject="coding",
            posture="convergent",
            task_kinds=["create", "change"],
        )
        sit = Situation(
            task_kind="explore",
            intent="read the code to understand it",
            subject="coding",
            phase="none",
        )
        out = make(root).contribute(sit)
        tiers = _by_priority(out)

        # explore suppresses conventions entirely
        assert 0 not in tiers
        # but principles still emitted
        assert 10 in tiers
        assert any("principles" in c.title for c in tiers[10])
        # no anchor, no process
        assert -10 not in tiers
        assert 20 not in tiers

"""Parse-layer tests: parse the coding-general worked example from
domain-file.md into a Domain and check fields, defaults, and error paths.
"""

import tempfile
import textwrap
from pathlib import Path

import pytest

from corpora import parse_domain_file
from corpora.models import Convention, Domain, Principle

# The coding-general example from domain-file.md ("Example domain file").
CODING_GENERAL = textwrap.dedent(
    """\
    ---
    id: coding-general
    subject: coding
    posture: convergent
    universal: false
    applies-when: []
    task-kinds: [create, change]
    workflows: []
    labels: [refactor, cleanup]
    ---

    conventions:
      - id: names
        rule: Name things for the reader who has never seen this code; no abbreviations that aren't already domain words.
      - id: early-return
        rule: Guard and return early; do not nest the happy path inside conditionals.
      - id: no-dead-code
        rule: Delete unused code rather than commenting it out.
      - id: one-purpose
        rule: A function does one thing; if you need "and" to describe it, split it.

    principles:
      - id: duplication-vs-abstraction
        rule: Tolerate a little duplication before you reach for an abstraction.
        condition: When two call sites look similar but you are not yet sure they will change together.
        reason: A wrong abstraction is more expensive to unwind than duplicated code is to maintain.
      - id: comments-explain-why
        rule: Comment the why, not the what.
        condition: When the code's intent cannot be recovered from reading it.
        reason: The what drifts out of sync with the code and then lies.
      - id: boundary-validation
        rule: Validate at the boundary, trust within the core.
        condition: When data crosses from outside the system into internal logic.
        reason: Concentrating validation at the edge lets the interior assume well-formed data.
      - id: optimize-later
        rule: Make it correct and clear first; optimize only against a measured hot path.
        condition: When you feel the urge to hand-optimize before profiling.
        reason: Measurement, not intuition, tells you where the time goes.
    """
)


def _write(tmp: Path, text: str) -> Path:
    p = tmp / "domain.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_coding_general_full():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _write(tmp, CODING_GENERAL)
        d = parse_domain_file(path, owner="general")

        assert isinstance(d, Domain)
        assert d.id == "coding-general"
        assert d.owner == "general"
        assert d.subject == "coding"
        assert d.posture == "convergent"
        assert d.universal is False
        assert d.applies_when == []
        assert d.task_kinds == ["create", "change"]
        assert d.workflows == []
        assert d.labels == ["refactor", "cleanup"]
        assert d.source_path == path
        assert d.fq == "general/coding-general"

        assert len(d.conventions) == 4
        assert all(isinstance(c, Convention) for c in d.conventions)
        assert [c.id for c in d.conventions] == [
            "names",
            "early-return",
            "no-dead-code",
            "one-purpose",
        ]
        assert d.conventions[1].rule.startswith("Guard and return early")

        assert len(d.principles) == 4
        assert all(isinstance(p, Principle) for p in d.principles)
        dup = d.principles[0]
        assert dup.id == "duplication-vs-abstraction"
        assert dup.rule.startswith("Tolerate a little duplication")
        assert dup.condition.startswith("When two call sites")
        assert dup.reason.startswith("A wrong abstraction")


def test_defaults_applied_for_minimal_file():
    minimal = textwrap.dedent(
        """\
        ---
        id: bare
        subject: coding
        posture: neutral
        ---

        principles:
          - id: p1
            rule: Do the thing.
            condition: always
            reason: because
        """
    )
    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), minimal)
        d = parse_domain_file(path, owner="project")

        assert d.universal is False
        assert d.applies_when == []
        assert d.task_kinds == []
        assert d.workflows == []
        assert d.labels == []
        assert d.conventions == []
        assert len(d.principles) == 1
        # runtime fields default here, set later by selection
        assert d.weight == 1.0
        assert d.registration_index == 0


def test_owner_disagreement_raises():
    disagree = textwrap.dedent(
        """\
        ---
        id: coding-general
        owner: general
        subject: coding
        posture: convergent
        ---

        principles: []
        """
    )
    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), disagree)
        with pytest.raises(ValueError, match="disagrees"):
            parse_domain_file(path, owner="project")


def test_owner_agreement_ok():
    agree = textwrap.dedent(
        """\
        ---
        id: coding-general
        owner: general
        subject: coding
        posture: convergent
        ---

        conventions: []
        principles: []
        """
    )
    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), agree)
        d = parse_domain_file(path, owner="general")
        assert d.owner == "general"


@pytest.mark.parametrize("missing", ["id", "subject", "posture"])
def test_missing_required_field_raises(missing):
    fields = {"id": "x", "subject": "coding", "posture": "neutral"}
    del fields[missing]
    fm = "\n".join(f"{k}: {v}" for k, v in fields.items())
    text = f"---\n{fm}\n---\n\nprinciples: []\n"
    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), text)
        with pytest.raises(ValueError, match=f"'{missing}'"):
            parse_domain_file(path)

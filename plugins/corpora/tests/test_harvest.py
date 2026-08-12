"""Surface-half tests: the per-unit `unit-close` hook harvests principle
PROPOSALS off the receipt into a project-local UNRATIFIED candidate store.

Harvest never ratifies and never writes into any domains_dir.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import journal
from contributors import HookContext, fire

from corpora import make


def _unit(uid="U1"):
    return SimpleNamespace(id=uid)


def _ctx(root, unit=None, receipt=None):
    return HookContext(
        root=Path(root),
        step="unit-close",
        unit=unit,
        receipt=receipt,
        verdict=None,
    )


def _store(root):
    return Path(root) / ".praxis" / "corpora" / "candidates.md"


def _proposal(i, kind="judgment", provenance=None):
    p = {
        "id": f"cand-{i}",
        "rule": f"rule {i}",
        "condition": f"cond {i}",
        "reason": f"reason {i}",
        "kind": kind,
    }
    if provenance is not None:
        p["provenance"] = provenance
    return p


def test_hooks_registers_unit_close():
    with tempfile.TemporaryDirectory() as td:
        c = make(Path(td))
        table = c.hooks()
        assert "unit-close" in table
        assert callable(table["unit-close"])


def test_two_proposals_append_two_unratified_candidates_with_provenance():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        receipt = {
            "evidence": {
                "proposals": [
                    _proposal(1, kind="judgment"),
                    _proposal(2, kind="knowledge", provenance={"phase": "verify"}),
                ]
            }
        }
        ctx = _ctx(root, unit=_unit("U42"), receipt=receipt)
        c._harvest(ctx)

        text = _store(root).read_text(encoding="utf-8")
        # marked clearly UNRATIFIED / for-review
        assert "UNRATIFIED" in text
        # both candidates landed (one heading each)
        assert text.count("· UNRATIFIED") == 2
        assert "cand-1" in text and "cand-2" in text
        assert "rule 1" in text and "rule 2" in text
        # kinds recorded
        assert "judgment" in text and "knowledge" in text
        # provenance stamped: unit id + harvest date + spawn-attached origin
        assert "unit=U42" in text
        assert "harvested=" in text
        assert "origin=" in text  # from the second proposal

        # journal note summarizing the surfaced count, scoped to the unit
        notes = journal.notes(root, unit="U42")
        assert any(
            n.get("source") == "corpora" and n.get("candidates") == 2
            for n in notes
        )


def test_appends_across_calls_not_overwrite():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        c._harvest(_ctx(root, _unit("U1"),
                        {"evidence": {"proposals": [_proposal(1)]}}))
        c._harvest(_ctx(root, _unit("U2"),
                        {"evidence": {"proposals": [_proposal(2)]}}))
        text = _store(root).read_text(encoding="utf-8")
        assert text.count("· UNRATIFIED") == 2
        # single header (not duplicated on the second append)
        assert text.count("# Corpora candidate principles") == 1


def test_fires_through_contributors_fire():
    """The hook is discovered + fired via contributors.fire, like praxis does."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        ctx = _ctx(root, _unit("U9"),
                   {"evidence": {"proposals": [_proposal(1), _proposal(2)]}})
        fire([c], "unit-close", ctx)
        assert _store(root).read_text(encoding="utf-8").count("· UNRATIFIED") == 2


def test_empty_and_malformed_receipts_are_failsoft_noops():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        # a battery of malformed / empty receipts — none may raise, none may write
        for receipt in (
            None,
            {},
            {"evidence": None},
            {"evidence": {}},
            {"evidence": {"proposals": None}},
            {"evidence": {"proposals": []}},
            {"evidence": {"proposals": "not-a-list"}},
            {"evidence": {"proposals": [123, "x", None]}},        # bad entries
            {"evidence": {"proposals": [{"id": "x"}]}},           # no rule
        ):
            c._harvest(_ctx(root, _unit("U1"), receipt))
        assert not _store(root).exists()
        # and no note was dropped
        assert journal.notes(root) == []


def test_nothing_lands_in_a_domains_dir():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        c._harvest(_ctx(root, _unit("U1"),
                        {"evidence": {"proposals": [_proposal(1)]}}))
        # the store is project-local under .praxis/corpora
        assert _store(root).exists()
        # nothing was written into any domains dir
        assert not (root / ".praxis" / "domains").exists()
        # corpora ships no domains_dir at all
        assert not hasattr(c, "domains_dir")


def test_unknown_kind_normalized():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = make(root)
        c._harvest(_ctx(root, _unit("U1"),
                        {"evidence": {"proposals": [_proposal(1, kind="wat")]}}))
        text = _store(root).read_text(encoding="utf-8")
        assert "unspecified" in text

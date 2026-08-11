#!/usr/bin/env python3
"""accretion — the vocabulary promotion loop: the conductor's ratify gate (PG of
docs/CONDUCTOR-PLAN.md).

Gap surfacing (situation.py / providers.consult) is the always-on detector: whenever the model's
free `suggested` name diverges from the verb work ran under, a `conductor.gap` is recorded, and
`journal.gap_candidates` tallies how often each suggestion recurs. This module is the other half —
the promotion step, symmetric to corpora's ratify gate:

  - `promotable(root, min_count)` — the mint signal: suggestions that have RECURRED at least
    `min_count` times across gaps and are not already known vocabulary. Accumulated real gaps, ready
    for the operator to judge (first-attempt-is-first-draft, applied to the vocabulary itself).
  - `mint(root, vocabulary, term)` — promote a suggestion into real vocabulary by recording a
    `conductor.mint` event. Like everything else, the accreted vocabulary is a fold over the log, not
    a separate registry — `vocabulary(root)` replays the mints on top of the built-in seeds.
  - `review(root, min_count)` — the operator surface: what's promotable, what's already minted, and
    the current vocabulary.

Where corpora accretes *judgment* (principles through its ratify gate), the conductor accretes
*process vocabulary* (verbs / subjects / phases / workflows / units) through this one — both growing
from real work rather than being complete from the start.
"""
from __future__ import annotations

from pathlib import Path

import journal
from situation import PHASES, SUBJECTS, TASK_KINDS, VOCABULARIES

BASE_VOCABULARY: dict[str, list[str]] = {
    "task_kind": list(TASK_KINDS),
    "subject": list(SUBJECTS),
    "phase": list(PHASES),
    "workflow": [],
    "unit": [],
}


def _norm(term: str) -> str:
    return str(term).strip().lower()


def minted(root: Path) -> dict[str, list[str]]:
    """Just the terms promoted through the gate (a fold of `conductor.mint`), per vocabulary."""
    out: dict[str, list[str]] = {}
    for e in journal.read(root):
        if e.get("event") != "conductor.mint":
            continue
        vocab, term = e.get("vocabulary"), _norm(e.get("term", ""))
        if not vocab or not term:
            continue
        bucket = out.setdefault(vocab, [])
        if term not in bucket:
            bucket.append(term)
    return out


def vocabulary(root: Path) -> dict[str, list[str]]:
    """The current accreted vocabulary: the built-in seeds plus everything minted, per vocabulary."""
    vocab = {k: list(v) for k, v in BASE_VOCABULARY.items()}
    for v, terms in minted(root).items():
        bucket = vocab.setdefault(v, [])
        for t in terms:
            if t not in bucket:
                bucket.append(t)
    return vocab


def is_known(root: Path, vocab: str, term: str) -> bool:
    """Whether a term is already vocabulary (a built-in seed or previously minted) — so it is neither
    a gap to surface again nor a candidate to promote."""
    return _norm(term) in {_norm(t) for t in vocabulary(root).get(vocab, [])}


def promotable(root: Path, min_count: int = 3) -> list[dict]:
    """Gap candidates recurrent enough to promote and not already known — the mint signal. Sorted by
    count (journal.gap_candidates' order), highest first."""
    return [c for c in journal.gap_candidates(root)
            if c["count"] >= min_count and not is_known(root, c["vocabulary"], c["suggested"])]


def mint(root: Path, vocab: str, term: str, note: str | None = None,
         examples: list | None = None) -> dict | None:
    """Promote `term` into `vocab` by recording a `conductor.mint` event. A no-op (returns None) when
    the term is already known — minting is idempotent. Rejects an unknown vocabulary name."""
    if vocab not in VOCABULARIES:
        raise ValueError(f"vocabulary must be one of {VOCABULARIES}, got {vocab!r}")
    term = _norm(term)
    if not term:
        raise ValueError("cannot mint an empty term")
    if is_known(root, vocab, term):
        return None
    return journal.append(root, "conductor.mint", vocabulary=vocab, term=term,
                          note=note, examples=examples)


def mint_candidate(root: Path, candidate: dict, note: str | None = None) -> dict | None:
    """Promote a `promotable` candidate straight from its own fields."""
    return mint(root, candidate["vocabulary"], candidate["suggested"], note=note,
                examples=candidate.get("examples"))


def review(root: Path, min_count: int = 3) -> dict:
    """The operator's ratify-gate surface: what has accumulated enough to promote, what is already
    minted, and the full current vocabulary."""
    return {"min_count": min_count, "promotable": promotable(root, min_count),
            "minted": minted(root), "vocabulary": vocabulary(root)}

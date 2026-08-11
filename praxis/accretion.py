#!/usr/bin/env python3
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
    vocab = {k: list(v) for k, v in BASE_VOCABULARY.items()}
    for v, terms in minted(root).items():
        bucket = vocab.setdefault(v, [])
        for t in terms:
            if t not in bucket:
                bucket.append(t)
    return vocab


def is_known(root: Path, vocab: str, term: str) -> bool:
    return _norm(term) in {_norm(t) for t in vocabulary(root).get(vocab, [])}


def promotable(root: Path, min_count: int = 3) -> list[dict]:
    return [c for c in journal.gap_candidates(root)
            if c["count"] >= min_count and not is_known(root, c["vocabulary"], c["suggested"])]


def mint(root: Path, vocab: str, term: str, note: str | None = None,
         examples: list | None = None) -> dict | None:
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
    return mint(root, candidate["vocabulary"], candidate["suggested"], note=note,
                examples=candidate.get("examples"))


def review(root: Path, min_count: int = 3) -> dict:
    return {"min_count": min_count, "promotable": promotable(root, min_count),
            "minted": minted(root), "vocabulary": vocabulary(root)}

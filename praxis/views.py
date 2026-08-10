#!/usr/bin/env python3
"""views — handoff, ledger, and cost as folds over the journal (P7 of docs/CONDUCTOR-PLAN.md).

The event log is the single source of truth, so the artifacts a system used to keep as separate
primitives are just *views* over it:

  - `handoff(root, unit)` — the terminal handoff for one unit (what a downstream consumer, e.g.
    corpora at its ratify gate, reads: outcome, verification evidence, surfaced items, the domains
    it composed under, the defects it took). Folded from the unit's events, not written as a file.
  - `ledger(root)` — the chunk-ledger: one row per unit in first-seen order (uow, state, outcome,
    attempts, verified, gap). The per-unit history, as a fold.
  - `cost(root)` — the cost rollup across every receipt (tokens / usd / tool_calls, total and
    per-unit). Retries sum, since each attempt costs.

Because these are pure folds, the separate handoff/chunk-ledger/cost files a process layer kept
become redundant: re-derive them from the log instead of maintaining them alongside it. (Wiring
praxis's file-based handoff + chunk ledger to consume these views is the surface-side retirement;
the core just proves the artifacts are recoverable from the journal.)
"""
from __future__ import annotations

from pathlib import Path

import journal


def _unit_events(root: Path) -> dict[str, list[dict]]:
    by_unit: dict[str, list[dict]] = {}
    for e in journal.read(root):
        uid = e.get("unit")
        if uid is not None:
            by_unit.setdefault(uid, []).append(e)
    return by_unit


def handoff(root: Path, unit: str) -> dict | None:
    """The terminal handoff for one unit, folded from its events — or None if the unit is unknown."""
    fold = journal.fold(root)
    u = fold["units"].get(unit)
    if u is None:
        return None
    events = _unit_events(root).get(unit, [])
    last = u["last"]
    verified = any(e.get("event") == "unit.verified" for e in events)
    evidence = next((e.get("evidence") for e in reversed(events)
                     if e.get("event") == "unit.verified"), None)
    defects = [e.get("defects") for e in events
               if e.get("event") == "unit.note" and e.get("kind") == "defect"]
    attempts = sum(1 for e in events if e.get("event") == "unit.receipt")
    return {
        "unit": unit,
        "unit_of_work": last.get("unit_of_work"),
        "state": u["state"],
        "outcome": u.get("outcome"),
        "status": u.get("status"),
        "verified": verified,
        "evidence": evidence,
        "domains_loaded": last.get("domains", []),
        "surfaced": u.get("surfaced"),
        "defects": defects,
        "attempts": attempts,
        "gap_surfaced": last.get("gap_surfaced"),
        "cost": last.get("cost"),
        "tool_calls": last.get("tool_calls"),
    }


def ledger(root: Path) -> list[dict]:
    """The chunk-ledger as a fold: one row per unit, in first-seen order."""
    fold = journal.fold(root)
    by_unit = _unit_events(root)
    rows = []
    for uid, u in fold["units"].items():   # dict preserves first-seen insertion order
        events = by_unit.get(uid, [])
        rows.append({
            "unit": uid,
            "unit_of_work": u["last"].get("unit_of_work"),
            "state": u["state"],
            "outcome": u.get("outcome"),
            "attempts": sum(1 for e in events if e.get("event") == "unit.receipt"),
            "verified": any(e.get("event") == "unit.verified" for e in events),
            "gap_surfaced": u["last"].get("gap_surfaced"),
        })
    return rows


def cost(root: Path) -> dict:
    """Roll up cost across every `unit.receipt` — total and per-unit. Retries sum (each attempt
    costs). A receipt with no cost contributes only its tool_calls."""
    per_unit: dict[str, dict] = {}
    tokens = usd = calls = 0
    for e in journal.read(root):
        if e.get("event") != "unit.receipt":
            continue
        uid = e.get("unit")
        c = e.get("cost") or {}
        t = int(c.get("tokens", 0) or 0)
        d = float(c.get("usd", 0) or 0)
        n = int(e.get("tool_calls", 0) or 0)
        tokens += t
        usd += d
        calls += n
        pu = per_unit.setdefault(uid, {"tokens": 0, "usd": 0.0, "tool_calls": 0})
        pu["tokens"] += t
        pu["usd"] = round(pu["usd"] + d, 6)
        pu["tool_calls"] += n
    return {"tokens": tokens, "usd": round(usd, 6), "tool_calls": calls, "per_unit": per_unit}

#!/usr/bin/env python3
"""journal — the conductor's single source of truth: an append-only event log per root, and a fold
that derives current state from it.

This is P1 of docs/CONDUCTOR-PLAN.md. Everything the conductor knows about a root's work — which
units exist, what state each is in, what a unit surfaced, the deliver-vs-stall summary — is derived
here by replaying events, not read from a scatter of marker/stamp/ledger files. Later phases point
the gate, the conductor loop, and the trace view at this fold and retire those files.

Design rules:
  - append-only: state is never mutated in place, only advanced by a new event.
  - a fold is a pure function of the event sequence (same events → same state), so it is trivially
    testable and recoverable.
  - unknown event types are preserved (attached to the unit) but never crash the fold — the log
    tolerates additions ahead of the reducer.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

JOURNAL_NAME = "journal.jsonl"

# State-advancing events → the lifecycle state they move a unit into. Everything else (edges,
# annotations, runtime notes) attaches to the unit without changing its state.
STATE_EVENTS: dict[str, str] = {
    "unit.proposed": "proposed",
    "unit.framed": "framed",
    "unit.dispatched": "dispatched",
    "unit.running": "running",
    "unit.receipt": "verifying",   # a receipt is a claim awaiting verification
    "unit.verified": "verified",
    "unit.done": "done",
    "unit.stalled": "stalled",
    "unit.closed": "closed",
}

# States in which a unit is still "in flight" — framed but not concluded. The gate asks this: is
# there an open unit for this root, and what may it edit?
IN_FLIGHT = {"framed", "dispatched", "running", "verifying", "verified"}
CONCLUDED = {"done", "closed", "stalled"}


def _praxis_dir(root: Path) -> Path:
    for m in (".praxis", "praxis"):
        if (root / m).is_dir():
            return root / m
    return root / ".praxis"


def journal_path(root: Path) -> Path:
    return _praxis_dir(root) / JOURNAL_NAME


def append(root: Path, event: str, unit: str | None = None, **payload) -> dict:
    """Append one event and return the written record (with ts + seq). seq is monotonic per file.

    Reserved payload keys (managed by the envelope, do not pass them): `event`, `unit`, `seq`, `ts`
    (may be passed to backdate). The journal is per-root, so a `root` field in payload is redundant.
    """
    path = journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = _next_seq(path)
    record = {"ts": payload.pop("ts", None) or time.time(), "seq": seq, "event": event}
    if unit is not None:
        record["unit"] = unit
    record.update(payload)
    with path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def _next_seq(path: Path) -> int:
    if not path.is_file():
        return 0
    last = -1
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                last = max(last, int(json.loads(line).get("seq", -1)))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    except OSError:
        return 0
    return last + 1


def read(root: Path) -> list[dict]:
    path = journal_path(root)
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return out


def fold(root: Path) -> dict:
    """Replay the log into current state.

    Returns:
      units:      { unit_id: { unit, state, events, workflow, phase_index, outcome, status,
                               surfaced, last:{…latest payload merged…} } }
      open_units: unit_ids still in flight, in first-seen order
      summary:    deliver-vs-stall counts by phase (unit label) and by workflow (the trace view)
    """
    units: dict[str, dict] = {}
    order: list[str] = []
    for ev in read(root):
        uid = ev.get("unit")
        if uid is None:
            continue
        if uid not in units:
            units[uid] = {"unit": uid, "state": None, "events": 0, "workflow": None,
                          "phase_index": None, "outcome": None, "status": None,
                          "surfaced": None, "last": {}}
            order.append(uid)
        u = units[uid]
        u["events"] += 1
        etype = ev.get("event", "")
        # Merge meaningful payload fields forward (last-write-wins), skipping envelope keys.
        for k, v in ev.items():
            if k in ("ts", "seq", "event", "unit"):
                continue
            u["last"][k] = v
            if k in ("workflow", "phase_index", "outcome", "status", "surfaced"):
                u[k] = v
        if etype in STATE_EVENTS:
            u["state"] = STATE_EVENTS[etype]

    open_units = [uid for uid in order if units[uid]["state"] in IN_FLIGHT]
    return {"units": units, "open_units": open_units, "summary": _summary(units, order)}


def _summary(units: dict[str, dict], order: list[str]) -> dict:
    def bucket() -> dict:
        return {"runs": 0, "result": 0, "stall": 0}

    by_phase: dict[str, dict] = {}
    by_workflow: dict[str, dict] = {}
    stalls: list[dict] = []
    for uid in order:
        u = units[uid]
        outcome = u.get("outcome")
        if outcome not in ("result", "stall"):
            continue
        phase = u["last"].get("label") or u["last"].get("unit_of_work") or uid
        bp = by_phase.setdefault(phase, bucket())
        bp["runs"] += 1
        bp[outcome] += 1
        flow = u.get("workflow")
        if flow:
            bw = by_workflow.setdefault(flow, bucket())
            bw["runs"] += 1
            bw[outcome] += 1
        if outcome == "stall":
            stalls.append({"unit": uid, "phase": phase, "workflow": flow,
                           "status": u.get("status"), "surfaced": u.get("surfaced")})
    return {"by_phase": by_phase, "by_workflow": by_workflow, "recent_stalls": stalls[-5:]}


def state_of(root: Path, unit: str) -> str | None:
    u = fold(root)["units"].get(unit)
    return u["state"] if u else None


def gaps(root: Path) -> list[dict]:
    """All surfaced vocabulary gaps (`conductor.gap` events) for this root, newest last. These are
    conductor-level, not unit-scoped: they are where the system didn't fit and asked for a better
    verb/phase/workflow — the raw material for the accretion (promotion) loop and the operator
    surface. The core mechanism, symmetric to corpora's ratify gate."""
    return [e for e in read(root) if e.get("event") == "conductor.gap"]


def gap_candidates(root: Path) -> list[dict]:
    """Tally the model's `suggested` names across surfaced gaps — the recurrence signal that drives
    promotion (a corpora-counter analogue). A suggestion that keeps recurring is a strong candidate
    to mint into real vocabulary. Sorted by count, newest examples last.

    Returns: [{ suggested, count, vocabulary, chosen_as:[…], examples:[intent…] }]
    """
    tally: dict[tuple[str, str], dict] = {}
    for e in gaps(root):
        suggested = (e.get("suggested") or "").strip().lower()
        if not suggested:
            continue
        vocab = e.get("vocabulary", "task_kind")
        key = (vocab, suggested)
        rec = tally.setdefault(key, {"suggested": suggested, "vocabulary": vocab,
                                     "count": 0, "chosen_as": [], "examples": []})
        rec["count"] += 1
        chosen = e.get("chosen")
        if chosen and chosen not in rec["chosen_as"]:
            rec["chosen_as"].append(chosen)
        if e.get("intent"):
            rec["examples"].append(e["intent"])
    return sorted(tally.values(), key=lambda r: r["count"], reverse=True)


def open_unit(root: Path) -> dict | None:
    """The most recent in-flight unit for this root, or None. This is what the edit gate consults:
    'is there an open unit, and what is its edit surface?' — replacing the marker+stamp dance."""
    f = fold(root)
    if not f["open_units"]:
        return None
    uid = f["open_units"][-1]
    return f["units"][uid]

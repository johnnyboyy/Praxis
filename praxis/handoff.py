#!/usr/bin/env python3
"""handoff — the forward handoff: composing a unit's brief + judgment on demand, and the gate-backed
PULL that hands it to a self-advancing agent.

Two delivery paths share one assembly (`assemble`) so a unit's handoff is composed lazily, per unit,
at the moment it is needed — never pre-built for the whole chain by the conductor:

  - PUSH (cross-spawn cascade): `run_unit` (run.py) already consults the provider per unit and hands
    the composed judgment to the executor, which injects it into a fresh spawn. The runner pulls in
    CODE; the agent has no discretion to skip it — guaranteed delivery.
  - PULL (in-context chaining): a long-lived agent that finishes one unit calls `pull` to get the
    NEXT ready unit's handoff itself, so the conductor doesn't micro-manage the chain. Reliability
    comes from the GATE, not the agent's diligence: `pull` frames the unit and records
    `payload_read`, and the edit gate (praxis/scripts/gate.py) denies edits for a spawn/file-delivery
    unit until that read is on the journal. The agent is free to skip the pull; it just cannot edit
    until it has pulled — the read is the fence in front of the work.

`next_ready` picks the next unit whose dependencies have all reached `done` and which has not itself
started — a pure fold over the journal, so the cascade is reproducible from the log.
"""
from __future__ import annotations

from pathlib import Path

import journal
from providers import consult
from run import Unit


def assemble(intent: str, composed: dict, brief: str | None = None,
             feedback: list | None = None) -> dict:
    """Build a unit's handoff from its composed judgment: the JUDGMENT block (the domain bodies, the
    stable system-prompt half) and the BRIEF (the concrete instruction, with any verification
    feedback appended). Returns both plus their sizes — the single assembly both the push executor
    and the pull tool use, so the two paths can never drift."""
    judgment = "\n\n".join(a["body"] for a in (composed.get("artifacts") or []) if a.get("body"))
    lines = [brief or intent or ""]
    fb = feedback if feedback is not None else composed.get("feedback")
    if fb:
        lines.append("\nThe previous attempt did not pass verification. Fix these defects:")
        lines += [f"  - {d}" for d in fb]
    lines.append("\nWhen done, reply with a short summary of exactly what you changed.")
    return {"judgment": judgment, "brief": "\n".join(lines),
            "judgment_bytes": len(judgment), "domains": composed.get("domains", [])}


def _state_of(fold: dict, uid: str) -> str | None:
    u = fold["units"].get(uid)
    return u["state"] if u else None


def next_ready(root: str | Path, units: list[Unit]) -> Unit | None:
    """The next unit ready to run: dependencies all `done`, and it has not itself started. Returns
    None when nothing is ready (either everything concluded, or the only remaining units are still
    waiting on an unfinished/failed dependency). Pure fold over the journal."""
    root = Path(root).resolve()
    fold = journal.fold(root)
    for u in units:
        if _state_of(fold, u.id) is not None:
            continue
        if all(_state_of(fold, d) == "done" for d in u.depends_on):
            return u
    return None


def status(root: str | Path, units: list[Unit]) -> dict:
    """Where the tasklist stands, folded from the journal: which units are done, in flight, stalled,
    or still waiting — the progress surface the operator watches while the chain cascades."""
    root = Path(root).resolve()
    fold = journal.fold(root)
    buckets = {"done": [], "in_flight": [], "stalled": [], "waiting": []}
    for u in units:
        st = _state_of(fold, u.id)
        if st == "done":
            buckets["done"].append(u.id)
        elif st == "stalled":
            buckets["stalled"].append(u.id)
        elif st in journal.IN_FLIGHT:
            buckets["in_flight"].append(u.id)
        else:
            buckets["waiting"].append(u.id)
    complete = len(buckets["done"]) + len(buckets["stalled"]) == len(units)
    return {**buckets, "complete": complete, "total": len(units)}


def pull(root: str | Path, units: list[Unit], provider, brief: str | None = None,
         delivery: str = "spawn") -> dict:
    """Hand the next ready unit's handoff to a self-advancing agent (the PULL path). Frames the unit
    (`unit.proposed` → `unit.framed`, carrying its delivery + edit surface so the gate can rule on
    it), composes its judgment on demand, records `payload_read` (the pull IS the read — the content
    is being delivered now, so the gate opens for THIS unit's edits), and returns the brief +
    judgment. When nothing is ready, returns a `waiting`/`complete` status and hands over nothing."""
    root = Path(root).resolve()
    st = status(root, units)
    unit = next_ready(root, units)
    if unit is None:
        return {"status": "complete" if st["complete"] else "waiting", "progress": st}

    composed = consult(provider, unit.situation, root=root)
    ho = assemble(unit.situation.intent, composed, brief=brief)
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    journal.append(root, "unit.framed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   routed_kind=composed.get("routed_kind"), gap_surfaced=composed.get("gap_surfaced"),
                   domains=composed.get("domains", []), stance=composed.get("stance"),
                   delivery=delivery, surface=unit.situation.targets or None,
                   note=composed.get("note"))
    # The pull delivers the payload into the agent's context, so record the read that opens the gate.
    journal.append(root, "unit.note", unit=unit.id, payload_read=True)
    journal.append(root, "handoff.pulled", unit=unit.id, judgment_bytes=ho["judgment_bytes"])
    return {"status": "ready", "unit": unit.id, "unit_of_work": unit.unit_of_work,
            "brief": ho["brief"], "judgment": ho["judgment"], "domains": ho["domains"],
            "routed_kind": composed.get("routed_kind"),
            "gap_surfaced": composed.get("gap_surfaced"), "progress": st}

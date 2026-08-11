#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import journal
from providers import consult
from run import Unit


def assemble(intent: str, composed: dict, brief: str | None = None,
             feedback: list | None = None) -> dict:
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
    root = Path(root).resolve()
    fold = journal.fold(root)
    for u in units:
        if _state_of(fold, u.id) is not None:
            continue
        if all(_state_of(fold, d) == "done" for d in u.depends_on):
            return u
    return None


def status(root: str | Path, units: list[Unit]) -> dict:
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
    journal.append(root, "unit.note", unit=unit.id, payload_read=True)
    journal.append(root, "handoff.pulled", unit=unit.id, judgment_bytes=ho["judgment_bytes"])
    return {"status": "ready", "unit": unit.id, "unit_of_work": unit.unit_of_work,
            "brief": ho["brief"], "judgment": ho["judgment"], "domains": ho["domains"],
            "routed_kind": composed.get("routed_kind"),
            "gap_surfaced": composed.get("gap_surfaced"), "progress": st}

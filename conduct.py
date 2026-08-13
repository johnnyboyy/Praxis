#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import config as config_mod
import contributors as contributors_mod
import journal
from run import verifier_from_test_cmd

_REBUILD_IGNORE = ".rebuild/"
_REBUILD_IGNORE_COMMENT = (
    "# praxis rebuild-triple scratch (extract→synthesize working dir) — never committed"
)

def _ensure_rebuild_gitignore(git_root: Path) -> bool:
    gitignore = Path(git_root) / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if any(line.strip() == _REBUILD_IGNORE for line in existing.splitlines()):
        return False
    prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
    gitignore.write_text(
        f"{prefix}{_REBUILD_IGNORE_COMMENT}\n{_REBUILD_IGNORE}\n", encoding="utf-8")
    return True

def init_root(root=None) -> dict:
    import root_tree
    start = Path(root).resolve() if root else Path.cwd()
    git_root = root_tree._git_toplevel(start)
    target = git_root if git_root is not None else start
    created = config_mod.ensure(target)
    gitignore_updated = (
        _ensure_rebuild_gitignore(git_root) if git_root is not None else False)
    return {"status": "initialized", "root": str(target),
            "config": str(config_mod.path(target)), "created": created,
            "gitignore_updated": gitignore_updated}

def _specs_for(root: Path, tasks: list[dict]) -> list:
    import plan as plan_mod
    return [plan_mod.TaskSpec.from_dict(dict(t)) for t in tasks]

def plan_status(root: str | Path) -> dict:
    import handoff as handoff_mod
    import plan as plan_mod
    import views
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    prog = handoff_mod.status(root, units)
    status = "complete" if prog["complete"] else "open"
    return {"status": status, "progress": prog, "cost": views.cost(root)}

def register_plan(root: str | Path, tasks: list[dict]) -> dict:
    import plan as plan_mod
    root = Path(root).resolve()
    specs = _specs_for(root, tasks)
    units = plan_mod.plan_tasks(root, specs)
    return {"status": "registered",
            "plan": {"units": [u.id for u in units],
                     "edges": [[d, u.id] for u in units for d in u.depends_on]},
            "next": "call next_handoff to pull the next ready unit into this context (it frames the "
                    "unit and opens the edit gate); repeat until status is complete"}

def next_handoff(root: str | Path, brief: str | None = None) -> dict:
    import handoff as handoff_mod
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    return handoff_mod.pull(root, units, contributors_mod.contributors_for(root), brief=brief)

def read_handoff(root: str | Path, unit_id: str) -> dict:
    import handoff as handoff_mod
    root = Path(root).resolve()
    unit = _find_unit(root, unit_id)
    if unit is None:
        import plan as plan_mod
        if plan_mod.reconstruct_units(root) is None:
            return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
        return {"status": "unknown-unit", "unit": unit_id}
    contributors = contributors_mod.contributors_for(root)
    composed = contributors_mod.gather(contributors, unit.situation, root=None)
    ho = handoff_mod.assemble(unit.situation.intent, composed)
    surface = (contributors_mod.surface_for(contributors, unit.situation)
               or (unit.situation.targets or None))
    journal.append(root, "unit.note", unit=unit.id, payload_read=True, reader="read_handoff")
    return {"status": "handoff", "unit": unit.id, "unit_of_work": unit.unit_of_work,
            "brief": ho["brief"], "overlay": ho["overlay"], "sources": ho["sources"],
            "surface": surface}

def _find_unit(root: Path, unit_id: str):
    import plan as plan_mod
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return None
    return next((u for u in units if u.id == unit_id), None)

def next_phase(root: str | Path, unit_id: str) -> dict:
    import phase_walk
    root = Path(root).resolve()
    unit = _find_unit(root, unit_id)
    if unit is None:
        import plan as plan_mod
        if plan_mod.reconstruct_units(root) is None:
            return {"status": "no-plan",
                    "note": "no tasklist has been planned for this root yet"}
        return {"status": "unknown-unit", "unit": unit_id}
    out = phase_walk.next_phase(root, unit)
    if out.get("status") == "phase":
        import copy

        import handoff as handoff_mod
        situation = copy.copy(unit.situation)
        situation.phase_name = out["phase"]
        composed = contributors_mod.gather(
            contributors_mod.contributors_for(root), situation)
        ho = handoff_mod.assemble(situation.intent, composed)
        if ho["overlay"]:
            out["overlay"] = ho["overlay"]
            out["sources"] = ho["sources"]
    return out

def record_phase(root: str | Path, unit_id: str, phase: str, evidence: dict | None = None,
                 test_cmd: str | None = None) -> dict:
    import phase_walk
    root = Path(root).resolve()
    unit = _find_unit(root, unit_id)
    if unit is None:
        import plan as plan_mod
        if plan_mod.reconstruct_units(root) is None:
            return {"status": "no-plan",
                    "note": "no tasklist has been planned for this root yet"}
        return {"status": "unknown-unit", "unit": unit_id}
    return phase_walk.record_phase(root, unit, phase, evidence or {},
                                   verifier=verifier_from_test_cmd(test_cmd))

def _workflow_close_status(root: Path, unit_id: str) -> tuple[str, str | None] | None:
    events = [e for e in journal.read(root) if e.get("unit") == unit_id]
    exited = [e for e in events if e.get("event") == "phase.exited"]
    entered = [e for e in events if e.get("event") == "phase.entered"]
    if not exited and not entered:
        return None
    stalled = [e for e in events if e.get("event") == "phase.stalled"]
    if stalled:
        phase = stalled[-1].get("phase")
        return ("halted", f"workflow walk stalled at phase {phase!r}")
    if not exited:
        return ("halted", "workflow walk produced no completed phase")
    unverified = [e for e in exited if not e.get("verified")]
    if unverified:
        e = unverified[-1]
        return ("halted",
                f"gate {e.get('gate')!r} did not verify at phase {e.get('phase')!r}")
    return ("complete", None)

def _escalated_reason(root: Path, unit_id: str) -> str | None:
    reason: str | None = None
    for e in journal.read(root):
        if e.get("unit") == unit_id and e.get("event") == "unit.escalated":
            reason = e.get("reason") or "unit escalated for human review"
    return reason

def _fire_unit_close(root: Path, unit_id: str, receipt: dict) -> None:
    try:
        contributors = contributors_mod.contributors_for(root)
        contributors_mod.fire(contributors, "unit-close", contributors_mod.HookContext(
            root=root, step="unit-close", unit=_find_unit(root, unit_id),
            receipt=receipt))
    except Exception:
        pass

def escalate_unit(root: str | Path, unit_id: str, reason: str | None = None) -> dict:
    root = Path(root).resolve()
    reason = (reason or "").strip() or "unit escalated for human review"
    journal.append(root, "unit.escalated", unit=unit_id, status="escalated", reason=reason)
    return {"status": "escalated", "unit": unit_id, "reason": reason}

def close_unit(root: str | Path, unit_id: str | None = None, note: str | None = None) -> dict:
    root = Path(root).resolve()
    target = unit_id
    if target is None:
        open_u = journal.open_unit(root)
        if open_u is None:
            return {"status": "no-open-unit"}
        target = open_u["unit"]
    esc = _escalated_reason(root, target)
    if esc is not None:
        journal.append(root, "unit.note", unit=target, kind="close-rejected",
                       reason=esc, escalated=True)
        return {"status": "blocked", "unit": target, "reason": esc, "escalated": True}
    walk = _workflow_close_status(root, target)
    if walk is not None and walk[0] == "halted":
        journal.append(root, "unit.note", unit=target, kind="close-rejected",
                       reason=walk[1])
        return {"status": "blocked", "unit": target, "reason": walk[1]}
    journal.append(root, "unit.done", unit=target, outcome="result", status="complete", note=note)
    _fire_unit_close(root, target, {"outcome": "result", "status": "complete",
                                    "surfaced": [], "evidence": {"note": note}})
    return {"status": "closed", "unit": target}

def record_receipt(root: str | Path, unit_id: str, outcome: str = "result",
                   note: str | None = None) -> dict:
    root = Path(root).resolve()
    if outcome == "result":
        esc = _escalated_reason(root, unit_id)
        if esc is not None:
            journal.append(root, "unit.note", unit=unit_id, kind="close-rejected",
                           reason=esc, escalated=True)
            return {"status": "blocked", "unit": unit_id, "reason": esc, "escalated": True}
        journal.append(root, "unit.done", unit=unit_id, outcome="result",
                       status="complete", note=note)
        _fire_unit_close(root, unit_id, {"outcome": "result", "status": "complete",
                                         "surfaced": [], "evidence": {"note": note}})
    elif outcome == "stall":
        journal.append(root, "unit.stalled", unit=unit_id, outcome="stall",
                       status="blocked", surfaced=[note] if note else [], note=note)
        _fire_unit_close(root, unit_id, {"outcome": "stall", "status": "blocked",
                                         "surfaced": [note] if note else [],
                                         "evidence": {"note": note}})
    else:
        raise ValueError(f"outcome must be 'result' or 'stall', got {outcome!r}")
    return {"status": "recorded", "unit": unit_id, "outcome": outcome}

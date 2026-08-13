#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import journal
from run import Receipt, verifiers_for_workflow
from workflow import GATES, EdgeType, Workflow, edge_parts

def _choose_edge(workflow: Workflow, from_phase: str, passed: bool, choice=None,
                 evidence=None):
    edges = [(t, when, et, pred)
             for (f, t, when, et, pred) in map(edge_parts, workflow.edges)
             if f == from_phase]

    if not passed:
        for (t, when, et, pred) in edges:
            if when in ("fail", "always"):
                return t, et
        return None

    if evidence is not None:
        for (t, when, et, pred) in edges:
            if when == "fact" and pred is not None:
                try:
                    if pred(evidence):
                        return t, et
                except Exception:
                    continue

    if choice is not None:
        for (t, when, et, pred) in edges:
            if when == "agent-choice" and t == choice:
                return t, et

    for (t, when, et, pred) in edges:
        if when in ("pass", "always"):
            return t, et
    return None

def incoming(workflow: Workflow, to_phase: str):
    return [(f, et) for (f, t, _when, et, _pred) in map(edge_parts, workflow.edges)
            if t == to_phase]

def gate_for(edge_in) -> str:
    return GATES[edge_in] if edge_in else GATES[EdgeType.create]

def decide_step(workflow: Workflow, unit, name: str, edge_in, receipt,
                composed: dict, verifiers: dict) -> dict:
    gate = gate_for(edge_in)
    verifier = verifiers.get(gate)
    verdict = verifier.verify(unit, receipt, composed) if verifier else None
    verified = verdict.verified if verdict is not None else True
    evidence = receipt.evidence or {}
    passed = evidence.get("passed", receipt.outcome == "result")
    advance = passed and verified
    choice = evidence.get("next") if advance else None
    nxt = _choose_edge(workflow, name, advance, choice, evidence)
    return {"gate": gate, "verified": verified, "verdict": verdict, "evidence": evidence,
            "passed": passed, "advance": advance, "choice": choice, "next": nxt}

def _resolve_workflow(root: Path, unit, workflow=None):
    if workflow is not None:
        return workflow
    name = getattr(unit.situation, "workflow", None)
    if not name:
        return None
    try:
        import registry
        return registry.resolve_workflows(root).get(name)
    except Exception:
        return None

def _stance_of(phase) -> str:
    return phase.stance if phase.stance in ("divergent", "convergent") else "none"

def _edge_type(value):
    if value in (None, "create"):
        return None
    try:
        return EdgeType(value)
    except ValueError:
        return None

def _unit_events(root: Path, unit_id: str) -> list[dict]:
    return [e for e in journal.read(root) if e.get("unit") == unit_id]

def _produces_by_phase(events: list[dict]) -> dict:
    out: dict = {}
    for e in events:
        if e.get("event") == "phase.recorded":
            out[e.get("phase")] = e.get("produces")
    return out

def _cursor(root: Path, unit, workflow) -> dict:
    events = _unit_events(root, unit.id)
    verdicts = [e for e in events if e.get("event") == "phase.verdict"]
    if not verdicts:
        first = workflow.first
        return {"status": "phase", "phase": first.name, "edge_in": None,
                "from_phase": None, "phase_index": 0}

    last = verdicts[-1]
    nxt_name = last.get("next")
    if nxt_name is not None:
        return {"status": "phase", "phase": nxt_name,
                "edge_in": _edge_type(last.get("next_edge")),
                "from_phase": last.get("phase"),
                "phase_index": int(last.get("phase_index", 0)) + 1}
    if last.get("advance"):
        return {"status": "complete", "terminal": last.get("phase")}

    return {"status": "phase", "phase": last.get("phase"),
            "edge_in": _edge_type(last.get("edge_in")),
            "from_phase": last.get("from_phase"),
            "phase_index": int(last.get("phase_index", 0))}

def next_phase(root, unit, workflow=None) -> dict:
    root = Path(root).resolve()
    workflow = _resolve_workflow(root, unit, workflow)
    if workflow is None:
        return {"status": "no-workflow", "unit": unit.id}

    cur = _cursor(root, unit, workflow)
    if cur["status"] == "complete":
        return {"status": "complete", "unit": unit.id, "workflow": workflow.name,
                "terminal": cur.get("terminal")}

    name = cur["phase"]
    edge_in = cur["edge_in"]
    from_phase = cur["from_phase"]
    phase = workflow.phase(name)
    if phase is None:
        return {"status": "no-workflow", "unit": unit.id,
                "note": f"cursor phase {name!r} not in workflow {workflow.name!r}"}

    produces = _produces_by_phase(_unit_events(root, unit.id))
    inputs = {f: produces[f] for (f, _et) in incoming(workflow, name) if f in produces}

    out = {
        "status": "phase",
        "unit": unit.id,
        "workflow": workflow.name,
        "phase": name,
        "phase_index": cur["phase_index"],
        "delivery": phase.delivery,
        "stance": _stance_of(phase),
        "edge_in": edge_in.value if edge_in else "create",
        "gate": gate_for(edge_in),
        "isolation": None,
    }
    if inputs:
        out["inputs"] = inputs
    if edge_in == EdgeType.carry:
        out["carry"] = produces.get(from_phase)
    elif edge_in == EdgeType.extract:
        spec = produces.get(from_phase)
        out["spec"] = spec

        out["isolation"] = {
            "seed_worktree": True,
            "seam": f"{from_phase}->{name}",
            "seeder": "isolation.seed_synth_worktree",
            "spec": spec,
            "reason": "seed an spec-only synth worktree; the original is withheld",
        }
    return out

def _compose_for_gate(edge_in, produces_by_phase, from_phase, evidence) -> dict:
    composed: dict = {}
    if edge_in == EdgeType.extract:
        composed["spec"] = produces_by_phase.get(from_phase)
    elif edge_in == EdgeType.carry:
        composed["carry"] = produces_by_phase.get(from_phase)

    if evidence.get("tool_log") is not None:
        composed["tool_log"] = evidence.get("tool_log")
    return composed

def record_phase(root, unit, phase, evidence, verifiers: dict | None = None,
                 verifier=None, workflow=None) -> dict:
    root = Path(root).resolve()
    workflow = _resolve_workflow(root, unit, workflow)
    if workflow is None:
        return {"status": "no-workflow", "unit": unit.id}

    evidence = dict(evidence or {})
    cur = _cursor(root, unit, workflow)

    if cur["status"] == "phase" and cur["phase"] == phase:
        edge_in = cur["edge_in"]
        from_phase = cur["from_phase"]
        phase_index = cur["phase_index"]
    else:

        edge_in = None if phase == workflow.first.name else\
            next((et for (_f, et) in incoming(workflow, phase)), None)
        from_phase = next((f for (f, _et) in incoming(workflow, phase)), None)
        prev = [e for e in _unit_events(root, unit.id) if e.get("event") == "phase.verdict"]
        phase_index = (int(prev[-1].get("phase_index", -1)) + 1) if prev else 0

    produces = _produces_by_phase(_unit_events(root, unit.id))
    composed = _compose_for_gate(edge_in, produces, from_phase, evidence)
    composed["phase"] = phase

    receipt = Receipt(outcome="result" if evidence.get("passed", True) else "stall",
                      status="complete", evidence=evidence)

    if verifiers is None:
        verifiers = verifiers_for_workflow(root, workflow, verifier)

    journal.append(root, "phase.recorded", unit=unit.id, phase=phase,
                   phase_index=phase_index,
                   edge_in=edge_in.value if edge_in else "create",
                   produces=evidence.get("produces"), facts=evidence.get("facts"),
                   tool_log=evidence.get("tool_log"))

    decision = decide_step(workflow, unit, phase, edge_in, receipt, composed, verifiers)
    gate = decision["gate"]
    verified = decision["verified"]
    nxt = decision["next"]
    nxt_name = nxt[0] if nxt else None
    nxt_edge = nxt[1].value if nxt else None
    verdict = decision["verdict"]
    defects = list(verdict.defects) if verdict is not None else []

    phase_fit = evidence.get("phase_fit", "clean")
    if phase_fit in ("loose", "none"):
        journal.append(root, "phase.gap", unit=unit.id, phase=phase,
                       suggested=evidence.get("suggested"), fit=phase_fit)

    journal.append(root, "phase.exited", unit=unit.id, phase=phase,
                   phase_index=phase_index, phase_fit=phase_fit, gate=gate,
                   verified=verified)

    journal.append(root, "phase.verdict", unit=unit.id, phase=phase,
                   phase_index=phase_index,
                   edge_in=edge_in.value if edge_in else "create",
                   from_phase=from_phase, gate=gate, verified=verified,
                   advance=decision["advance"], next=nxt_name, next_edge=nxt_edge,
                   defects=defects)

    return {"status": "recorded", "unit": unit.id, "workflow": workflow.name,
            "phase": phase, "gate": gate, "verified": verified,
            "advance": decision["advance"], "next": nxt_name, "next_edge": nxt_edge,
            "defects": defects}

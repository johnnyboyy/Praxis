#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

import config
import journal
from contributors import HookContext, fire, gather
from registry import resolve_phases
from run import Receipt
from workflow import GATES, EdgeType, Workflow, edge_parts

def _has_choice_edge(workflow: Workflow, from_phase: str, target) -> bool:
    return any(t == target and when == "agent-choice"
               for (f, t, when, _et, _pred) in map(edge_parts, workflow.edges)
               if f == from_phase)

def _stall_on_unmatched(root) -> bool:
    try:
        raw = config.read(root).get("stall-on-unmatched-route")
    except Exception:
        return False
    return isinstance(raw, str) and raw.strip().lower() == "true"

def _classify_route(root, name: str) -> str:
    try:
        known = name in resolve_phases(root)
    except Exception:
        known = False
    return "unwired" if known else "unknown"

def _journal_route_unmatched(root, **fields) -> None:
    try:
        journal.append(root, "phase.route_unmatched", **fields)
    except Exception:
        pass

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

def _incoming(workflow: Workflow, to_phase: str):
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

def run_workflow(root: Path, unit, workflow: Workflow, contributors, executor,
                 verifiers: dict | None = None, start: str | None = None,
                 max_phase_loops: int = 3) -> dict:
    verifiers = verifiers or {}
    by_name = {p.name: p for p in workflow.phases}
    name = start or workflow.first.name

    edge_in = None
    carry = None
    outputs: dict = {}
    visits: dict = {}
    phase_index = 0
    walked: list[str] = []
    phase_fits: dict[str, str] = {}
    gaps: list[dict] = []
    receipt = None
    agg_evidence: dict = {}

    while name is not None:
        visits[name] = visits.get(name, 0) + 1
        if visits[name] > max_phase_loops:
            journal.append(root, "phase.stalled", unit=unit.id, phase=name,
                           phase_index=phase_index,
                           note=f"exceeded max_phase_loops={max_phase_loops}")
            break
        phase = by_name[name]
        situation = copy.copy(unit.situation)
        situation.phase = phase.stance if phase.stance in ("divergent", "convergent") else "none"
        situation.phase_name = phase.name
        composed = gather(contributors, situation, root=(root if phase_index == 0 else None))
        composed["phase"] = phase.name
        inputs = {f: outputs[f] for (f, _et) in _incoming(workflow, phase.name) if f in outputs}
        if inputs:
            composed["inputs"] = inputs
        if edge_in == EdgeType.carry:
            composed["carry"] = carry
        elif edge_in == EdgeType.extract:
            composed["spec"] = carry

        journal.append(root, "phase.entered", unit=unit.id, phase=phase.name,
                       phase_index=phase_index,
                       edge_in=edge_in.value if edge_in else "create")

        if phase.delivery == "deterministic" and callable(getattr(phase, "run", None)):
            try:
                ev = phase.run(root, unit, composed) or {}
            except Exception as e:
                journal.append(root, "phase.error", unit=unit.id, phase=phase.name,
                               phase_index=phase_index, error=str(e))
                receipt = Receipt(outcome="stall", status="blocked",
                                  surfaced=[f"phase.run failed: {e}"])
            else:
                facts = ev.get("facts") or {}
                if facts:
                    journal.append(root, "phase.facts", unit=unit.id, phase=phase.name,
                                   phase_index=phase_index, facts=facts)
                receipt = Receipt(
                    outcome="result" if ev.get("passed", True) else "stall",
                    status="complete", evidence=ev)
        else:
            receipt = executor.run(unit, composed)

        decision = decide_step(workflow, unit, name, edge_in, receipt, composed, verifiers)
        gate, verified = decision["gate"], decision["verified"]

        evidence = decision["evidence"]
        if isinstance(evidence, dict):
            agg_evidence.update(evidence)
        phase_fit = evidence.get("phase_fit", "clean")
        suggested = evidence.get("suggested")
        phase_fits[phase.name] = phase_fit

        journal.append(root, "phase.exited", unit=unit.id, phase=phase.name,
                       phase_index=phase_index, phase_fit=phase_fit, gate=gate,
                       verified=verified)

        if phase_fit in ("loose", "none"):
            journal.append(root, "phase.gap", unit=unit.id, phase=phase.name,
                           suggested=suggested, fit=phase_fit)
            gaps.append({"phase": phase.name, "suggested": suggested, "fit": phase_fit})

        walked.append(phase.name)
        carry = evidence.get("produces")
        outputs[phase.name] = carry

        passed = decision["passed"]
        advance = decision["advance"]
        choice = decision["choice"]
        nxt = decision["next"]

        emitted = evidence.get("next")
        facts_emitted = bool(evidence.get("facts"))
        if emitted and not _has_choice_edge(workflow, name, emitted):
            stall = _stall_on_unmatched(root)
            fallthrough = nxt[0] if nxt else None
            _journal_route_unmatched(
                root, unit=unit.id, phase=name, phase_index=phase_index,
                next=emitted, kind=_classify_route(root, emitted),
                resolved="stall" if stall else fallthrough)
            if stall:
                journal.append(root, "phase.stalled", unit=unit.id, phase=name,
                               phase_index=phase_index,
                               note=f"unmatched route next={emitted!r}")
                break
        elif facts_emitted and not emitted and nxt is None:

            stall = _stall_on_unmatched(root)
            _journal_route_unmatched(
                root, unit=unit.id, phase=name, phase_index=phase_index,
                next=None, kind="no-match", resolved="stall" if stall else None)
            if stall:
                journal.append(root, "phase.stalled", unit=unit.id, phase=name,
                               phase_index=phase_index,
                               note="unmatched fact route (no predicate/default matched)")
                break

        if nxt is None:
            break
        name, edge_in = nxt
        phase_index += 1

    final_receipt = {
        "outcome": receipt.outcome if receipt else "stall",
        "status": receipt.status if receipt else "blocked",
        "surfaced": list(receipt.surfaced) if receipt else [],
        "evidence": agg_evidence,
        "cost": receipt.cost if receipt else None,
        "tool_calls": receipt.tool_calls if receipt else 0,
    }
    fire(contributors, "unit-close", HookContext(
        root=root, step="unit-close", unit=unit,
        receipt=final_receipt, verdict=None))
    return {"unit": unit.id, "workflow": workflow.name, "phases": walked,
            "phase_fits": phase_fits, "gaps": gaps,
            "final": final_receipt, "receipt": final_receipt}

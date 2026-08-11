#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

import journal
from contributors import gather
from workflow import GATES, EdgeType, Workflow


def _next_edge(workflow: Workflow, from_phase: str):
    for (f, t, when, et) in workflow.edges:
        if f == from_phase and when in ("pass", "always"):
            return t, et
    return None


def run_workflow(root: Path, unit, workflow: Workflow, contributors, executor,
                 verifiers: dict | None = None, start: str | None = None) -> dict:
    verifiers = verifiers or {}
    by_name = {p.name: p for p in workflow.phases}
    name = start or workflow.first.name

    edge_in = None
    carry = None
    phase_index = 0
    walked: list[str] = []
    phase_fits: dict[str, str] = {}
    gaps: list[dict] = []
    receipt = None

    while name is not None:
        phase = by_name[name]
        situation = copy.copy(unit.situation)
        situation.phase = phase.name
        composed = gather(contributors, situation, root=root)
        if edge_in == EdgeType.carry:
            composed["carry"] = carry
        elif edge_in == EdgeType.extract:
            composed["ir"] = carry

        journal.append(root, "phase.entered", unit=unit.id, phase=phase.name,
                       phase_index=phase_index,
                       edge_in=edge_in.value if edge_in else "create")

        receipt = executor.run(unit, composed)

        gate = GATES[edge_in] if edge_in else GATES[EdgeType.create]
        verifier = verifiers.get(gate)
        verified = verifier.verify(unit, receipt, composed).verified if verifier else True

        evidence = receipt.evidence or {}
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

        nxt = _next_edge(workflow, name)
        if nxt is None:
            break
        name, edge_in = nxt
        phase_index += 1

    return {"unit": unit.id, "workflow": workflow.name, "phases": walked,
            "phase_fits": phase_fits, "gaps": gaps,
            "final": receipt.to_dict() if receipt else None}

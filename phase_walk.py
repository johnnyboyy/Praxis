#!/usr/bin/env python3
"""phase_walk — the RESUMABLE, model-driven phase-walk surface (Spine B1).

`next_phase`/`record_phase` step a unit through its gated workflow ONE PHASE at a
time, exactly as `next_handoff`/`record_receipt` step the unit graph one level up.
The cursor lives in the JOURNAL, never in the caller: `next_phase` is a PURE READ
that folds this unit's `phase.verdict`/`phase.recorded` events to decide the phase
to execute now; `record_phase` appends the phase result, runs the incoming edge's
gate verifier FROM DISK, journals the verdict, and computes the next edge.

The gate + edge decision is NOT re-implemented here — both `run_workflow` (the
synchronous loop) and this surface call `workflow_run.decide_step`, so the two
paths cannot drift. Fail-soft on a malformed/partial journal state.
"""
from __future__ import annotations

from pathlib import Path

import journal
from run import Receipt, verifiers_for_workflow
from workflow import EdgeType
from workflow_run import _incoming, decide_step, gate_for


# --- workflow / verifier resolution ----------------------------------------

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
    """The situation stance a phase runs under, mirroring run_workflow."""
    return phase.stance if phase.stance in ("divergent", "convergent") else "none"


def _edge_type(value):
    if value in (None, "create"):
        return None
    try:
        return EdgeType(value)
    except ValueError:
        return None


# --- journal fold: the cursor lives here -----------------------------------

def _unit_events(root: Path, unit_id: str) -> list[dict]:
    return [e for e in journal.read(root) if e.get("unit") == unit_id]


def _produces_by_phase(events: list[dict]) -> dict:
    """phase name -> its last-recorded produced artifact (for input/carry/spec threading)."""
    out: dict = {}
    for e in events:
        if e.get("event") == "phase.recorded":
            out[e.get("phase")] = e.get("produces")
    return out


def _cursor(root: Path, unit, workflow) -> dict:
    """Fold this unit's verdicts to the cursor: which phase to execute now.

    Returns a dict with `status` one of:
      * "phase"    — {phase, edge_in (EdgeType|None), from_phase, phase_index}
      * "complete" — the walk reached a terminal (no next edge on an advance)
    The rule mirrors run_workflow's loop exactly (via the SAME `_choose_edge`
    result stored on the verdict): follow the stored `next` edge when there is
    one; if there is none, a terminal on an advance is COMPLETE, and a non-advance
    (gate failed with no fail/halt route) RE-HANDS the same phase — never the
    pass-route successor."""
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
    # Gate failed and the workflow had no fail/halt route: re-hand the SAME phase.
    return {"status": "phase", "phase": last.get("phase"),
            "edge_in": _edge_type(last.get("edge_in")),
            "from_phase": last.get("from_phase"),
            "phase_index": int(last.get("phase_index", 0))}


# --- next_phase: the pure-read cursor surface -------------------------------

def next_phase(root, unit, workflow=None) -> dict:
    """Return the phase to execute NOW for `unit`, folded from the journal.

    A PURE READ — calling it twice without an intervening `record_phase` returns
    the same phase (idempotent). `no-workflow` when the unit has no workflow;
    `complete` when the walk has reached a terminal. Otherwise returns the phase
    directive: {phase, delivery, stance, gate (the incoming edge's GATES entry),
    inputs/carry/spec to inject, isolation (the extract->synthesize seam)}."""
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
    if phase is None:  # fail-soft: cursor points at an unknown phase
        return {"status": "no-workflow", "unit": unit.id,
                "note": f"cursor phase {name!r} not in workflow {workflow.name!r}"}

    produces = _produces_by_phase(_unit_events(root, unit.id))
    inputs = {f: produces[f] for (f, _et) in _incoming(workflow, name) if f in produces}

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
        # The isolation seam: entering synthesize via the extract edge must run in
        # an spec-only worktree, seeded with the spec (isolation.seed_synth_worktree).
        out["isolation"] = {
            "seed_worktree": True,
            "seam": f"{from_phase}->{name}",
            "seeder": "isolation.seed_synth_worktree",
            "spec": spec,
            "reason": "seed an spec-only synth worktree; the original is withheld",
        }
    return out


# --- record_phase: append the result, gate from disk, advance the cursor ----

def _compose_for_gate(edge_in, produces_by_phase, from_phase, evidence) -> dict:
    """Build the `composed` the gate verifier reads (spec threaded on the extract edge)."""
    composed: dict = {}
    if edge_in == EdgeType.extract:
        composed["spec"] = produces_by_phase.get(from_phase)
    elif edge_in == EdgeType.carry:
        composed["carry"] = produces_by_phase.get(from_phase)
    # tool_log surfaces to the copy tripwire (composed first, then receipt.evidence).
    if evidence.get("tool_log") is not None:
        composed["tool_log"] = evidence.get("tool_log")
    return composed


def record_phase(root, unit, phase, evidence, verifiers: dict | None = None,
                 verifier=None, workflow=None) -> dict:
    """Record `phase`'s result, gate it FROM DISK, and advance the journal cursor.

    Appends the phase result (`produces`/`facts`/`tool_log`), runs the incoming
    edge's gate verifier against the evidence on disk (the create/preservation/adequacy verifiers; for a
    rebuild unit the synthesize-exit gate is the tripwire+coverage_diff gate, fed
    `produces`/`tool_log`), journals the verdict, and computes the next edge via
    `_choose_edge` — all through the SAME `decide_step` the synchronous loop uses.
    Crucially the cursor DOES NOT advance past a failed gate: the next `next_phase`
    re-hands the same phase (or the workflow's fail/halt route), never the
    successor. `no-workflow` when the unit has no workflow."""
    root = Path(root).resolve()
    workflow = _resolve_workflow(root, unit, workflow)
    if workflow is None:
        return {"status": "no-workflow", "unit": unit.id}

    evidence = dict(evidence or {})
    cur = _cursor(root, unit, workflow)
    # Locate the incoming edge for THIS phase (normally the cursor's phase).
    if cur["status"] == "phase" and cur["phase"] == phase:
        edge_in = cur["edge_in"]
        from_phase = cur["from_phase"]
        phase_index = cur["phase_index"]
    else:
        # Fail-soft: caller recorded a phase other than the cursor's. Best-effort
        # incoming edge (create for the first phase, else the first wired edge).
        edge_in = None if phase == workflow.first.name else \
            next((et for (_f, et) in _incoming(workflow, phase)), None)
        from_phase = next((f for (f, _et) in _incoming(workflow, phase)), None)
        prev = [e for e in _unit_events(root, unit.id) if e.get("event") == "phase.verdict"]
        phase_index = (int(prev[-1].get("phase_index", -1)) + 1) if prev else 0

    produces = _produces_by_phase(_unit_events(root, unit.id))
    composed = _compose_for_gate(edge_in, produces, from_phase, evidence)
    composed["phase"] = phase

    receipt = Receipt(outcome="result" if evidence.get("passed", True) else "stall",
                      status="complete", evidence=evidence)

    if verifiers is None:
        verifiers = verifiers_for_workflow(root, workflow, verifier)

    # Append the phase result BEFORE gating (so its produces is on disk for the fold).
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

    # phase.exited mirrors run_workflow's shape so close-certification works too.
    journal.append(root, "phase.exited", unit=unit.id, phase=phase,
                   phase_index=phase_index, phase_fit=phase_fit, gate=gate,
                   verified=verified)
    # phase.verdict IS the cursor: it carries the entry context + the chosen edge.
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

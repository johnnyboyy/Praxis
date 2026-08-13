#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import conduct as conduct_engine  # noqa: E402
import journal  # noqa: E402
import root_tree  # noqa: E402
import views  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("praxis")

def _root(search_base: str | None) -> Path:
    if search_base:
        return Path(search_base).resolve()
    cwd = Path.cwd()
    resolved = root_tree.resolve_root(cwd)
    return resolved if resolved is not None else cwd

def _managed(search_base: str | None) -> bool:
    return root_tree.resolve_root(_root(search_base)) is not None

_NOT_A_ROOT = json.dumps(
    {"status": "not-a-root",
     "note": "this repo isn't a praxis root yet — run /praxis:init to set it up first"},
    indent=2)

def _parse_tasklist(tasks: str) -> tuple[list | None, str | None]:
    try:
        parsed = json.loads(tasks)
    except json.JSONDecodeError as e:
        return None, json.dumps({"error": f"tasks must be a JSON array of task objects: {e}"}, indent=2)
    if not isinstance(parsed, list) or not parsed:
        return None, json.dumps({"error": "tasks must be a non-empty JSON array"}, indent=2)
    return parsed, None

@mcp.tool()
def init(search_base: str | None = None) -> str:
    """Mark the current git repo (or folder) as a praxis root by ensuring an empty
    `.praxis/config.json`, so the gate and drive tools begin managing it. The file is a
    namespaced store plugins persist their own config in; a fresh root starts clean (`{}`)."""
    return json.dumps(conduct_engine.init_root(root=search_base), indent=2)

@mcp.tool()
def plan_status(search_base: str | None = None) -> str:
    """Progress of the current plan, folded from the journal: per-unit buckets (done / in_flight /
    stalled / escalated / waiting) and the cost rollup. `no-plan` when nothing has been planned
    for this root."""
    return json.dumps(conduct_engine.plan_status(_root(search_base)), indent=2)

@mcp.tool()
def register_plan(tasks: str, search_base: str | None = None) -> str:
    """Record a tasklist's unit graph to the journal — the entry point for driving units of work.
    `tasks` is a JSON array of task objects:
      { "intent": <what this task does>,            // required
        "id": <stable id>,                            // optional; how other tasks reference it
        "task_kind": "create|change|explore",         // the seed verb (default change)
        "subject": "coding|design|process|prose",     // default coding
        "suggested_kind": <what you'd freely call it>,// THE gap candidate — fill it honestly
        "fit": "clean|loose|none",                    // how well task_kind fits (default clean)
        "workflow": <workflow name>,                  // optional; makes the unit phase-walked
        "depends_on": [<id>, ...] }                   // tasks that must finish first (the unit graph edges)

    YOU are the planner: decompose the request into these tasks and infer the `depends_on` edges
    before calling this. It writes one plan event (deterministic, no spawn); then call
    `next_handoff` to pull the next ready unit into THIS context — it frames the unit and opens the
    edit gate — and either do the work here or dispatch it to a subagent. Repeat next_handoff until
    it reports `complete`. A loose/none `fit` surfaces a vocabulary gap — fill it honestly."""
    if not _managed(search_base):
        return _NOT_A_ROOT
    parsed, err = _parse_tasklist(tasks)
    if err:
        return err
    return json.dumps(conduct_engine.register_plan(_root(search_base), parsed), indent=2)

@mcp.tool()
def next_handoff(brief: str | None = None, search_base: str | None = None) -> str:
    """PULL the next ready unit's handoff (brief + composed overlay) from the current plan, for a
    self-advancing agent that chains units in one context. Recording the pull opens the edit gate for
    that unit — you cannot edit for it until you have pulled it. Returns a `waiting`/`complete`
    status when nothing is ready, or `no-plan` when no tasklist has been planned for this root."""
    return json.dumps(conduct_engine.next_handoff(_root(search_base), brief=brief), indent=2)

@mcp.tool()
def next_phase(unit_id: str, search_base: str | None = None) -> str:
    """PULL the next PHASE of a workflow-driven unit's gated walk into this context — the
    phase-level twin of `next_handoff`. Folds the unit's phase events in the journal (a pure read,
    no mutation) and returns the phase to execute now: its `delivery`, the incoming edge's
    `gate`, the `inputs`/`carry`/`spec` to inject, a per-phase `overlay` composed from the
    registered contributors (when any speak for this phase), and an `isolation` directive when the phase must run
    in a seeded worktree (the extract->synthesize seam). Returns `complete` when the walk has reached
    a terminal, `no-workflow` when the unit isn't workflow-driven, or `no-plan`/`unknown-unit`. Idempotent:
    calling it again without `record_phase` re-hands the same phase."""
    return json.dumps(conduct_engine.next_phase(_root(search_base), unit_id), indent=2)

@mcp.tool()
def record_phase(unit_id: str, phase: str, evidence: str | None = None,
                 test_cmd: str | None = None, search_base: str | None = None) -> str:
    """Record one PHASE's result and advance the journal cursor — the phase-level twin of
    `record_receipt`. `evidence` is a JSON object of the phase's output (`produces`, `facts`,
    `tool_log`, and `passed`); the incoming edge's gate verifier is run FROM DISK against it (for a
    rebuild unit's synthesize-exit, the copy-tripwire + coverage-diff preservation gate). The cursor
    NEVER advances past a failed gate — the next `next_phase` re-hands the same phase (or the
    workflow's fail/halt route), never the successor. Then call `next_phase` again for the next step."""
    parsed: dict = {}
    if evidence:
        try:
            parsed = json.loads(evidence)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"evidence must be a JSON object: {e}"}, indent=2)
        if not isinstance(parsed, dict):
            return json.dumps({"error": "evidence must be a JSON object"}, indent=2)
    return json.dumps(conduct_engine.record_phase(_root(search_base), unit_id, phase,
                                                  evidence=parsed, test_cmd=test_cmd), indent=2)

@mcp.tool()
def close_unit(unit_id: str | None = None, note: str | None = None,
               search_base: str | None = None) -> str:
    """Mark the current inline unit done so its dependents unlock and the edit gate closes; call it
    when you finish an inline unit pulled via next_handoff."""
    return json.dumps(conduct_engine.close_unit(_root(search_base), unit_id=unit_id, note=note),
                      indent=2)

@mcp.tool()
def record_receipt(unit_id: str, outcome: str = "result", note: str | None = None,
                   search_base: str | None = None) -> str:
    """Journal the outcome of a dispatched unit. `outcome=result` marks the unit done and unlocks its
    dependents; `outcome=stall` marks it blocked (with `note` as the blocker) and its dependents stay
    waiting."""
    return json.dumps(conduct_engine.record_receipt(_root(search_base), unit_id, outcome=outcome,
                                                     note=note), indent=2)

@mcp.tool()
def escalate_unit(unit_id: str, reason: str | None = None,
                  search_base: str | None = None) -> str:
    """Escalate a unit to a human: mark its bounded fix loop EXHAUSTED (needs-human). Use this
    instead of `record_receipt(stall)` when a unit cannot progress on its own retries and requires
    a person — it is a one-way terminal state. An escalated unit surfaces in its own `escalated`
    bucket in `plan_status` (distinct from `stalled`) and can no longer be closed or receipted
    `result` until a human intervenes."""
    return json.dumps(conduct_engine.escalate_unit(_root(search_base), unit_id, reason=reason),
                      indent=2)

@mcp.tool()
def conductor_status(search_base: str | None = None) -> str:
    """The journal fold for the governing root: the open unit (if any), the deliver-vs-stall summary
    by phase and workflow, and the cost rollup."""
    root = _root(search_base)
    f = journal.fold(root)
    return json.dumps({"root": str(root), "open_unit": journal.open_unit(root),
                       "summary": f["summary"], "cost": views.cost(root)}, indent=2)

if __name__ == "__main__":
    mcp.run()

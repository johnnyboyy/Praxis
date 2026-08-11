---
description: Drive a task autonomously through praxis, dispatching each unit as a fresh subagent via the Agent tool. Use for multi-step work you want fanned out, verified at a barrier, and fixed on failure.
disable-model-invocation: true
---

The task to drive is: $ARGUMENTS

Drive it through praxis with the Agent tool as the executor. praxis owns framing, the unit DAG, the journal, and the edit gate; you dispatch each unit as a fresh subagent.

1. DECOMPOSE into a tasklist: a JSON array of unit objects, each with `intent`, `task_kind` (create|change|explore), `subject`, `fit`, and `depends_on` edges. Fill `fit` honestly. Call `register_plan` (praxis) to record the DAG.

2. FAN OUT — repeat:
   - Call `next_handoff`. On `complete`/`waiting` with nothing ready, stop the loop.
   - It returns a ready unit with `unit`, `brief`, and `overlay`. Dispatch it as a fresh subagent via the Agent tool (subagent_type general-purpose): prompt = the `brief`, plus the `overlay` as guidance if non-empty, plus "Work only in this repo. Report what you changed, or the blocker if you cannot finish." Run several in parallel (run_in_background) when the DAG has multiple ready units.
   - When a subagent returns: call `record_receipt` with `outcome=result` if it finished (unlocks dependents), or `outcome=stall` with the blocker as `note` if it could not (dependents stay blocked).
   - Loop until `next_handoff` reports `complete`.

3. BARRIER — once the units are done, run the full verification once yourself (the project's test command, via Bash).
   - Pass → go to CLOSE.
   - Fail → FIX LOOP: for each defect, dispatch a fix subagent via the Agent tool (the code exists — a carry-edge patch) targeting it; `record_receipt` each; re-run the barrier. Bound to 3 rounds.

4. ESCALATE (stop and surface to the user; do not loop) when: a fan-out unit stalled, the fix loop exhausts its rounds, or a fix subagent reports the fix is a re-architecture, not a patch.

5. CLOSE — report what ran, what the barrier showed, and any escalations. Tell the user they could drop out while the subagents ran.

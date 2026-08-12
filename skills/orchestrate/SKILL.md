---
description: Drive complex, multi-step work through praxis end to end — interview it to a barrier, decompose into a DAG, fan each unit out as a fresh subagent, verify against that barrier, and fix on failure. The complex path; use `inline` for simple, single-context work.
disable-model-invocation: true
---

The task to drive is: $ARGUMENTS

Drive it through praxis with the Agent tool as the executor. praxis owns framing, the unit DAG, the journal, and the edit gate; you interview the work into a plan, then dispatch each unit as a fresh subagent and hold the result to the barrier you defined.

1. INTAKE — drive the planner's `intake` workflow (`interview -> frontier -> barrier -> plan`) to turn the request into a plannable DAG. This settles the decisions the work hinges on before slicing it, instead of decomposing blind.
   - INTERVIEW — surface the decisions the work actually hinges on, following the `interviewing` discipline: ask **one question at a time**; when there is one clear direction, **name it and ask for confirmation** rather than manufacturing a choice; **frame each question for a cheap answer**. Record every surfaced decision into `<root>/.praxis/planner/frontier.md` as a checklist item — `- [ ] <decision>` while open, `- [x]` once answered. A fully-specified task surfaces few or no open decisions and clears at once — do not manufacture questions to justify the step.
   - FRONTIER — the deterministic check reads that artifact: `open` while any item is unanswered (or none surfaced yet), `clear` only when at least one item exists and all are answered. Loop INTERVIEW -> FRONTIER until `clear`.
   - BARRIER — define the contract the work must satisfy: the observable behavior/interface a fresh agent can synthesize against (for code, the tests / acceptance conditions), stated as what must be true, not how to build it. This is the EXTRACT step of the rebuild triple (`docs/design.md`) — keep it; step 3 verifies against it.
   - PLAN — emit a sequenced tasklist (each unit: `intent`, `task_kind` create|change|explore, `subject`, `fit` honestly, `depends_on`; sequenced by output dependency; each unit points at the barrier item(s) it must satisfy), then call `register_plan` (praxis) to record the DAG.

2. FAN OUT — repeat:
   - Call `next_handoff`. On `complete`/`waiting` with nothing ready, stop the loop.
   - It returns a ready unit with `unit`, `brief`, and `overlay`. Dispatch it as a fresh subagent via the Agent tool (subagent_type general-purpose): prompt = the `brief`, plus the `overlay` as guidance if non-empty, plus "Work only in this repo. Report what you changed, or the blocker if you cannot finish." Run several in parallel (run_in_background) when the DAG has multiple ready units.
   - When a subagent returns: call `record_receipt` with `outcome=result` if it finished (unlocks dependents), or `outcome=stall` with the blocker as `note` if it could not (dependents stay blocked).
   - Loop until `next_handoff` reports `complete`.

3. BARRIER — once the units are done, verify against the barrier you defined in INTAKE, run once yourself (for code, the acceptance tests / project test command, via Bash).
   - Pass → go to CLOSE.
   - Fail → FIX LOOP: for each defect, dispatch a fix subagent via the Agent tool (the code exists — a carry-edge patch) targeting it; `record_receipt` each; re-run the barrier. Bound to 3 rounds.

4. ESCALATE (stop and surface to the user; do not loop) when: a fan-out unit stalled, the fix loop exhausts its rounds, or a fix subagent reports the fix is a re-architecture, not a patch.

5. CLOSE — report what ran, whether the barrier held, and any escalations.

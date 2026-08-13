---
description: Drive complex, multi-step work through praxis end to end — interview it to a barrier, decompose into a gated unit graph, and walk each unit through the engine's phase gates with subagents as the executor, so "done" is defined by passed gates, not self-report. The complex path; use `inline` for simple, single-context work.
disable-model-invocation: true
---

The task to drive is: $ARGUMENTS

Drive it through praxis with the Agent tool as the executor. praxis owns framing, the unit graph, the workflow gates, the journal, and the edit gate; you interview the work into a barrier, then walk each unit through its gated workflow, dispatching each phase as a fresh subagent. The engine runs the gates from disk and refuses to advance a unit past a failed gate — you cannot self-certify a unit to done.

1. INTAKE — drive the planner's `intake` workflow (`interview -> frontier -> barrier -> plan`) to turn the request into a plannable unit graph, settling the decisions the work hinges on before slicing it.
   - INTERVIEW — surface the decisions the work actually hinges on, following the `interviewing` discipline: ask **one question at a time**; when there is one clear direction, **name it and ask for confirmation** rather than manufacturing a choice; **frame each question for a cheap answer**. Record every surfaced decision into `<root>/.praxis/planner/frontier.md` (`- [ ] <decision>` open, `- [x]` answered). A fully-specified task surfaces few or no open decisions and clears at once — do not manufacture questions.
   - FRONTIER — the deterministic check reads that artifact: `open` while any item is unanswered (or none surfaced yet), `clear` only when at least one item exists and all are answered. Loop INTERVIEW -> FRONTIER until `clear`.
   - BARRIER — define the contract the work must satisfy: the observable behavior/interface a fresh agent can synthesize against (for code, the acceptance tests + the coverage threshold), stated as what must be true, not how to build it. This is the EXTRACT step of the rebuild triple (`docs/design.md`).
     - Author **integration-contract tests** here, not only per-unit acceptance tests: name the shared interfaces / runtime state / ordering the units will straddle, and write cross-unit tests for them — so integration is somebody's job, not hoped-for out of the full suite.
     - The barrier is **append-only during implementation**: an implementer that discovers an unhandled case may propose an ADDITION (never a modification), which you approve and append. The contract only grows; it never bends to fit an implementation.
   - PLAN — emit a sequenced tasklist. Each unit: `intent`, `task_kind` (create|change|explore), `subject`, `fit` honestly, `depends_on`, and a `workflow` **when the work fits one** — `rebuild-triple` for a re-architecture/rewrite, `tdd-unit`/`build-verify` for a feature, left unset for a simple single-dispatch unit. Sequence by output dependency; each unit points at the barrier item(s) it must satisfy. Call `register_plan`.

2. FAN OUT — repeat: call `next_handoff`; on `complete`/`waiting` with nothing ready, stop the loop. For each ready unit, run independent ones in parallel (`run_in_background`):
   - **No workflow** → dispatch ONE fresh subagent (prompt = `brief` + `overlay` as guidance + "Work only in this repo. Report what you changed, or the blocker."); `record_receipt` `result` (unlocks dependents) or `stall` (blocker as `note`).
   - **Has a workflow** → WALK it through the engine's gates:
     a. `next_phase(unit)` → the phase to run now + its `gate`, the `inputs`/`ir` to inject, and an `isolation` directive when present. On `complete`, every gate passed — `record_receipt` `result` and move on.
     b. Dispatch a fresh subagent for **that phase**: prompt = the phase intent + the injected `inputs`/`ir` + "Work only in <the phase's tree>. Report the artifact you produced (the path)." If `isolation` is set (the extract→synthesize seam), dispatch INTO the seeded worktree it names — the subagent sees the spec, **not** the original — and capture the subagent's file reads to pass as `tool_log` (the tripwire). The synthesize subagent's reads are captured by the `tripwire_log.sh` PreToolUse hook keyed on the subagent's `agent_id` (the id the Agent spawn returns); after it returns, read them via `isolation.read_tool_log(<root>/.praxis/tripwire.log, agent_id)` (or `isolation.synth_tool_log(root, agent_id)`) and pass the result as `tool_log`.
     c. `record_phase(unit, phase, {produces, tool_log, facts})` — the engine runs the phase's gate FROM DISK (coverage / held-out + surface / tripwire) and journals the verdict. If it does NOT advance (re-hands the same phase), the gate failed: dispatch a fix subagent for that phase and re-record, bounded to 3 rounds, then ESCALATE.
     Loop a–c until `next_phase` → `complete`.
   The per-unit coverage gate fires here, during the walk — a unit only advances when its acceptance tests pass at threshold; it re-runs after any `test-cleanup` phase so pruning scaffolding cannot drop coverage.

3. FINAL BARRIER — once every unit is done, run the full verification ONCE yourself before close: the full test suite, plus any adequacy signal the root configures (e.g. a mutation run scoped to the plan's changed files). A failing barrier BLOCKS close. On failure, route the defect to a SINGLE fixer subagent with GLOBAL context (the whole diff + the barrier) — not back to the isolated implementers, who each lack the whole picture. Re-run the barrier, bounded to 3 rounds.

4. ESCALATE — an explicit stop surfaced to the user, never a silent stall — when: a fan-out unit stalled, a phase gate stayed red past its fix budget, the final barrier's fix loop exhausted its rounds, or a fix subagent reports the fix is a re-architecture, not a patch.

5. CLOSE — report what ran, which gates held, and any escalations. Close is reachable only through passed gates.

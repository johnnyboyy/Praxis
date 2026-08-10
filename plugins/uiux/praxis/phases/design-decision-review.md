# Phase: design-decision-review

Review a divergent unit's `Artifact` (a UI/UX identity or aesthetic decision) as accept / revise /
reject, and file an accepted decision into the project's UI/UX library. Migrated from corpora
`processes/design-decision-review.md`. This is **entirely separate from the ratify gate**: a design
decision has no `condition` to weigh a future case against and no fork to guard against
re-litigating — it is what the project's identity *is*, right now — so it never enters `proposals:`
and never reaches the gate. Praxis carries the deterministic *routing* fact (which handoffs land
here vs. at the gate) and leaves the accept/revise/reject to the operator + engine.

**Entry condition (a deterministic routing fact):** a handoff whose `stance: divergent`, **or** whose
`Artifact` targets `ui-library.md`/`ux-library.md` content. Both are readable from the handoff's
own fields (`stance` is a base-schema field; the library target is what the library-init/sync phases
produce). This runs during relay, *before* the ratify gate ever sees the handoff.

**Stance:** none of its own — it reviews another unit's divergent output. Not a new composition.

**Invocations:** none of the judgment engine — this is an operator decision (accept/revise/reject)
plus, on accept, a write into the library. A revise resumes the *same* workstream agent (the
`questions-pending` continuation mechanic), so its context survives.

## Deterministic facts — run first

- the handoff's `stance` and whether its `Artifact` targets a library document — the routing test
  above. Praxis reads these from the handoff it already validates; nothing else is computed.

## The review (operator's three responses)

1. **Present the `Artifact`** as one unit — the whole library document (a founding unit) or the
   specific section(s) it changes (an ongoing designer unit).
2. **Accept** — write the content into the library now, replacing the superseded section outright.
   No "(direction, <date>)" tag, no "supersedes X" lead-in, no dates, no naming what was rejected —
   the library describes only current state; git history is its audit trail. A still-live accepting
   agent performs the write itself; otherwise the orchestrator applies it.
   **Revise** — relay the specific feedback and resume the same workstream agent (returns to
   execution, not to routing); the workstream and context survive. Not a rejection.
   **Reject** — discard. No kill-log entry and no `reason_killed` — a rejected design decision has no
   future re-proposal to guard against.
3. **`ui-drift` stays open until accepted** — the handoff's self-reported drift only means the
   library is caught up once the decision is actually accepted and written. A revise/reject leaves
   the drift counters as they were.
4. **Resolve deferred decisions** — mark any `.corpora/deferred-decisions.md` entry this acceptance
   settles as resolved, `deferred_queue.py resolve --id <id> --resolution <how>` — which KEEPS it as a
   trace (the backward spine), not deletes it, so a later pass sees it was raised and how it was
   settled. A revise/reject resolves nothing.

**Artifact:** the accepted content written into `ui-library.md`/`ux-library.md`, or the
revised-and-resumed workstream, or a clean discard.

**Surfaced/lacking:** any genuine judgment/knowledge the session *also* surfaced (a real tradeoff
whose reason will bind future weighing, distinct from the identity choice) still goes through
`proposals:` and the ratify gate — this phase handles only the `Artifact` and has no opinion on
`proposals:`.

---
subject: process
posture: guardrail
units-of-work: [plan-work]
universal: false
---

# Domain: planning

Judgment about decomposing roadmap capabilities into sequenced task lists and managing the work
queue. Provenance and per-kill detail in `domains/audit.md`.

Also defines the **queue file schema** (`.corpora/queue.md`) — the planning spawn writes it; the
process layer reads it and routes from it. The planning spawn only produces the decomposition; the
queue's lifecycle and the loop that consumes it belong to the process layer.

A planning spawn is a disambiguator, not a solver: reduce a capability's ambiguity to the point
where other spawns can act, then decompose what remains into a sequenced, actionable task list —
including whether a resolved ambiguity later warrants a re-entry into disambiguation. Read `.corpora/config.md` and
`.corpora/queue.md` (if it exists, to avoid re-queuing work already in progress) before orienting. Dialogue is scoped to the capability description, its own subject: do
not anticipate the direction questions downstream spawns will face mid-work — those belong to the
executing spawn, in its own composition, at the moment they arise, via the `questions-pending`
handoff channel (`kernel.md`, "The handoff artifact"). Out of scope: assigning tasks to specific
compositions, prescribing implementation approach or design direction, re-planning work already in
progress or complete, ratifying its own proposals, or any routing/orchestration work — output the
queue and stop.

---

## Queue file schema

The queue lives at `.corpora/queue.md` in the project root. One active capability at a time.

```yaml
capability: "Exact capability statement from ROADMAP.md"
area: "Area name from ROADMAP.md"
status: active       # active | complete | on-hold
created: YYYY-MM-DD
updated: YYYY-MM-DD

tasks:
  - id: <area-abbrev>-<nn>      # e.g. disc-01, song-03
    title: "Short, actionable title"
    description: "What this task requires and what its output is."
    context: ""                  # what the planning spawn found during orientation: current state, relevant
                                 # files, what exists vs. what is missing. Also: any concepts this
                                 # task shares with other tasks in this capability — state, data, or
                                 # behavior that multiple tasks will read or mutate — so the executing
                                 # spawn starts with the interaction surface visible, not just the
                                 # task's own scope. Populated by the planning spawn so the executing spawn
                                 # does not re-derive it.
    status: pending              # pending | in-progress | complete | blocked
    blocked-by: []               # list of task ids this task cannot start without
    parallel-ok: false           # true if this task can run alongside its non-blocking peers
    concern: ""                  # what kind of work this task involves — open-ended, named from
                                 # what orientation found (e.g. visual, interaction, implementation).
                                 # The process layer routes from this; the planning spawn does not name compositions.
    judgment: ""                 # settled | uncertain — whether orientation found established project
                                 # patterns that cover this work, or genuine novel territory where
                                 # judgment under uncertainty is required.
    notes: ""                    # planning spawn or process-layer notes; resolution of open questions

open-questions:
  - id: q-<nn>
    question: "The unanswered question that must be resolved before the task(s) that depend on it."
    blocks: []                   # list of task ids this question blocks
    resolved: false
    answer: ""

not-yet-specified:
  - id: nys-<nn>
    note: "A question or area sensed as in-scope but not yet sharp enough to state precisely —
           the dim view toward the destination, not a task to slice prematurely."

out-of-scope:
  - id: <the task or nys id that was closed out>
    gist: "One-line restatement of what it was, for legibility without reopening the ticket."
    reason: "Why it sits past the capability's scope."
```

Rules:
- `id` must be stable once written — the process layer uses it to mark status. An id is unique
  across the whole file — `tasks`, `open-questions`, `not-yet-specified`, and `out-of-scope` share
  one namespace, since `queue-mark-out-of-scope` looks an id up across `tasks` and
  `not-yet-specified` without the caller naming which.
- A task whose `blocked-by` list is non-empty and contains any `pending` or `in-progress` ids
  cannot be started.
- A question that is `resolved: false` blocks all tasks in its `blocks` list.
- `not-yet-specified` carries no status or blocking fields — it isn't a task yet. An entry
  **graduates** when it becomes sharp enough to state precisely (not when it becomes answerable):
  add the real task to `tasks:` by hand, the same authorship as any other task, then run
  `corpus.py queue-graduate --id <nys> --task-id <t>` to remove the fog entry and confirm the
  pointer isn't dangling.
- `out-of-scope` is a closed ledger: a task or `not-yet-specified` entry that turns out to sit
  past the capability's own scope is moved there with a reason, never deleted outright and never
  a task again. `corpus.py queue-mark-out-of-scope --id <id> --reason <text>` does the move.
- The process layer updates `status` on tasks and `resolved`/`answer` on questions in-place —
  `corpus.py queue-set-status --id <t> --status <s>` and `corpus.py queue-resolve-question --id <q>
  --answer <text>`, never a hand edit; `queue-status` reads the current state (including whether a
  given task is actually startable) without one, and `lint-queue` validates the file structurally.
- When all tasks are `complete` and all questions are `resolved`, set the top-level `status` to
  `complete` — `queue-set-status`/`queue-resolve-question` do this automatically as their last
  effect, not a separate step to remember.

---

```yaml
last-retrospective: 2026-08-02

principles:

- id: task-is-actionable-without-planning
  rule: "A task must be specific enough that the process layer can route it and a spawn can act on it without doing planning work of its own. If a task description requires the spawn to first decide what the task actually is, it is not yet a task."
  condition: "When decomposing a capability into tasks."
  reason: "The planning spawn's job is to consume the ambiguity so executing spawns do not have to. A task that delegates planning back to the spawn negates the benefit of the queue and makes the process layer's loop-mode routing unreliable."

- id: sequence-by-output-dependency
  rule: "Sequence tasks by what each task's output is required by, not by assumed composition order. Two tasks that don't depend on each other's output are parallelizable regardless of which composition would handle them."
  condition: "When ordering tasks in the queue."
  reason: "Composition order (ux-design before ui-design before coder) is a heuristic, not a law. It breaks when tasks within a capability don't align with that order. Output dependency is the correct sequencing signal — it holds regardless of who does the work."

- id: open-questions-are-explicit
  rule: "A question the planning spawn cannot resolve from available information must appear as an explicit open question in the queue, with the tasks it blocks listed — never a silent assumption. This includes a shared runtime concept (a current position, a selection, a history, a running count) that two or more decomposed tasks would each need to read or mutate: name the concept, state the conflict, and block every affected task rather than letting them independently decide how it behaves."
  condition: "When a decomposition decision hinges on information the planning spawn does not have — including when a capability description implies multiple tasks will operate on the same underlying runtime concept (e.g. undo + filter, pagination + sort, bookmark + search)."
  reason: "Silent assumptions compound: an unresolved question that travels silently into a task produces a deliverable built on an unknown foundation. This is especially costly for a shared concept — tasks that independently decide how it behaves are locally correct but globally inconsistent, and the conflict only surfaces at runtime, where it's expensive to fix. Making it explicit at planning time moves that cost to where it's cheap — one operator answer becomes context for every affected task."
  see-also: fog-before-ticket, scope-boundary-is-closed-not-silent

- id: task-describes-output-not-implementation
  rule: "A task description states the observable output and its acceptance condition. It does not name files, functions, types, or data paths the executing spawn should touch."
  condition: "When writing or reviewing any task description in the queue."
  reason: "Naming implementation details couples the plan to a specific approach before the implementing spawn has seen the code. It narrows the solution space unnecessarily and makes the queue wrong the moment the code diverges from the assumption — without any signal that it has. The implementing spawn's job is to decide how; the planning spawn's job is to decide what."
  see-also: planning-states-what-not-how-or-who

- id: concern-names-work-not-role
  rule: "When setting a task's `concern` field, name the character of the work (e.g. visual, interaction, implementation) as orientation revealed it — never a composition that should perform it."
  condition: "When decomposing a capability into tasks and populating each task's `concern` field."
  reason: "Naming a composition there pre-empts a routing decision the planning spawn doesn't own, and removes the process layer's flexibility — e.g. it blocks the lighter surface-to-operator path for settled work, which routes off `concern`/`judgment` signals rather than a composition assignment."
  see-also: planning-states-what-not-how-or-who

- id: fog-before-ticket
  rule: "When orientation surfaces something in scope that can't yet be stated as a specific task or open question, write it to `not-yet-specified` rather than silently omitting it or forcing it into an under-specified task or question. The test for fog vs. ticket is whether the question can be stated precisely right now — not whether it can be answered right now."
  condition: "When decomposing a capability into tasks, whenever orientation surfaces an area that is in scope but not yet sharp enough to phrase as a specific task or open question."
  reason: "Without an explicit fog category, a planning spawn facing an unsharp-but-real area has only two bad options: omit it (the same silent-assumption risk `open-questions-are-explicit` already guards against for information gaps, applied here to scope gaps) or force it into a task/question that violates `task-is-actionable-without-planning`. Testing on precision-of-statement rather than answerability keeps the fog category from becoming a dumping ground for genuinely resolvable questions that are just inconvenient to resolve now."
  see-also: open-questions-are-explicit, scope-boundary-is-closed-not-silent

- id: scope-boundary-is-closed-not-silent
  rule: "When a task or not-yet-specified entry turns out to sit past the capability's own destination, move it to `out-of-scope` with a one-line reason rather than deleting it outright or leaving it as an open task. An out-of-scope entry never graduates back into a task; if scope is later redrawn to cover it, that's a new capability, not a resumption."
  condition: "When a task or not-yet-specified entry is judged to fall outside the capability's own scope, whether caught while first decomposing or discovered later as work proceeds."
  reason: "Silent deletion loses the boundary decision itself — a later planning pass has no record this was considered and deliberately excluded, and may re-raise a question the capability already settled. A one-line ledger entry keeps the boundary legible without turning `out-of-scope` into a second queue that could ever be resumed from."
  see-also: open-questions-are-explicit, fog-before-ticket

- id: planning-states-what-not-how-or-who
  rule: "A planning spawn's output states what needs to be true — a task's observable output and acceptance condition, the character of work it involves — never how it should be implemented or who (which composition) should do it."
  condition: "When writing any part of a planning spawn's output — a task's description, its `concern` field, or any future field this domain grows — that could be read as prescribing implementation approach or composition/role assignment rather than describing the work itself."
  reason: "The planning spawn works from only a capability description and its own orientation — it hasn't seen how the executing spawn's implementation will actually take shape, and it doesn't hold the process layer's live view of composition load and availability that a routing decision needs. Prescribing either past that boundary embeds a guess made with the least available information into a plan meant to reduce ambiguity — the executing spawn or the process layer then has to first detect and unwind that guess before they can apply the fuller information they actually have."
  see-also: task-describes-output-not-implementation, concern-names-work-not-role

- id: batch-wide-refactors-by-blast-radius
  rule: "When a task's mechanical change fans out widely enough that no single vertical slice can land it as a demoable, working unit, decompose it as expand (add the new form alongside the old) then migrate in batches sized by blast radius, each batch blocked by the expand, then contract (remove the old form), blocked by every migrate batch. Do not force this shape into an ordinary vertical-slice task, and do not leave it as one oversized task."
  condition: "When decomposing a capability whose core change is a single mechanical edit with a codebase-wide blast radius, rather than a feature built from cooperating vertical slices."
  reason: "`sequence-by-output-dependency` assumes each task's output is a discrete deliverable other tasks consume — that model breaks when the risk isn't sequencing between distinct outputs but a single edit large enough that no task boundary keeps the codebase working mid-change."
  see-also: sequence-by-output-dependency

- id: no-placeholder-content-in-task-steps
  rule: "A task's content must be the actual material an implementer needs, not a placeholder standing in for it. Reject and rewrite text like 'add appropriate error handling,' 'handle edge cases,' 'similar to Task N' (without repeating what that means here), or a reference to a type/function/method not defined anywhere in the plan."
  condition: "Writing or reviewing any task's steps or descriptions in a plan or task queue."
  reason: "A vague placeholder phrase reads as if it specifies something while actually deferring the real decision to whoever executes it — the same gap `task-is-actionable-without-planning` guards against for a task as a whole, applied here to the prose habit of writing confident-sounding but hollow instructions within an otherwise-actionable task. Generating this kind of plausible-but-empty text is a natural failure mode when drafting a plan, since it pattern-matches to what a real instruction looks like."
  see-also: task-is-actionable-without-planning

- id: verify-interface-consistency-across-tasks
  rule: "Before finalizing a decomposition, check that any name, signature, or type one task defines and a later task depends on is used identically across both — same function or type name, same parameters, same return shape. A mismatch is a plan defect, not a detail to reconcile during implementation."
  condition: "Multiple tasks in one decomposition depend on interfaces (functions, types, data shapes) defined by an earlier task in the same decomposition."
  reason: "Tasks are drafted in sequence but read independently by whoever executes them — a name that drifts between the task that defines it and the task that depends on it is invisible within either task read alone, and only surfaces once the dependent task's implementer discovers the mismatch, after commitment already happened."

killed:
```

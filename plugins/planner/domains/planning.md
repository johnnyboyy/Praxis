---
id: planning
subject: process
universal: false
workflows: [intake]
---

# Domain: planning
#
# Judgment about decomposing a capability into a sequenced, actionable set of tasks once ambiguity is
# resolved. Governs how a planning pass turns a capability description plus its own orientation into
# work that another spawn can pick up and act on without re-planning — sequencing by output
# dependency, making unresolved questions and in-scope fog explicit, describing each task by its
# observable output rather than an implementation or a role, keeping the scope boundary a legible
# closed ledger, and checking that interfaces one task defines and another depends on stay consistent
# across the decomposition. A planning pass is a disambiguator, not a solver — it reduces a
# capability's ambiguity to the point where other spawns can act, then decomposes what remains.

principles:

- id: task-is-actionable-without-planning
  rule: "A task must be specific enough that the process layer can route it and a spawn can act on it without doing planning work of its own. If a task description requires the spawn to first decide what the task actually is, it is not yet a task."
  condition: "When decomposing a capability into tasks."
  reason: "The planning pass's job is to consume the ambiguity so executing spawns do not have to. A task that delegates planning back to the spawn negates the benefit of the decomposition and makes routing unreliable."

- id: sequence-by-output-dependency
  rule: "Sequence tasks by what each task's output is required by, not by assumed composition order. Two tasks that don't depend on each other's output are parallelizable regardless of which composition would handle them."
  condition: "When ordering tasks in the decomposition."
  reason: "Composition order (design before build, say) is a heuristic, not a law. It breaks when tasks within a capability don't align with that order. Output dependency is the correct sequencing signal — it holds regardless of who does the work."

- id: open-questions-are-explicit
  rule: "A question the planning pass cannot resolve from available information must appear as an explicit open question, with the tasks it blocks listed — never a silent assumption. This includes a shared runtime concept (a current position, a selection, a history, a running count) that two or more decomposed tasks would each need to read or mutate: name the concept, state the conflict, and block every affected task rather than letting them independently decide how it behaves."
  condition: "When a decomposition decision hinges on information the planning pass does not have — including when a capability description implies multiple tasks will operate on the same underlying runtime concept (e.g. undo + filter, pagination + sort, bookmark + search)."
  reason: "Silent assumptions compound: an unresolved question that travels silently into a task produces a deliverable built on an unknown foundation. This is especially costly for a shared concept — tasks that independently decide how it behaves are locally correct but globally inconsistent, and the conflict only surfaces at runtime, where it's expensive to fix. Making it explicit at planning time moves that cost to where it's cheap — one operator answer becomes context for every affected task."
  see-also: fog-before-ticket, scope-boundary-is-closed-not-silent

- id: task-describes-output-not-implementation
  rule: "A task description states the observable output and its acceptance condition. It does not name files, functions, types, or data paths the executing spawn should touch."
  condition: "When writing or reviewing any task description in the decomposition."
  reason: "Naming implementation details couples the plan to a specific approach before the implementing spawn has seen the code. It narrows the solution space unnecessarily and makes the plan wrong the moment the code diverges from the assumption — without any signal that it has. The implementing spawn's job is to decide how; the planning pass's job is to decide what."
  see-also: planning-states-what-not-how-or-who

- id: concern-names-work-not-role
  rule: "When naming the character of a task's work, name what the work is (e.g. visual, interaction, implementation) as orientation revealed it — never a composition or role that should perform it."
  condition: "When decomposing a capability into tasks and describing the kind of work each one involves."
  reason: "Naming a composition or role there pre-empts a routing decision the planning pass doesn't own, and removes the process layer's flexibility — e.g. it forecloses a lighter path for already-settled work that routes off the character and certainty of the work rather than a fixed role assignment."
  see-also: planning-states-what-not-how-or-who

- id: fog-before-ticket
  rule: "When orientation surfaces something in scope that can't yet be stated as a specific task or open question, record it explicitly as fog — an in-scope-but-unsharp area — rather than silently omitting it or forcing it into an under-specified task or question. The test for fog vs. ticket is whether the question can be stated precisely right now — not whether it can be answered right now."
  condition: "When decomposing a capability into tasks, whenever orientation surfaces an area that is in scope but not yet sharp enough to phrase as a specific task or open question."
  reason: "Without an explicit fog category, a planning pass facing an unsharp-but-real area has only two bad options: omit it (the same silent-assumption risk open-questions-are-explicit already guards against for information gaps, applied here to scope gaps) or force it into a task/question that violates task-is-actionable-without-planning. Testing on precision-of-statement rather than answerability keeps the fog category from becoming a dumping ground for genuinely resolvable questions that are just inconvenient to resolve now."
  see-also: open-questions-are-explicit, scope-boundary-is-closed-not-silent

- id: scope-boundary-is-closed-not-silent
  rule: "When a task or fog entry turns out to sit past the capability's own destination, move it to a closed out-of-scope ledger with a one-line reason rather than deleting it outright or leaving it as an open task. An out-of-scope entry never graduates back into a task; if scope is later redrawn to cover it, that's a new capability, not a resumption."
  condition: "When a task or fog entry is judged to fall outside the capability's own scope, whether caught while first decomposing or discovered later as work proceeds."
  reason: "Silent deletion loses the boundary decision itself — a later planning pass has no record this was considered and deliberately excluded, and may re-raise a question the capability already settled. A one-line ledger entry keeps the boundary legible without turning the out-of-scope set into a second queue that could ever be resumed from."
  see-also: open-questions-are-explicit, fog-before-ticket

- id: planning-states-what-not-how-or-who
  rule: "A planning pass's output states what needs to be true — a task's observable output and acceptance condition, the character of work it involves — never how it should be implemented or who (which composition) should do it."
  condition: "When writing any part of a planning pass's output — a task's description, the character of its work, or any other field — that could be read as prescribing implementation approach or composition/role assignment rather than describing the work itself."
  reason: "The planning pass works from only a capability description and its own orientation — it hasn't seen how the executing spawn's implementation will actually take shape, and it doesn't hold the process layer's live view of composition load and availability that a routing decision needs. Prescribing either past that boundary embeds a guess made with the least available information into a plan meant to reduce ambiguity — the executing spawn or the process layer then has to first detect and unwind that guess before they can apply the fuller information they actually have."
  see-also: task-describes-output-not-implementation, concern-names-work-not-role

- id: batch-wide-refactors-by-blast-radius
  rule: "When a task's mechanical change fans out widely enough that no single vertical slice can land it as a demoable, working unit, decompose it as expand (add the new form alongside the old) then migrate in batches sized by blast radius, each batch blocked by the expand, then contract (remove the old form), blocked by every migrate batch. Do not force this shape into an ordinary vertical-slice task, and do not leave it as one oversized task."
  condition: "When decomposing a capability whose core change is a single mechanical edit with a codebase-wide blast radius, rather than a feature built from cooperating vertical slices."
  reason: "sequence-by-output-dependency assumes each task's output is a discrete deliverable other tasks consume — that model breaks when the risk isn't sequencing between distinct outputs but a single edit large enough that no task boundary keeps the codebase working mid-change."
  see-also: sequence-by-output-dependency

- id: no-placeholder-content-in-task-steps
  rule: "A task's content must be the actual material an implementer needs, not a placeholder standing in for it. Reject and rewrite text like 'add appropriate error handling,' 'handle edge cases,' 'similar to Task N' (without repeating what that means here), or a reference to a type/function/method not defined anywhere in the plan."
  condition: "Writing or reviewing any task's steps or descriptions in a plan or decomposition."
  reason: "A vague placeholder phrase reads as if it specifies something while actually deferring the real decision to whoever executes it — the same gap task-is-actionable-without-planning guards against for a task as a whole, applied here to the prose habit of writing confident-sounding but hollow instructions within an otherwise-actionable task. Generating this kind of plausible-but-empty text is a natural failure mode when drafting a plan, since it pattern-matches to what a real instruction looks like."
  see-also: task-is-actionable-without-planning

- id: verify-interface-consistency-across-tasks
  rule: "Before finalizing a decomposition, check that any name, signature, or type one task defines and a later task depends on is used identically across both — same function or type name, same parameters, same return shape. A mismatch is a plan defect, not a detail to reconcile during implementation."
  condition: "Multiple tasks in one decomposition depend on interfaces (functions, types, data shapes) defined by an earlier task in the same decomposition."
  reason: "Tasks are drafted in sequence but read independently by whoever executes them — a name that drifts between the task that defines it and the task that depends on it is invisible within either task read alone, and only surfaces once the dependent task's implementer discovers the mismatch, after commitment already happened."

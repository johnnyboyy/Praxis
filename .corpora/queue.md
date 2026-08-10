# Self-host task queue

The ai-engines house developing itself. Each task is driven through the praxis front door
(`root_tree` → `frame`/`route` → compose → spawn → handoff). Status transitions via
`corpus.py queue-set-status`; validate with `corpus.py lint-queue`.

```yaml
capability: self-host the ai-engines house (praxis + corpora developing themselves)
area: praxis + corpora architecture
status: complete
created: 2026-08-05
updated: 2026-08-05

tasks:
  - id: t-01
    title: "Framing Stage 2 — the raw-ask front door + project engine-slot resolution"
    description: "One entry that takes a natural-language ask (no targets/uow decided yet), runs frame+route, and prints the frame + size_signals + assumptions, degrading cleanly when no targets are guessed. Plus: resolve a project's OWN engine slot automatically so frame/route don't need --engine-plugins passed by hand (the ergonomics gap the FAMOUS + self-host trials both hit)."
    context: "praxis/scripts/frame.py, route.py, phases/framing.md. Stage 1 (size_floor/size_signals/assumptions) already landed."
    status: complete
    blocked-by: []
    parallel-ok: true
    concern: implementation
    judgment: settled
    notes: "Highest leverage — the user-facing front door and the first thing every other task routes through."

  - id: t-02
    title: "Move compose-spawn-prompt to praxis (capability sort)"
    description: "compose-spawn-prompt is a process verb still living in corpus.py; the capability sort flagged it as praxis-side. Move the spawn-prompt composition to praxis (invoking the engine's compose for the domain set), leaving corpora as pure judgment."
    context: "corpora/scripts/corpus.py cmd_compose_spawn_prompt; praxis routing/framing."
    status: complete
    blocked-by: []
    parallel-ok: true
    concern: implementation
    judgment: settled
    notes: "A clean loose-end from the process/judgment split."

  - id: t-03
    title: "Orchestration-spine migration: bootstrap + general-operation into praxis"
    description: "corpora/processes/bootstrap.md and general-operation.md are the deliberately-unbuilt session/loop conductors still in corpora (the 'I am the orchestrator' spine). Migrate their process into praxis phases. This ALSO carries the legacy corpora/processes/ UI/UX cluster retirement (ui-library-*/ux-library-*/screenshot-library-*/design-decision-review docs) — those get displaced naturally as their bootstrap/operation references move to the uiux plugin phases."
    context: "corpora/processes/bootstrap.md, general-operation.md; the legacy UI/UX process docs woven into them; uiux plugin phases already exist."
    status: complete
    blocked-by: []
    parallel-ok: false
    concern: architecture
    judgment: open
    notes: "Big design item. Sequence the UI/UX-doc retirement inside this, not before it (operator decision 2026-08-05)."

  - id: t-04
    title: "Parent interop root + bidirectional cross-root handoff"
    description: "The mechanism for two roots that legitimately span (e.g. FAMOUS app vs admin) to communicate: a symmetric interop root governing only the boundary, plus a bidirectional handoff addressed to a root with a return path. root_tree already flags missing interop roots."
    context: "praxis/scripts/root_tree.py (interop), handoff.py, phases/interop.md."
    status: complete
    blocked-by: []
    parallel-ok: true
    concern: architecture
    judgment: open
    notes: "The self-host root-shape decision (single vs per-concern roots) may make this concrete."

  - id: t-05
    title: "Backward spine + framing Stage 3 (persisted frame artifact)"
    description: "A backward spine: deferred-decisions keep a trace rather than deletion; reopening a closed chunk / looping back is currently fragile. Framing Stage 3 rides with it — a frame becomes a small persisted artifact (assumptions relayed + size + route taken) so a redirect leaves a trace and a reopened task sees what was assumed."
    context: "praxis chunk_ledger.py, frame.py; deferred_queue (uiux). Builds on framing Stage 1/2."
    status: complete
    blocked-by: [t-01]
    parallel-ok: true
    concern: architecture
    judgment: open
    notes: ""

  - id: t-06
    title: "Finer generic-vs-design split of the routing domain"
    description: "The routing domain (in plugins/routing) still bundles generic routing judgment with design-specific routing — a full-domain-decomposition-audit item. Split it so the generic half is engine-agnostic and any design-specific routing lives with the design concern."
    context: "plugins/routing/corpora/domains/routing.md."
    status: complete
    blocked-by: []
    parallel-ok: true
    concern: judgment
    judgment: open
    notes: "Lowest priority; an audit-driven refinement."

open-questions:
not-yet-specified:
out-of-scope:
```












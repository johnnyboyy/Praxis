---
description: Capture a workflow from a lived session, an external source, or a freeform idea into a validated workflow pack — or conclude honestly that it is a skill, not a workflow.
disable-model-invocation: true
---

The process to forge is: $ARGUMENTS

Praxis is process-agnostic: it knows units, phases, typed edges, gates, the lease, and the
journal, and nothing about any particular practice (`docs/workflow-packs.md`). A **workflow pack**
is how a practice becomes vocabulary the engine can referee. This skill is how one gets forged —
mined honestly from where the process actually lives, checked deterministically before it is
trusted, then run through one real unit before it is called done.

## 1. INTAKE — pick the mode that matches where the process lives

**(a) LIVED** — mine the current session or recent work for the process actually run.
- List the moves that happened, in order, and what each one produced.
- For each transition between moves, state what actually happened to the prior artifact: was it
  created fresh (no predecessor), carried forward and perturbed in place, or dropped and rebuilt
  from a spec derived from it? That empirical answer — not a guess about what edge type "sounds
  right" — is what picks `create` / `carry` / `extract` (`workflow.py`'s `EdgeType`, `GATES`).
- Note what verification actually occurred at each transition (a test run, a read-back, nothing).
  A step with no real verification is not a gate — don't invent one it didn't have.

**(b) SOURCE** — mine an external methodology doc or article for its moves and transitions.
- Fetch the actual text. If it cannot be retrieved (fetch error, paywall, bot-block, a stub or
  summary standing in for the real page), **stop and report the failure** — do not reconstruct
  the source from training-data recall or from a search-result snippet and cite it as if it were
  read. This is the same hard-stop discipline `skills/read` in corpora runs for the same reason:
  a citation to a source that was never actually read is worse than no citation, because it reads
  as more grounded than it is. Carry that epistemic here as prose; do not import corpora's queue,
  its CLI, or any dependency on it — the forge reads sources for **process** (moves and
  transitions), corpora mines sources for **judgment** (rules). Keep the two separate: if a claim
  in the source is really a rule of thumb rather than a move the process makes, it does not belong
  in this pack — name it in your close notes as considered-and-killed, the way a corpora reading
  note records a kill.
- Mine for moves-and-transitions the way LIVED does, sourced from the text instead of the session.

**(c) FREEFORM** — an idea with no session and no source yet, interviewed into shape.
- Reuse the `interviewing` discipline `skills/orchestrate/SKILL.md` runs for its own INTAKE: ask
  **one question at a time**, wait for the answer before the next; when there is one clear
  direction, **name it and ask for confirmation** rather than manufacturing a choice; frame each
  question so the answer is cheap. Frontier the moves, their products, and their verification
  points the same way orchestrate frontiers open decisions — loop until settled, not until you
  run out of questions to ask.

## 2. THE VERDICT — is this even a workflow?

A process earns a workflow pack only if it has **at least two distinct phases with typed artifact
transitions between them, and at least one gate that can genuinely refuse to advance.** If the
mined moves don't clear that bar — a checklist with no artifact handed from step to step, a
cadence or ceremony (a standup, a review pass, a naming convention), a single-move practice — it
is a **skill**, not a workflow, and drafting a skill instead is the legitimate, honest outcome
here. Say so plainly; do not force a two-phase shape onto something that is one move wearing a
process costume.

This has precedent in this very repo: `planner` was built as engine vocabulary (phases, a
frontier-check workflow) and never once got driven that way — the form that actually worked was
prose discipline plus an artifact (`frontier.md`), owned directly by the `orchestrate` skill
(commit `5c626e8`, "planner dissolves into the orchestrate skill"). A mechanized workflow that
nothing exercises is worse than an honest skill; don't repeat that shape when the verdict already
points at a skill.

**Hybrids split.** If part of the mined process really is a typed multi-phase workflow and part is
a surrounding ceremony (a review cadence, a way of writing up notes), split them: forge the small
true workflow as a pack, and draft the ceremony as a separate skill. Don't force the ceremony into
a phase just to keep everything in one artifact.

If the verdict is "skill, not workflow" — stop here, draft the skill (a normal `SKILL.md`, no
`workflow.py` vocabulary involved), and report that conclusion. Everything below is for the
workflow case.

## 3. AUTHOR — write the pack module

Follow `plugins/coding-process/coding_process_plugin.py` (a workflow with no fact edges, all
`carry`) and `plugins/rebuild/rebuild_plugin.py` (a two-phase `extract` seam with a `verifiers`
factory) as templates. A pack module needs:

- `PRAXIS_PLUGIN = True` at module level (the discovery marker; see `scripts/plugin_registry.py`).
- `Phase(...)` objects for each move (`name`, `stance`, `intent`, `produces`, optionally
  `delivery`).
- `Workflow(name=..., phases=[...], edges=[...])` — each edge a 4- or 5-tuple
  `(from_phase, to_phase, when, edge_type[, predicate])`. `when` is one of `workflow.WHENS`
  (`pass`/`fail`/`always`/`feeds`/`fact`); a `fact` edge's 5th element must be a callable predicate
  over the evidence dict (`registry.validate_workflow` enforces this). `edge_type` decides the
  gate that runs at that seam (`workflow.GATES`): `create`→does-it, `carry`→regression,
  `extract`→coverage-diff.
- Optionally a `verifiers` factory (`(root) -> {gate-name: Verifier}`) on the `Workflow`, when the
  pack needs its own gate form instead of the default.
- Either a `make(root)` returning a contributor object with `phases()`/`workflows()` (preferred —
  matches both templates and lets the pack also carry `contribute()`/`hooks()`/`surface()`), or
  bare module-level `Phase`/`Workflow` objects for a minimal pack.

**Choose the home**, by maturity (`docs/workflow-packs.md`'s three homes):
1. **project-local** — `<root>/.praxis/plugins/` — default for a first forge; zero ceremony,
   scoped to one repo.
2. **peer repo** — its own life outside this engine, discovered via `plugins_search_paths` or the
   global layer (the corpora/uiux pattern).
3. **bundled** — praxis's own `plugins/` — reserved for process vocabulary with no life outside
   the engine itself; rare, and not the default for a first forge.

## 4. GATE — run the deterministic check

```
python3 scripts/forge_check.py <module_path> [--workflow NAME] [--root DIR] [--facts JSON]
```

It validates every candidate phase/workflow against the engine's own rules
(`registry.validate_phase`/`validate_workflow`), then dry-walks each workflow with stub evidence
through `phase_walk` in a throwaway root, reporting: whether the walk reached a genuine terminal,
which fail edges were never exercised (informational — the stub always "passes"), any unreachable
phases, and any fact-gated route it couldn't exercise without `--facts`. It exits 0 only when
validation is clean and every walked workflow reached a terminal.

**A red check is a defect in the pack to fix, never to talk past.** Paste the JSON report into
your close notes — both when it's green and when you had to iterate to get there.

## 5. REGISTER + TRIAL

- **Register** the pack: either run `skills/register-plugins` (project-local and bundled homes
  are auto-discovered by their `PRAXIS_PLUGIN` marker), or for a peer-repo home, add it to the
  root's `plugins_search_paths` and register it the same way.
- **Trial it on one real unit.** Route a genuine unit of work through the new workflow via
  `orchestrate` (or `inline` for a single-phase check) and let it walk the gates for real. Its
  `phase_fit` self-reports (`loose`/`none` evidence on `record_phase`) are the first revision
  signal — a phase that keeps getting reported as a loose fit is telling you the pack's shape is
  wrong, not that the unit is unusual.
- **Probation.** A workflow that no real unit adopts within a few plans is a pack that should not
  have survived — cite `BACKLOG.md`'s "Probation: tdd-unit usage" entry as precedent for the
  standard: if the journal shows units choosing something else every time, retire the unused pack
  rather than let dead vocabulary accumulate (it can always be re-forged the day a consumer
  actually demands it).

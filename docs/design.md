# Praxis design — phases, typed edges, and workflows

Praxis runs a **unit of work through a workflow** — a graph of **phases** — rather than a single
dispatch. This is the conceptual model: the part that does not fall out of the code. For what's
wired today, read the code.

---

## Conceptual model

### Primitives

**Phase** — one atomic move an agent (or a deterministic step) makes.
```
Phase = { name, stance, intent, produces, delivery, run }
  produces : the result contract — what "done" looks like
  delivery : inline | spawn | deterministic
  run      : a Callable, used only when delivery == "deterministic"
```

**Workflow** — a graph of phases with typed, possibly-conditional edges.
```
Workflow = { name, phases[], edges[(from,to,when,edge_type[,predicate])], verifiers }
  when      : pass | fail | always | feeds | fact
  verifiers : optional factory (root) -> {gate-name: Verifier} — the gate's form
              travels with the workflow that needs it
```

There is deliberately **no phase-intrinsic `gate` field** — the preservation gate is a property of
the incoming edge, not the phase (see below).

### The context boundary is a property of the EDGE, not the phase

Firmest seam in the system. An artifact in context is an **attractor**: instructions cannot reliably
override it. So the edge into a phase is typed by what that phase does to the prior artifact, and the
edge type — not the phase — selects the preservation gate:

| edge    | did to the original | what's in context               | preservation gate | question        |
|---------|---------------------|---------------------------------|-------------------|-----------------|
| create  | none existed        | the spec (prescriptive)         | `does-it`         | *does it?*      |
| carry   | perturbs it         | the original (it should anchor) | `regression`      | *didn't break?* |
| extract | rebuilds it         | the spec only (original dropped)  | `coverage-diff`   | *covered it?*   |

**Every edge carries a preservation gate; its form is a function of what the edge did to the
original.** Coverage-diff is not generic — it is the compensating control specific to the `extract`
edge, for having dropped the original.

### The rebuild triple (the `extract` edge, expanded)

A hard seam is never one phase:
```
extract       original IN — inventory / classify / define-interface → produces the spec (no synthesis)
  ── drop the original ──
synthesize    spec ONLY     — rebuild to the interface, free of the attractor
coverage-diff both IN     — TWO directions: losslessness (spec covered?) + completeness (spec met?)
```
Who may hold the original is decided by what the phase emits: **restructures it → no; analyzes it →
yes; compares it → both.** `plan` is itself an extraction (request → units/edges = the spec), so
planning and re-architecture are the same move at different altitudes. `coverage-diff` is
two-input — it consumes *both* `extract`'s spec and `synthesize`'s artifact; the linear single-slot
carry cannot feed it, which is why the runner threads a named-output map (below).

### Two altitudes

**Orchestration** (across units) — verification is DEFERRED to a single barrier. The engine does
not run this loop; the orchestrator (the model, via the orchestrate skill) does, over the
register_plan / next_handoff / record_receipt surface:
```
plan → fan-out (units run isolated, in parallel) → ┃BARRIER┃ → verify(full suite, once)
                                                              ├ fail → fix units → re-verify
                                                              └ pass → close
```
**Unit** (within a unit) — a phase-walked workflow, e.g. TDD:
```
write-tests → implement → refactor → test-cleanup
```
Two verification scopes: **local** (a unit's own new tests, fast, inside the unit workflow) and
**global** (the full suite, once, at the barrier).

### Phase-fit discovery: grow the phase set from strain

Every phase exit reports `phase_fit` (clean|loose|none) + `suggested` (what the agent would call
what it actually did) — the same mechanism as task-kind fit, lifted to process. `loose`/`none`
writes a `phase.gap`; `/praxis:report gaps` surfaces the recurring ones, and promoting one is an
operator act: add the phase to a plugin. Seed the phase set small; grow it from where real work
strains.

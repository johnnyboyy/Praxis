# Praxis backlog — parked ideas

Ideas deliberately set aside with their rationale, so their place can be rediscovered rather than
lost. Not a task queue; each entry states what it was, why it's parked, and a candidate home.

## Anti-mean anchor (retired from corpora 2026-08-11)

**What it was.** A composed Contribution corpora injected when the situation's stance was
divergent, telling the agent to resist the default/expected answer. The text:

> The default, expected answer is a starting point to push against, not a target. Treat the
> obvious solution as the mean to differentiate from: interrogate it, and only settle there if it
> still wins after you have tried to beat it.

**Why parked.** convergent/divergent stance originally existed to stop an implementation from
marrying its own design within one context. praxis now owns that seam structurally (fresh context
across a phase edge; the preservation boundary is a property of the edge). With that gone, every
corpora domain is convergent (a guardrail to follow), so `posture`/stance had no real job left in
the composer — and the anti-mean anchor was its only residual value. It's a *stance* concern, and
stance now lives at the praxis phase/edge level, so it does not belong in the judgment composer.

**Candidate home.** A genuinely divergent PHASE's framing — when praxis (or the uiux design flow)
runs a divergent design phase, that phase carries "resist the mean," injected because of where you
are in the graph, not because a domain asked for it.

**Consequence to unwind when re-homing.** uiux design tasks previously received anti-mean via
corpora and lose it until it is re-homed to a phase.

## Worktree isolation for parallel orchestrate units (queued 2026-08-11)

**What.** When `orchestrate` fans out multiple units in parallel — especially rebuild-triple pairs
like composer + its tests — each subagent should run in its own git worktree, so they cannot see
or edit each other's files.

**Why.** Parallel agents sharing one working tree can (a) clash by editing the same files, (b)
collude — converge on each other rather than on the barrier (the "tail-chase": tests bend to what
the composer does, composer bends to whatever tests exist, and a shared misreading of the barrier
passes green), or (c) get confused by half-written peer files mid-run. Worktrees enforce the
rebuild-triple's independence structurally: synthesize and coverage-diff in isolation, converge
only at the barrier.

**Candidate home.** The `orchestrate` skill / the Agent dispatch step. The Agent tool already
supports `isolation: "worktree"` — simplest first cut is: dispatch parallel units with
`isolation: "worktree"`, then reconcile at the barrier. Open questions: how per-unit worktrees
merge back, and how the praxis edit gate + journal (already per-root) interact with a worktree per
unit. Observed live in the corpora Lap-1 build, where cx-composer and cx-tests saw each other and
converged (the pin held, but it was luck-adjacent).

## Corpora owns domain discovery + validation (queued 2026-08-11)

**What.** Corpora should discover a root's domains the same way praxis's `plugin_registry`
discovers plugins — generically, from registered contributors' `domains_dir` + the project pool —
and validate them AT DISCOVERY (fail-soft: surface a malformed domain with its file + reason, never
raise). A judgment plugin's whole contract is "ship a `domains_dir`"; it imports corpora zero times.

**Why.** The per-plugin schema-lint tests (planner/general/coding-stack) reached into corpora's
parser to validate their own domain files — a leaky coupling that broke the moment corpora moved to
a peer. Removing it (done in Lap-1 hygiene) leaves a gap: nothing automatically checks that a
plugin's shipped domains are well-formed. That guard belongs to corpora's discovery, exercised once
by a corpora-side test over a fixture root — the single generic validator, not N per-plugin copies
that drift from the real parser.

**Candidate shape.** `corpora.discover(root)` collects malformed-domain problems alongside the
pool; a `validate_domains(root) -> problems` surface; one corpora test over a fixture root with a
couple of plugins registered. Possibly unify by having `discover` reuse praxis's marker/layered
discovery for locating `domains_dir`s. Land with Lap 2 (ratify/retrospective), which is corpora's
next build.

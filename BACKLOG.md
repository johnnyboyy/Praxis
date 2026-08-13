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

**Status (2026-08-13).** The Situation stance channel was deleted in the vocabulary trims
(`42b192b`) — `Phase.stance` survives as metadata on phase definitions, so the candidate home
stands: a divergent phase's framing, injected by a contributor branching on `phase_name`.

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

**Status (2026-08-13).** Dispatch moved to the pull model (`a7c1a13`): executors read their own
payloads via `read_handoff`/`next_phase`. The candidate home is unchanged — the orchestrate
skill's dispatch step is where `isolation: "worktree"` gets requested.

## OS-level capability sandboxing for the rebuild seam (queued 2026-08-12)

**What.** Rebuild isolation (`isolation.py`) is best-effort: a spec-only seeded worktree
(attractor-reduction), a copy-detection tripwire (`scan_tripwire`, a detector), and dependency
hygiene (`dep_hygiene_ok`). What it explicitly does NOT do is make the original *unreadable*: a
`claude -p` synth subagent can still `Read` the original by absolute path. The residual risk — a
faithful copy through an absolute-path read — is named, not closed.

**Why parked.** Real capability isolation needs OS mechanism: a container, a mount namespace, or a
read-only bind mount that excludes the original tree, plus (optionally) moving the original aside
for the run so a naive absolute-path read fails. That is heavy machinery relative to this lap; the
critique's pragmatic honest bar is best-effort isolation + a tripwire + strong held-out adequacy
(the preservation gate), which at least guarantees a copy is behavior-preserving even if it did not escape the
attractor. So OS sandboxing is deferred.

**Candidate home.** The Agent/subagent dispatch step (where the synth runs), paired with the
worktree-isolation entry above.

**Status (B lap done, 2026-08-12).** Tool-log capture is now built: the `tripwire_log.sh`
PreToolUse hook logs each dispatched subagent's tool call keyed on its `agent_id`, and
`isolation.read_tool_log` replays the synth subagent's reads into the tripwire gate as
`tool_log`. The tripwire covers Read-tool reads (`Read`/`Grep`/`Glob`) plus shell reads
(`cat`/`sed`/`head`/`tail`/`less`/`grep`/`find`) seen in `Bash` commands. **The residual, still
open here:** a raw filesystem syscall (e.g. Python `open()`) bypasses the PreToolUse hook and is
NOT captured — only the OS-level sandboxing below closes it. Capture is also only active when the
hook is installed in settings (`hooks/hooks.json`; the script itself moved to
`plugins/rebuild/hooks/tripwire_log.sh` with the rebuild pack, `ce149bd`).

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
couple of plugins registered.

**Status (2026-08-13).** Half the premise moved: corpora's discovery is now driven by its own
`sources` config list (`91fd1d2`) and plugin `domains_dir`s no longer exist (`8c5d5f3`) — the
domains live in the peer bucket. What remains wanted is `validate_domains` over the bucket
collections + the project pool, fail-soft at discovery, exactly as stated above.

## Mutation scope = plan blast radius (queued 2026-08-12 — SUPERSEDED 2026-08-13)

**Superseded:** mutation verifiers were evicted from core in the engine cut (`ce149bd`); the
barrier's form is plugin/root content now. The scoping insight below transfers to whoever builds
a mutation adequacy pack — kept for that reader.

The mutation adequacy signal's THRESHOLD is an absolute policy constant, but its SCOPE should be
the files the plan/units actually changed (the blast radius), not the whole repo. Mutation is
expensive (re-runs the suite once per injected mutant), so scoping it to changed code keeps the
final barrier tractable on a large codebase. Wire: the mutation barrier verifier targets only the
plan's touched paths (from the journal/plan), not the entire tree. Applies to the mutation barrier
and the extract-seam adequacy gate. (Surfaced from the "would an architecture shift be blocked?"
question — answer: no, mutation measures TEST strength, not churn; but scope it to the blast radius.)

## Refinements from an independent design review (2026-08-12 — reconciled 2026-08-13)

Five points from an outside review of the spine. The skeleton (contract-first, cheap inner-loop
gates, expensive outer-loop gate, close only through passed gates) was affirmed. Reconciliation
after the cuts: **1–3 LANDED** in `skills/orchestrate` (the BARRIER step carries
integration-contract tests and the append-only rule; the FINAL BARRIER step carries the
single-fixer-with-global-context rule); **4 LANDED** as the `escalate_unit` engine terminal
(escalated bucket, close refused); **5 superseded** with mutation's eviction (see the
superseded entry above). Original points kept below for their reasoning.

1. **Integration-contract tests are an explicit BARRIER deliverable** (lands in: planner). Per-unit
   acceptance tests can all pass while units disagree about interfaces / shared state / ordering.
   The final barrier only catches this if the up-front barrier includes genuine cross-unit
   integration tests. Make "author integration contract tests" a named planner/barrier deliverable,
   not something hoped to fall out of the full suite. (Complements planner's
   verify-interface-consistency-across-tasks + open-questions-are-explicit.)
2. **Cross-cutting fixes owned by a dedicated fixer with GLOBAL context** (lands in: B fix loop). A
   mutation survivor / integration failure often implicates two units jointly; re-dispatching to the
   original isolated implementers (each lacking the whole picture) works worse than one fixer agent
   with global context. Decide fix ownership up front.
3. **Barrier is append-only during implementation** (lands in: planner + B). Implementers may
   propose ADDITIONS (never modifications) when they discover unhandled edge cases, subject to
   planner approval. Preserves the contract property without freezing the planner's blind spots
   (acceptance tests written before any implementation tend to under-specify edges).
4. **Explicit escalation-to-human terminal on fix-loop exhaustion** (lands in: B / engine). Today
   the bounded fix loop's exhaustion is prose (orchestrate ESCALATE), not an engine state — make it
   a real terminal so the workflow can't stall silently.
5. **Per-unit mutation SMOKE on the diff** (lands in: the mutation barrier + the mutation-scope note).
   Coverage invites Goodharting — agents write line-touching, assertion-free tests to clear the
   gate. Mutation is the defense but runs once at the end, so gamed coverage survives all of fan-out
   before being caught. A coarse, diff-scoped per-unit mutation smoke check catches hollow tests
   during fan-out. Pairs with "mutation scope = plan blast radius."

## record_phase MCP evidence arg accepts only a JSON string (2026-08-12)

The `record_phase` MCP tool types `evidence` as a string it `json.loads`es, but the harness
serializes a JSON object argument as a dict (rejected by the string type) and a quoted string as a
double-encoded string (loads to a str, not an object). Small usability fix: accept a dict OR a JSON
string for `evidence` (coerce dict-or-string), like other tools do. Found driving the live rebuild
walk; the conduct/phase_walk functions themselves take a dict fine. **Reproduced live
2026-08-13** driving the audit-and-cut trial walk (the harness hands the tool a dict; the tool
rejects it) — still open, still the same one-line coercion fix.

## Probation: tdd-unit usage (queued 2026-08-13)

`coding-process`'s tdd-unit workflow has a zero runtime record (no workflow-driven unit
has ever chosen it). It survives the 2026-08 cuts on cheapness (45 lines) and on being
the seed's only alternative to build-verify. At the next audit, decide by the journal:
if real workflow-driven units exist and none picked tdd-unit, delete it the way stance
and agent-choice went — the vocabulary can be re-added the day a consumer demands it.

# praxis — the process / orchestration core

Praxis is the **process / orchestration layer**: routing, phases, workflows, the framing step, and the
hard "one unit-of-work = one spawn = one handoff" rule.

## The plugin-slot model

Praxis exposes SLOTS; an engine's *contribution* fills them:

- **`engine/plugins/`** — an engine capabilities manifest declares `capability → verb + argv shape`
  and a `cli` (where to invoke). `scripts/engine.py` discovers whatever manifest is registered,
  resolves a capability name against it, builds the argv, and invokes the declared CLI. A second
  engine is just a second manifest; nothing in praxis enumerates or names any engine.
- **`handoff/plugins/`** — a handoff plugin manifest declares the `frontmatter`/`sections` an engine
  expects on every handoff. `scripts/handoff.py` composes the schema from `handoff/base.json` + all
  registered plugins and validates that every registered plugin's required fields are present — praxis
  enforcing presence without knowing what any field means. A plugin may not override a base field.
- **`phases/`** — praxis-core carries only universal phases (`framing`, `routing`, `interop`,
  `session`). An engine contributes its own phases alongside its manifests.

"Moving an engine in" = a project snapshot-imports the engine's contribution (its manifests, its
scripts, its phases) into these slots — the same snapshot-import model an engine's own content layer
uses. The shipped praxis has empty slots; a project that uses an engine imports that engine's
contribution into them.

## The invocation contract — how praxis calls an engine

A phase or sequence script invokes the engine for a *capability*, generically:

- `scripts/engine.py`: `discover_manifest` → `load_manifest` (resolves the `cli`) → `build_argv`
  (globals before the verb, positionals bare, booleans as a lone flag, required params enforced) →
  `invoke`. `resolve(manifest, capability, params)` is the single entry point.
- **compose** is not special — it is the read capability `frame` interprets as JSON (the domain set
  for a unit-of-work) rather than branching on pass/fail. Praxis owns the *unit-of-work decision*
  (routing judgment); the engine owns turning it into a domain set.

## The deterministic-first method (why the scripts exist)

Whatever can be a script should be a script — scripts are testable and can't be wrong the way
inference can. Each process is sorted into its **deterministic** surface (which root, what
composition, what drifted) → a praxis script with tests; and its **judgment** surface (size this,
weigh that) → a thin phase that runs the scripts for facts, then invokes the engine only where
judgment actually remains.

### Phase schema (every phase file declares, in prose)

- **entry condition** — the task-state test that selects this phase
- **stance** — convergent / divergent / none
- **invocations** — which capability it invokes (named generically), with stance + scope; omit for a
  purely mechanical phase
- **deterministic facts** — the scripts it runs first, whose output is fact not judgment
- **artifact** — the concrete deliverable it hands forward
- **surfaced/lacking** — what a run reports as still missing (drives re-routing)

## Praxis-core components

- `scripts/root_tree.py` (+ tests) — deterministic root-tree resolver (`tree`/`resolve`/`span`/
  `interop`). The "fact prior to everything": which root(s) a task belongs to. A root is a directory
  carrying `.praxis/config.md` (legacy `praxis/config.md` recognized); the marker set is configurable so an engine's own config marker can be
  recognized without a code change.
- `scripts/frame.py` (+ tests) — the fact bundle for a task: governing root, span→decompose verdict,
  and the composition (via the registered engine's `compose`). Degrades when no engine is registered.
- `scripts/engine.py` (+ tests) — the generic plugin loader + capability resolver (the entire
  engine-coupling surface, all of it data-driven).
- `scripts/handoff.py` (+ tests) — the handoff primitive: schema composition, template, validate, and
  native **close** (delete, or archive under `<handoffs-dir>/archive/` when the root's
  the root config sets `debug: yes`). The whole create→validate→close lifecycle is praxis-owned.
- `scripts/chunk_ledger.py` (+ tests) — unit-of-work accounting. Praxis reads/writes the ledger at
  `<root>/.praxis/chunks/<workstream>.md` natively; the only engine touch is `compose` (the
  `domains-composed` ground truth). Enforces the chunk-done-before-handoff-close gate + the
  handoff-exists precondition + the composition reconciliation.
- `scripts/route.py` (+ tests) — the routing fact-sheet: `frame` plus execution-shape signals
  (spans→isolate; resume-vs-new via a native ledger lookup), plus the unit's lease when declared.
- `scripts/units.py` (+ tests) — the lease declarations per unit of work (`<root>/.praxis/units.md`):
  the edit surface that unit may write and the output whose delivery ends it. Fail-open — an
  undeclared unit restricts nothing. The unit *names* are engine vocabulary; the lease is process
  metadata, so it lives praxis-side like `config.md`.
- `scripts/churn.py` (+ tests) — a generic git-churn utility (no engine coupling), offered for phases
  that scope by recent change.
- `phases/framing.md`, `phases/routing.md`, `phases/interop.md`, `phases/session.md` — the universal
  judgment phases on top of the scripts above; `session` is the loop conductor that iterates the
  front door over a queued task source and halts on any non-`complete` handoff status.

Full suite: `python3 -m unittest discover -s praxis/tests`.

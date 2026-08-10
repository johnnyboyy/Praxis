# House notes — separation decisions & open judgment forks

This house holds the idealized, fully-separated form of two skills:

- **`praxis/`** — the process/orchestration core, **pure**: it names no engine, knows no engine's
  location, and names no engine's verbs. It ships with empty plugin slots and degrades when nothing is
  registered. (See `praxis/BOUNDARY.md`.)
- **`corpora/`** — one judgment engine. Its praxis-facing contribution (the manifests, scripts, and
  phases that register it into praxis) lives under **`corpora/praxis-plugin/`**.

The canonical, still-running repo is `~/jdev/corpora` — untouched. This house is a fresh assembly.

---

## The engine binding — how it flows now (the crux)

Before separation, praxis hardcoded `DEFAULT_CORPUS_PY = parents[2]/corpora/scripts/corpus.py` and a
fixed path to `engine/plugins/corpora.json`. Both are gone. The binding now flows entirely from data:

1. An engine registers by dropping a **capabilities manifest** into praxis's `engine/plugins/` slot.
2. That manifest carries a **`cli`** block — `{"command": "python3", "entry": "<path>"}` — whose
   entry is resolved **relative to the manifest file**. So the manifest declares where its own engine
   CLI is; praxis encodes no path.
3. `engine.load_registered(slot)` discovers whichever manifest is present and resolves its `cli` to an
   absolute command. `engine.resolve(manifest, capability, params)` maps the capability name → verb +
   argv (from the manifest) and invokes that command. `frame.engine_compose` is just
   `resolve(manifest, "compose", …)`.
4. Empty slot → `load_registered` returns `None` → callers degrade ("no engine registered").

Corpora's manifest (`corpora/praxis-plugin/engine/plugins/corpora.json`) now declares
`cli.entry = ../../../scripts/corpus.py` (→ `corpora/scripts/corpus.py`), so the location travels with
the contribution. A project "moves corpora in" by snapshot-importing the contribution into praxis's
slots; the import records the concrete corpus.py path (the integration test simulates this by writing
the manifest into a slot with an absolute `entry`).

---

## What stays praxis-core vs moves to corpora

- **Praxis-core (`praxis/scripts`)**: `root_tree`, `frame`, `engine`, `handoff`, `chunk_ledger`,
  `route`, `churn`. Phases: `framing`, `routing`, `interop`. Plus `handoff/base.json` and the two
  EMPTY slots.
- **Corpora's contribution (`corpora/praxis-plugin/`)**: `engine/plugins/corpora.json`,
  `handoff/plugins/corpora.json`; scripts `domain_import`, `ratify_writeback`, `kill_graduation`,
  `domain_migrate`, `library_state` (+ `_engine_link` linking them to praxis-core's resolver); the
  corpora-specific phases; the corpora-mimicking test stub, the moved sequence-script tests, and the
  integration test.

### Per-phase stay/move calls (the ones the task flagged for individual assessment)

- **`debugging.md` → MOVE.** Names the corpora `debugging` domain and defers every step's judgment to
  it. Corpora's contribution.
- **`runtime-verification.md` → MOVE.** Names the corpora `testing` domain and specific corpora
  principle ids. Corpora's contribution.
- **`testing.md` → MOVE.** Built around the corpora `testing` domain and three corpora processes.
  Corpora's contribution.

  (All three name corpora domains, so by the stated rule they are corpora's contribution, not core.)

### Two disposition calls the task left unstated

- **`library_state.py` → MOVED to corpora.** Not in either explicit list, but it is the deterministic
  backing for the `library-init`/`library-sync` phases (which ARE in the move list) and is entirely
  about corpora's UI/UX/screenshot libraries and `corpora/…` paths. It moved with its phases.
- **`churn.py` → KEPT core.** Not in either list; it is a pure git utility with zero engine coupling,
  so it stays as a generic praxis-core primitive. Its *consumer* `architecture-scan.md` moved to
  corpora; churn is offered generically.

---

## Open judgment fork — praxis-native config & state paths (recorded per instruction)

To make praxis-core name nothing corpora, praxis now uses its **own** markers and state locations:

- root marker: `praxis/config.md` (was `corpora/config.md`);
- chunk ledger: `<root>/praxis/chunks/…` (was `corpora/chunks`);
- handoffs + debug flag: `<root>/praxis/handoffs/…`, `<root>/praxis/config.md` (were `corpora/…`).

**The fork:** the pre-split praxis deliberately "ran off `corpora/config.md` for now" so it could drive
existing corpora projects that carry only that marker. Making praxis native means a project that uses
both now carries **both** a `praxis/config.md` (praxis's root marker) and its `corpora/` content (the
engine's own layout) — which is exactly the "project using both" shape the plugin model implies, and
what the integration fixture demonstrates.

**Recommendation:** keep praxis native (done here) — it is what makes the boundary real. If backward
compatibility with marker-only corpora projects is ever needed, add the engine's config marker to the
per-project `--marker` set rather than re-hardcoding it in praxis; `root_tree` already accepts extra
markers as data, so this is a project-config change, not a code change.

Retained from the pre-split notes as still-open, engine-side, operator-gated (unchanged by this
separation): the orchestration-spine extraction (`session`/`bootstrap` loop conductors) remains
deliberately unbuilt (update 2026-08-05: the `session` loop conductor is now built as
`praxis/phases/session.md` + `chunk_ledger next`); and retiring the engine's own competing "I am the
orchestrator" framing is an edit to the engine, out of scope for this additive house.

---

## North Star — harness incorporation (recorded 2026-08-05, unscheduled)

Praxis/corpora is, functionally, a meta-harness built in userspace: dispatch (the front door),
context assembly (`spawn_prompt`/compose), middleware (the frame-before-edit hook), transactional
state (chunk ledger + handoffs), a package manager (`plugin_import`), and an event loop (the
`session` phase) — implemented as prose the model must read, hooks that catch what it forgets, and
scripts it must remember to call. The future direction is re-homing the **enforcement shell** into a
real harness while the judgment corpus stays model-side data.

**The operator's stated biggest gain: things reliably firing, honestly** — gates as code that cannot
be skipped or rationalized around. Token savings and simplification are secondary and assumed, to be
confirmed.

Port shape (agreed in the 2026-08-05 architecture review):

- framing/routing → task-submission middleware; composition → native subagent prompt assembly;
  handoff + ledger → schema-validated tools whose handlers refuse invalid closes; session loop → the
  harness's actual loop; plugin distribution → versioned packages (kills half-provisioned roots like
  the 2026-08-05 motors-and-controls stall);
- the ratify gate and retrospective remain model-side judgment, triggered by harness events;
- the Python CLIs stay as subprocesses — they are the portable, tested kernel; don't port them.
  Candidate first target: a single TypeScript extension for badlogic's Pi harness.

Success metric: **prose deleted** — every rule that becomes code is tokens removed from every spawn.
Hard constraint: one source of truth for the corpus; harnesses (Claude Code, Pi, …) are consumers —
the moment judgment forks per-harness, the ratify gate stops meaning anything. Smallest first bite
when the time comes: wrap `handoff.py validate` + the ledger close gate as real harness tools.

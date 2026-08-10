# skills — praxis + corpora, separated

This house holds the **idealized, fully-separated** form of two skills that compose:

- **`praxis/`** — the process / orchestration core. It routes work, runs phases, owns the framing step
  and the handoff primitive, and enforces "one unit-of-work = one spawn = one handoff." It is **pure**:
  it contains no reference to any engine — it does not import one, does not know where one lives, and
  does not name one's verbs. It ships with **empty plugin slots** and degrades gracefully when nothing
  is registered.

- **`corpora/`** — one **judgment engine** (domains, `kernel.md`, `scripts/corpus.py`, …). It composes
  the domain set for a unit of work, ratifies principles, and owns everything about *what to think*.
  Its praxis-facing contribution — the files that register it into praxis — lives under
  **`corpora/praxis-plugin/`**.

Praxis is one thing; corpora is one engine that plugs into it. A second engine would be a second
contribution registering into the same slots, and praxis-core would drive it with the same code.

## This is the Pi fork

This tree (`~/jdev/skills-pi`) is the **Pi-dedicated fork**, split from the Claude-Code-hosted
original (`~/jdev/skills`) so it can optimize for Pi without interop constraints. The front door is
delivered through `pi-extension/praxis/index.ts` — one extension registering the tools natively
(`begin_work`, `praxis_spawn`, `compose_spawn`, `close_work`, `work_status`) with the edit gate and
stamping ported to `tool_call`/`tool_result` handlers. It shells to `praxis/front-door/cli.py`,
which runs the python engine room (`praxis/scripts/`) and corpora (`corpora/scripts/corpus.py`) for
composition and spawn assembly. Pi-only upgrades (in-context inline delivery, native isolated
spawns, judgment eviction on close, stance→runtime policy) are documented in
`pi-extension/README.md`.

The original FastMCP server (`praxis/front-door/server.py`) and shell hooks (`praxis/hooks/`) remain
for reference but are the Claude Code path.

## How they compose (the plugin-slot model)

Praxis exposes SLOTS; an engine's contribution fills them:

| praxis slot | corpora fills it with (`corpora/praxis-plugin/…`) |
|---|---|
| `engine/plugins/` (capability → verb + `cli` location) | `engine/plugins/corpora.json` |
| `handoff/plugins/` (handoff fields an engine expects) | `handoff/plugins/corpora.json` |
| `phases/` (universal only: framing/routing/interop) | `phases/*.md` (retrospective, domain-import, …) |
| the sequence scripts praxis-core doesn't own | `scripts/*.py` (domain_import, ratify_writeback, …) |

The shipped `praxis/` has empty `engine/plugins/` and `handoff/plugins/`. **"Moving corpora in"** = a
project snapshot-imports corpora's `praxis-plugin/` contribution into praxis's slots (the same
snapshot-import model corpora uses for domains). The engine's CLI location travels with its manifest
(`cli.entry`, resolved relative to the manifest), so praxis learns where to invoke from the registered
data — never from a hardcoded path.

## Plugins — concerns as self-contained faces

A **plugin** is a self-contained concern living under `plugins/<name>/`, OUTSIDE `praxis/` so the core
stays engine-free. A plugin can carry either or both faces, declared in its `plugin.json`:

- a **judgment face** (`judgment_face`: a `corpora/domains/` dir) — the concern's design/decision
  domains. On import it is staged THROUGH the registered engine's ratify gate (containers
  auto-adopted, principles proposed as candidates), never written live.
- a **praxis face** (`provides`: slot → subdir) — the concern's phases/scripts, snapshot-imported into
  the project's own `praxis/` slots the same way corpora's contribution is.

| plugin | faces | what it is |
|---|---|---|
| `plugins/routing/` | judgment only | praxis's own judgment about its process — routing, spawn-integrity, planning, and `interviewing` (the clarifying-dialogue judgment that companions planning; consumed by the framing phase). Praxis runs on deterministic facts alone with no engine; with one, these compose into its `route-work`/`plan-work` units. |
| `plugins/uiux/` | **both** | the UI/UX concern. Judgment face: the styling-engine-agnostic design domains (color, motion, visual-hierarchy, design-method, …; *not* css — that's a coding/styling-engine concern, kept in corpora-core). Praxis face: `library-init`/`library-sync` phases + `library_state.py`. A UI project moves it in — praxis face → slots, judgment face → gate — and gets both the domains a design unit-of-work composes and the library phases that bootstrap/maintain them. |
| `plugins/writing/` | praxis only (judgment accretes) | the writing concern — producing prose *products* across genres (fiction, non-fiction, copy, legal, documentation) and styles. Ships only the writing *process* (`writing-draft` divergent, `writing-revision` convergent); its judgment face is deliberately **empty**. Craft judgment can't be pre-authored — a baked-in "good writing" rule is just baseline an agent applies anyway, and corpora only earns its keep with judgment that *beats* baseline. So genre/style domains are born at the gate from real writing, then promoted back here. (Not the retired prose plugin, which wrongly repackaged corpora's own housekeeping domains.) |

A plugin's judgment face need not ship populated: `plugins/writing/` ships **process only**, letting
genre/style judgment accrete at the gate from real work rather than inventing it up front — structure
can be laid out deterministically, judgment must be earned. corpora-core keeps only its own operating
domains (ratify-gate, principle-judgment, retrospective) plus `prose-craft` (how the engine writes its
own artifacts); every other concern's judgment lives in the plugin that owns it or is earned per
project.

"Moving a plugin in" (`praxis/scripts/plugin_import.py import --contribution plugins/<name> --root PROJECT`)
imports the praxis face into the project's slots and stages the judgment face through the engine's gate;
provenance lands in `<root>/praxis/plugins.lock.json`.

**Authoring plugins** is scripted too — the deterministic half only:
- `praxis/scripts/plugin_scaffold.py` (core, engine-free): `new` writes a plugin's `plugin.json` + face
  dirs; `validate` checks the manifest + layout.
- corpora's `relocate-domain` verb (`corpus.py relocate-domain`, also a registered engine capability):
  moves a domain's working file **and** its whole audit trail (provenance + counter + efficacy) between
  domains-dirs — the scripted form of a plugin extraction's audit surgery, replacing what was hand-done.
- `praxis/phases/plugin-authoring.md` sequences them and marks the seam where *judgment* (whether it's a
  plugin, which domains move, whether judgment ships or accretes) stays out of the scripts.

## Verify

```bash
# 1. Pure praxis-core: passes with a GENERIC engine stub, zero corpora present.
cd praxis && python3 -m unittest discover -s tests

# 2. Corpora plugged in: the sequence scripts + an integration test that registers corpora's
#    manifest (pointing at corpora/scripts/corpus.py) into a praxis engine slot and composes for real.
cd corpora/praxis-plugin && python3 -m unittest discover -s tests

# 3. Corpora's judgment engine itself (domains, gate, select, chunk ledger):
cd corpora && python3 -m unittest discover -s tests

# 4. The uiux plugin's praxis face (deterministic library eligibility):
cd plugins/uiux/praxis && python3 -m unittest discover -s tests

# 5. The purity check — no engine named anywhere in the core:
grep -ri corpora praxis/    # → nothing
```

## Note

The canonical, still-running repo lives at `~/jdev/corpora` and is untouched — this house is a fresh
assembly of the idealized separation, not a replacement for it. Design decisions and open judgment
forks are recorded in `NOTES.md`.

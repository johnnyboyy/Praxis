---
name: corpora
description: "Corpora — a judgment engine for a design+coding system. Composes the domain set (stance + domain subset) for a unit of work, evaluates and authors principles at the ratify gate, and runs the retrospective. One flat domain pool; each domain states its own load condition against the project's config (language, framework, styling, has-ui). Invoked by a process/orchestration layer for composition and ratification — corpora does not route, spawn, relay, or drive the workflow itself."
---

# Corpora

A judgment engine for a portable design+coding system. Corpora answers two kinds of question, and
only these:

- **What judgment applies** to a unit of work — the *composition*: a stance (convergent or divergent)
  plus the domain subset, returned by `scripts/corpus.py select` for the project's config.
- **Whether new judgment is sound and where it belongs** — the ratify gate, write-back, and the
  retrospective.

Corpora is **invoked** by a process/orchestration layer that owns routing, deciding units of work,
spawning, the handoff lifecycle, and the loop. Historically that process layer was folded into
corpora itself ("the orchestrator"); it is now a separate engine (praxis). Corpora does not route,
spawn, relay, or decide when to spawn — it is called for a composition, and it is called at the
ratify gate. `kernel.md` is the canonical reference: the principle schema, the stance+composition
model, generative stance, the ratify gate, write-back, and the retrospective.

A **spawn** (the process layer's unit) draws a *stance* plus a **composition** — the domain subset
corpora composes for the task at hand. Judgment lives in domains, not fixed roles or a cached naming
layer between task and domains: corpora states the domain subset directly from the unit-of-work, every
time. How that subset is turned into a spawn, and whether it runs inline or isolated, is the process
layer's call, not corpora's.

**One flat domain pool.** Every domain this skill carries — its own operating-judgment domains
(`ratify-gate`, `principle-judgment`, `retrospective`), the stack-agnostic coding/authoring domains
(`coding-general`, `prose-craft`), and the stack-specific ones (`coding-ts`, `coding-react`,
`coding-nextjs`, `coding-expo`, `css`) alike — lives together in `domains/`, with one
`domains/audit.md` for the pool; nothing here is a privileged tier a project's own principle gets
"promoted" into (`kernel.md`, "Project corpora"). Whole *concerns* of judgment ship separately as
plugins a project imports — the design domains (color, motion, …) as the UI/UX plugin, the
routing/planning/spawn-integrity/interviewing domains as the routing plugin — each staged into the
project's own `domains/` through the same ratify gate, then loaded as the project's own. There is no separate "role pack"
layer selected by a project-config field either: each stack-specific domain states its own load
condition as `applies-when` frontmatter against `.corpora/config.md`'s existing shape fields
(`coding-nextjs` loads when `framework: nextjs`, `css` loads when `styling` is not `none`, and so on)
— retired 2026-07-22, see `kernel.md`, "One flat domain pool," for why the old `role-pack:` field
added an indirection without adding information. `scripts/corpus.py select --unit-of-work <u>`
evaluates every domain's condition mechanically against the project's actual config and returns the
domain subset directly — see `kernel.md`, "Spawns: stance + composition."

## Project shape

Every composition reads `.corpora/config.md`. It carries:

- **Project shape** — language, framework, package manager, `has-ui`, styling. Each stack-specific
  domain checks these fields directly to decide whether it applies to this project; `has-ui`
  additionally governs whether the design domains are ever composed at all.
- **Project utilities and commands** — project-owned deterministic tools that replace recurring
  inference, UI/UX library locations, and verification commands. Environment-owned capabilities
  such as browser automation, image generation, and agent delegation are discovered from the
  current runtime rather than persisted here.
- **`debug`** — optional, operator-set, defaults to no. Gates audit-trail writes that otherwise
  don't happen. (Spawn-prompt assembly and its saved copy moved to praxis with the process/judgment
  split — corpora's `emit-spawn-parts` only emits the prompt's parts; praxis composes and saves them,
  honoring praxis's own `debug:`.) See `kernel.md`.

If `.corpora/config.md` does not exist, the project is not bootstrapped. No domain or composition
carries other "if missing" logic.

---

# What corpora owns — and what it doesn't

Corpora is the judgment layer. It owns exactly:

- **Composition** — `scripts/corpus.py select --unit-of-work <u>` returns the stance-appropriate
  domain subset for the project's config. The process layer decides the *unit-of-work* (a routing
  judgment) and invokes corpora to turn it into a domain set; corpora does not choose the unit itself.
- **The ratify gate** — propose → ratify → promote for new corpus content: the genuine-fork test,
  domain assignment, write-back, kills, and graduation (`kernel.md`, "The ratify gate").
- **The retrospective** — reading a domain's accumulated corpus and gate history for which signals
  are real (`praxis-plugin/phases/retrospective.md`, `domains/retrospective.md`).

It does **not** own — these belong to the process layer that invokes it:

- routing, framing, and deciding units of work;
- spawning, and the inline / resume / isolate execution decision;
- the handoff artifact's creation, relay, and lifecycle (corpora only *reads* the proposal fields a
  completed handoff carries, as input to the ratify gate);
- the chunk ledger and the "one unit-of-work = one spawn = one handoff" rule;
- the session loop.

When corpora needs one of these to have happened (a handoff to ratify from, a unit-of-work to compose
for), it receives it as input — it does not produce or drive it.

## domains

stance: convergent

Corpora loads its own operating-judgment domains when it is invoked: **`ratify-gate`** (assembling
what a complete proposal needs and processing what a handoff returns) and **`principle-judgment`**
(whether a proposed or already-ratified principle is genuine judgment and lives in the right domain)
— `domains/ratify-gate.md` and `domains/principle-judgment.md`, plus each one's
`.corpora/domains/<name>.md` project counterpart when it exists.

A third, **`retrospective`** (reading a domain's accumulated corpus and gate history for which signal
is real), loads on a different cadence — only when a retrospective actually runs — since its judgment
has nothing to apply to outside that periodic pass.

Routing/spawn/relay judgment (`subject: process`) is the process layer's own, not corpora's — it
lives in the routing plugin, and corpora does not carry it as one of its domains.

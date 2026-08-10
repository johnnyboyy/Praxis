---
name: corpora:engine-bootstrap
description: The engine's own bootstrap — detect a project's shape and write .corpora/config.md, the one fallback corpora needs to become routable. Invoked by praxis's operation loop (session entry) when a project is not yet bootstrapped. The config write itself is the deterministic `corpus.py init` verb; this phase is the judgment around it (detection, the has-ui fork, the default-pool offer). For has-ui projects the design libraries are stood up by the design plugin's library-init phase, not here.
---

# Phase: engine-bootstrap

Corpora's own bootstrap — what makes corpora itself routable, the fallback the operation loop reaches
for when a project has no `.corpora/config.md` yet. It is the engine counterpart to praxis's root
marker (`praxis_init`): praxis has a root, corpora has a project shape. The *write* is a deterministic
script (`corpus.py init`); this phase is the **detection and routing judgment** around it.

**Entry condition:** invoked by `operation`'s session entry when the engine's project state is absent.

**Stance:** convergent. Not generative.

## Detect the shape, then write the config

Detect the project's shape before anything else — read the platform's agent instructions (`AGENTS.md`
/ `CLAUDE.md`), the package manifest and lockfiles, and enough of the codebase to determine, asking
the operator only for what cannot be inferred:

- **language(s)**, **framework**, **package manager**, **styling** — what each stack-specific domain's
  `applies-when` frontmatter checks to decide whether it loads. (There is no separate role-pack field.)
- **`has-ui`** — does this project render a UI a person looks at? A web/Electron/TUI app → yes; a CLI
  that prints text, a library, a backend service → no. This single field decides whether the design
  libraries get stood up.
- **verification commands** — the project's real lint / check / build / test commands (some have none).

Then write it with **`corpus.py --root <dir> init`** (`--language … --framework … --has-ui … --styling
…`, plus `--lint/--check/--build/--test`). Detect, don't assume: a wrong command is worse than `none`,
because a spawn will try to use something that isn't there. The verb writes the schema; the values are
this phase's judgment.

## Route after the config exists

- **`has-ui: no`, no concrete feature request** — Phase 1 was the whole job. Note to the operator that
  divergent/visual-identity domains are inactive and the project runs on the kernel layer.
- **`has-ui: yes`, no feature request** — stand up the design libraries directly through the design
  plugin's **library-init** phase (UI library first, then screenshot seed and UX library, which depend
  on it), ratifying each through the gate as usual. No planner hop — there is nothing to decompose.
- **A concrete feature request accompanied bootstrap** — route a **planning** workstream with a
  capability combining the bootstrap need and the feature (passed as direct input, not from a
  ROADMAP). The planner decomposes into the design-system setup tasks (when `has-ui: yes`) sequenced
  ahead of the feature's own tasks, by real output dependency. Hold one boundary: the planner must not
  ask the library-init phase's own audience/aesthetic-direction questions — those are that phase's
  divergent judgment, asked when it runs.

## Also, at bootstrap

- **Offer the default-pool import.** A fresh project's `.corpora/domains/` starts empty. Ask whether to
  bulk-import the matching default pool now (`corpus.py import-default-pool`) — the normal path for a
  new project; declining just means starting emptier and importing individually later.
- **Create the working ledgers.** For a UI project, `.corpora/deferred-decisions.md` with `decisions:
  []`; for every project, `.corpora/deterministic-shortcut-candidates.md` with `candidates: []`.

Bootstrap is complete once the config exists and every applicable setup phase has run and ratified —
from there the operation loop resumes normal per-unit routing.

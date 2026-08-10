# Phase: library-init

Found a project's design libraries from nothing — one phase over the three init variants (UI, UX,
screenshot), which are variants of a single move (establish a library that doesn't exist yet), not
three routes. Migrated from corpora `processes/ui-library-init.md`,
`processes/ux-library-init.md`, `processes/screenshot-library-init.md`. The *eligibility and
ordering* of these — which library is missing, and the ui→{screenshot, ux} dependency — is a
deterministic fact praxis scripts (`library_state.py`); the documentation itself is design judgment
(UI/UX variants) or mechanical capture (screenshot variant).

**Entry condition (from `library_state.py state`):** `has-ui: yes` and the target library absent —
`ui-library-init` when `ui` absent; `screenshot-library-init` / `ux-library-init` when `ui` present
but the manifest / `ux-library.md` absent. The script computes these and names the `next_bootstrap_step`,
so the ordering (Phase 2 ui before Phase 3 screenshot / Phase 4 ux, the latter two independent) is
read, not remembered. Existence of `ui-library.md` is the deterministic proxy for "ui-init ratified."

**Stance (per variant, from the same fact):**
- `ui-library-init` — **divergent**, `unit-of-work: bootstrap-ui-surface`.
- `ux-library-init` — **convergent**, `unit-of-work: bootstrap-ux-surface`.
- `screenshot-library-init` — **mechanical, no composition, no stance** (identifying and capturing a
  screen needs no design judgment); runs inline, produces no handoff of its own.

**Invocations:** the judgment engine, composed for the variant's `unit-of-work` (UI/UX only). The
narrower `bootstrap-*` composition — not the ongoing `design-*` set — because founding from nothing
has no concrete components/screens for every domain to attach to yet; that narrowing lives in each
contributing domain's own `units-of-work` frontmatter, not here.

## Deterministic facts — run first (praxis script)

- **`library_state.py state --root <root> --json`** — `has_ui`, which libraries exist, the eligible
  init variant(s), each variant's `unit_of_work`/`stance`/`mechanical`, and the `next_bootstrap_step`.
  This is the whole "which init runs and in what order" question, as fact.

## The work (per variant)

- **UI / UX init** — one spawn each, composed as above, then the ordinary spawn lifecycle. Document
  what the project actually is to the depth a scoping feature needs (do not invent aspirational
  components/states). Foundational identity choices (a color system, a density decision) live in the
  library `Artifact` and are reviewed via **design-decision-review**, *not* dressed up as
  `proposals:`. `proposals:` is reserved for genuine judgment *about how to make this kind of
  decision* — none is a valid outcome. A defect found while documenting is a **finding** → the
  handoff's `Surfaced` section, not a proposal.
- **Screenshot init** — read the ratified `ui-library.md`'s component vocabulary; for each screen the
  manifest lacks, capture one canonical shot with the project's browser tool and register it
  (`corpus.py screenshot-record`). One shot per screen; skip anything already current. If no browser
  tool this session, skip the phase entirely — the cache grows the normal way later.

**Artifact:** the library document (UI/UX, reviewed at design-decision-review) or the seeded manifest
entries (screenshot). UI/UX leave `ui-drift` empty — init is not the drift-invalidation channel.

**Surfaced/lacking:** findings (bugs/gaps) go to `Surfaced`, one line each. A screenshot init with no
browser tool available surfaces that it was skipped rather than reporting the cache complete.

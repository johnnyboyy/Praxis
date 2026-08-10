# Phase: library-sync

Bring a project's design libraries back in line with its actual rendered/behavioral state after
coder-side drift has accumulated — one phase over the three sync variants (UI, UX, screenshot).
Migrated from corpora `processes/ui-library-sync.md`, `processes/ux-library-sync.md`,
`processes/screenshot-library-sync.md`. Sync is documentation *against current state*, not a fresh
design pass; the judgment (is this discrepancy a chosen change to document, or an unintended defect
to surface as a finding) is the engine's, and the eligibility is `library_state.py`'s.

**Entry condition:** `has-ui: yes` and the target library **present** (`library_state.py` marks these
`drift_gated`). The *drift threshold itself* — `library-drift.since-last-sync ≥ 3`, or an immediate
retired-something-the-library-still-teaches — is a **corpora counter**, not a filesystem fact; praxis
reports the phase is drift-gated and relays the count, it does not invent it. The operator's decision
to act on the suggestion is the judgment, not the count.

- The **UI** and **UX** syncs are suggested off the *same* `library-drift` counter (UX drift is a
  subset of UI drift — real UX work surfaces as changed screens). The operator dismisses the UX half
  for a purely-visual restyle. `corpus.py sync-done` resets the shared counter once, whichever ran.
- The **screenshot** sync fires *every time* a handoff's `ui-drift.screens`/`.components` is
  non-empty (not on a threshold) — invalidating a stale capture is cheap to check, expensive to leave
  wrong. It is mechanical, runs inline at the gate, produces no handoff.

**Stance (per variant):** `ui-library-sync` — **divergent**, `unit-of-work: design-ui-surface`;
`ux-library-sync` — **convergent**, `unit-of-work: design-ux-flow` (the full ongoing composition, not
the narrower founding one — a synced project already has concrete components/screens to weigh);
`screenshot-library-sync` — **mechanical, no composition**.

**Invocations:** the judgment engine, composed for the variant's ongoing `design-*` unit-of-work
(UI/UX only).

## Deterministic facts — run first (praxis script)

- **`library_state.py state --root <root> --json`** — confirms `has_ui` and that the target library
  exists (a sync's precondition), and marks the sync variants `drift_gated`. The specific screens /
  flows to audit come from the triggering handoff's `ui-drift`; absent that detail, the library's
  full section list.

## The work (per variant)

- **UI / UX sync** — audit the library section by section against what the code actually looks like /
  how it actually behaves today; overwrite any entry the code has moved away from, as a standing
  description of current state — no history tags, no "supersedes X", no dates, no naming what was
  rejected. A discrepancy that reads as an unintended defect is a **finding** → `Surfaced`, not a
  silent correction. Genuinely new judgment (a pattern that recurred enough to generalize) still goes
  through `proposals:` — sync is not exempt from producing a principle when the work earns one, only
  from treating documentation corrections as principles. Leave `ui-drift` empty (the job is to
  *close* drift, not accumulate it). After the gate, `corpus.py sync-done` resets the counter.
- **Screenshot sync** — `corpus.py screenshot-mark-stale --screens … --components …` from the
  handoff's own `ui-drift` (it expands components into every screen the manifest tags them on);
  recapture each invalidated screen with the browser tool and re-register, inline in the same gate
  pass. No browser tool → leave the screens marked stale for a later session.

**Artifact:** the corrected library sections (UI/UX) or the refreshed/invalidated manifest entries
(screenshot).

**Surfaced/lacking:** findings to `Surfaced`; a screenshot sync with no browser tool surfaces the
deferred recaptures rather than reporting the manifest current.

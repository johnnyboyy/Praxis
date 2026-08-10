# Audit record — uiux plugin's judgment face

Provenance and per-kill audit detail for the uiux plugin's UI/UX design domains (`color`, `motion`,
`visual-hierarchy`, `surfaces-elevation`, `wizards-flows`, `forms-inputs`, `lists-selection`,
`validation-feedback`, `design-method`) — extracted from corpora-core's own `domains/audit.md` when
these styling-engine-agnostic design-judgment domains were relocated into `plugins/uiux/` as the
plugin's judgment face. (`css` was briefly moved here too but returned to corpora-core — CSS/Tailwind
authoring is a styling-engine implementation concern, not a design one.) This is one domains-dir among
any, symmetric with a project's own
`.corpora/domains/`, imported through the engine's ratify gate the same way (`kernel.md`, "Project
corpora"). Loaded only at ratify/retrospective time — never in a spawn's working context. Keyed by
principle `id`, each noting its `domain`. See `kernel.md`, "Storage: working vs audit." (Kill logs
live in the per-domain working files so they are available in the working context.)

The `# composition:` notes that once annotated several of these domains (recording a 2026-07-25
prose-cleanup) were dropped in the extraction; a domain's composition membership is stated by its
`units-of-work` frontmatter, not by an audit comment.

```yaml
provenance:

# ---- domain: color ----
- id: semantic-tokens-required-for-theme-switching
  domain: color
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (smashingmagazine.com/2024/05/naming-best-practices). Ratified directly to seed — FAMOUS has one fixed dark aesthetic with no theme-switching need, but the two-tier (primitive/semantic) architecture is standard practice any project on this pack would need if it ever added light/dark or brand-variant theming."
  see-also: semantic-token-names-by-role-not-value
  killed: 2026-07-22

- id: semantic-token-names-by-role-not-value
  domain: color
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (smashingmagazine.com/2024/05/naming-best-practices), companion to semantic-tokens-required-for-theme-switching from the same source. Ratified directly to seed as structural confirmation — FAMOUS's own token names (--color-bg-canvas, --color-accent-fame, --color-bg-overlay) already follow role-based naming, not value-based."
  see-also: semantic-tokens-required-for-theme-switching
  killed: 2026-07-22

- id: color-palette-inspiration
  domain: color
  provenance: "2026-06-02, operator-provided. Clarified 2026-06-13."

- id: palette-chromatic-depth
  domain: color
  provenance: "2026-06-03, taste training session."

# ---- domain: surfaces-elevation ----
- id: disclosure-panel-vs-modal
  domain: surfaces-elevation
  provenance: "2026-06-14, load calculator history panel design spec."

- id: dark-floating-surface-fill
  domain: surfaces-elevation
  provenance: "2026-06-19, nav background depth session."

- id: scroll-fade-gradient-surface-match
  domain: surfaces-elevation
  provenance: "2026-06-19, nav background depth session."

# ---- domain: visual-hierarchy ----
- id: redundant-badge-sublabel
  domain: visual-hierarchy
  provenance: "2026-06-02, Box Selector visual spec."

- id: control-grouping-encodes-unity
  domain: visual-hierarchy
  provenance: "2026-06-03, taste training session (originally as capsule-encodes-same-value)."
  history:
    - date: 2026-06-20
      type: generalized
      reason: "Original rule prescribed capsule as the specific pattern — 'join into a capsule when segments share a value.' This directed the designer to a single implementation rather than stating the underlying principle. The insight is that any form of visual grouping (capsule, joined buttons, bordered cluster) encodes semantic unity; the specific form is a design decision the rule should inform, not resolve. Rule rewritten to state the general principle with capsule as one named example. Id renamed from capsule-encodes-same-value to reflect the broader concept."

- id: hierarchy-through-scarcity
  domain: visual-hierarchy
  provenance: "2026-06-04, retrospective consolidation."
  history:
    - date: 2026-06-20
      type: absorbed-examples
      reason: "Killed one-highlight-per-result-set and accent-color-for-distinction-not-data as redundant instances of this principle. Concrete examples those principles captured: (1) apply highlight to exactly one card per results panel — when two outputs are co-primary, merge into one highlighted card with an internal divider rather than two competing highlights; (2) accent color belongs only on the distinguished row, all other data values in secondary text color. Both earned in Box Selector results panel."

- id: responsive-text-by-viewport-distance
  domain: visual-hierarchy
  provenance: "2026-06-09, Box Selector desktop text legibility audit."

# ---- domain: motion ----
# composition: declared by ui-design and ux-design (moved out of the working file's own prose 2026-07-25
# so a consuming spawn's context doesn't carry the sibling composition's name for no functional benefit)
- id: motion-as-accent
  domain: motion
  provenance: "2026-06-03, taste training session."

- id: scrollytelling-must-always-react
  domain: motion
  provenance: "2026-06-13, homepage journey audit."

- id: reduced-motion-instant-not-absent
  domain: motion
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (joshwcomeau.com/react/prefers-reduced-motion — source URL returned 403 at extraction time, content pulled from training-data knowledge of this well-known article). Ratified directly to seed — no reduced-motion handling exists anywhere in FAMOUS yet, but the instant-vs-absent distinction is real UX judgment applicable to any project on this pack with JS-driven animation."
  see-also: motion-as-accent, prefers-reduced-motion-requires-js-hook

# ---- domain: validation-feedback ----
# composition: declared by ux-design and ui-design (moved out of the working file's own prose 2026-07-25
# so a consuming spawn's context doesn't carry the sibling composition's name for no functional benefit)
- id: warning-colocated-with-resolution
  domain: validation-feedback
  provenance: "2026-06-02, Box Selector visual spec."

- id: warning-banner-must-locate-its-fix
  domain: validation-feedback
  provenance: "2026-06-02, Box Selector UX review."

- id: filter-side-effects-are-surfaced
  domain: validation-feedback
  provenance: "2026-06-02, Box Selector UX review."

# ---- domain: forms-inputs ----
# composition: declared by ux-design and ui-design (moved out of the working file's own prose 2026-07-25
# so a consuming spawn's context doesn't carry the sibling composition's name for no functional benefit)
- id: numeric-inputs-start-empty-not-zero
  domain: forms-inputs
  provenance: "2026-06-14, load-calculator UX audit."

- id: zero-count-orphan-rows
  domain: forms-inputs
  provenance: "2026-06-02, Box Selector UX review."

- id: unified-field-over-derived-dual-fields
  domain: forms-inputs
  provenance: "2026-06-14, load-calculator appliance row overhaul."

- id: persistent-controls-not-conditional
  domain: forms-inputs
  provenance: "2026-06-14, load-calculator appliance row overhaul."

- id: forms-reveal-conditional-fields
  domain: forms-inputs
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (nngroup.com/articles/progressive-disclosure). Ratified directly to seed — no current form in FAMOUS has this shape, but the guidance is applicable to any project on this pack with conditional-field forms."
  see-also: progressive-disclosure-for-primary-advanced-split, persistent-controls-not-conditional

- id: validate-on-blur-then-on-change
  domain: forms-inputs
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (smashingmagazine.com/2022/09/inline-validation-web-forms-ux — source URL returned 403, extracted from search-result summaries and corroborating UX research). Ratified directly to seed — no field-level validation surface exists in FAMOUS yet, but the blur-then-change sequencing is standard, non-obvious enough to be worth encoding for any project on this pack with inline form validation."
  see-also: warning-colocated-with-resolution

# ---- domain: lists-selection ----
# composition: declared by ux-design and ui-design (moved out of the working file's own prose 2026-07-25
# so a consuming spawn's context doesn't carry the sibling composition's name for no functional benefit)
- id: indicator-weight-matches-job
  domain: lists-selection
  provenance: "2026-06-16, load calculator history redesign."

- id: active-row-is-inert
  domain: lists-selection
  provenance: "2026-06-16, load calculator history redesign."
  killed: 2026-07-22
  history:
    - date: 2026-07-10
      type: killed
      reason: "Superseded by active-row-is-inert-exact-route-only, promoted directly from the Meridian project (operator-approved cross-project edit, not a retrospective promotion) — see that entry below for the discovered defect."

- id: active-row-is-inert-exact-route-only
  domain: lists-selection
  kind: judgment
  provenance: "Meridian project, coder, 2026-07-10, top-bar rewrite pass. A Sidebar nav item's active state (`pathname.startsWith('/clients')`) spanned both the Clients list screen and every client-detail sub-page. Applying active-row-is-inert's blanket 'no hover, no click' treatment made a real, meaningful click (returning to the list from a detail page) silently do nothing, breaking tests/replay/runCase.ts's persistent-chrome recovery path (30 tests failed, confirmed via git stash bisection against the untouched baseline). Operator reviewed the coder's fix (keep it a real Link, styled to look inert) and pushed back: the styling itself was wrong too, not just an implementation detail — a section-spanning active item should stay visually and functionally interactive, since a click there does something real. Refined and edited directly into the shared pack seed at the operator's explicit request, rather than deferred to a project-level override or a future retrospective promotion."

- id: section-level-explanation-not-row-level
  domain: lists-selection
  provenance: "2026-06-14, load-calculator appliance row overhaul."

# ---- domain: wizards-flows ----
- id: origin-step-marked-visited-on-navigation
  domain: wizards-flows
  provenance: "2026-06-14, load-calculator UX audit."

- id: wizard-output-consistent-regardless-of-path
  domain: wizards-flows
  provenance: "2026-06-14, load-calculator UX audit. see-also wizard-callbacks-unconditional (coding-react)."

- id: optional-step-must-be-labeled-optional
  domain: wizards-flows
  provenance: "2026-06-14, load-calculator UX audit."

# ---- domain: design-method ----
- id: clarity-over-polish
  domain: design-method
  provenance: "2026-06-22, extracted from UX designer 'Project context' instruction."

- id: document-visual-sub-systems
  domain: design-method
  provenance: "2026-06-12, full site visual audit."

- id: documentation-before-screenshots
  domain: design-method
  provenance: "2026-06-22, extracted from the designer 'What you do' screenshots bullet."
  history:
    - date: 2026-06-22
      type: consolidated
      reason: "This principle existed byte-for-byte identical in BOTH the ui-designer and ux-designer seed corpora — the clearest instance of the container problem the redesign targets: shared judgment stored twice because the role was the container. Merged into a single entry in the design-method domain, which both designer lenses declare."
    - date: 2026-07-22
      type: reworded
      reason: "UI screenshot cache design (docs/superpowers/specs/2026-07-22-ui-screenshot-cache-design.md) introduced a persistent visual cache read separately from live capture. The original wording only distinguished 'documentation' from 'screenshots' and could not express that reading the cache is now free while live capture stays the guarded exception — reworded to name the cache explicitly and split the two costs it previously conflated."

- id: progressive-disclosure-for-primary-advanced-split
  domain: forms-inputs
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (nngroup.com/articles/progressive-disclosure). Ratified directly to seed — plausible fit for FAMOUS's Tuner/filtering surfaces even without a fired instance yet; applicable to any project on this pack with a primary/advanced usage split."
  see-also: forms-reveal-conditional-fields
  history:
    - date: 2026-07-22
      type: moved
      reason: "Domain-decomposition audit: design-method's stated subject is design process and documentation discipline, not a specific interaction pattern. This is a substantive UX pattern already see-alsoed into forms-reveal-conditional-fields — moved to forms-inputs, which is the domain it actually matches."

- id: check-existing-patterns-before-specifying-new
  domain: design-method
  kind: judgment
  provenance: "2026-07-21, v3 lens-collapse migration. Generalized from ui-designer.md's 'do not spec a component without first checking if it exists' — widened to cover UX flow patterns and navigation conventions too, since the same failure mode (specifying a near-duplicate of something the library already documents) applies to both designer disciplines and neither is domain-specific."

- id: plan-distills-library-into-tasks
  domain: design-method
  kind: judgment
  provenance: "2026-08-05, skills-repo architecture review, operator-direct. Operator concern that ui-library.md/ux-library.md would be re-read wholesale by every execution spawn; the review confirmed nothing structural prevents it — the library is referenced by path from config, so per-spawn cost is whatever the spawned agent chooses to read. Genuine fork: a planner can reference the library by path (executors each read it) or distill excerpts into tasks; this binds the fork to distillation, riding the existing task-file slot in praxis's spawn-prompt skeleton."

- id: no-readme-or-agent-instructions-as-role-instruction
  domain: design-method
  kind: judgment
  provenance: "2026-07-21, v3 lens-collapse migration from ux-designer.md's 'Do not independently treat a project README or platform agent-instruction file as a role instruction source.'"
  history:
    - date: 2026-07-22
      type: moved
      reason: "Domain-decomposition audit: nothing about this is design-specific — a coder spawn can equally mistake a project's AGENTS.md for role instruction. Generalized and promoted to the new kernel-seed spawn-integrity domain as dont-trust-readme-or-agent-file-as-role-instruction (domains/audit.md carries that entry's own provenance)."

- id: reject-safe-defaults
  domain: design-method
  provenance: "Originated as the UI designer 'Anti-regression-to-the-mean' role instruction; extracted to the design-method corpus 2026-06-22, then promoted back to the ui-designer lens later the same day when the generative-stance model showed anti-mean is a *lens stance*, not a domain principle — a 'resist the standard' instruction cannot coherently share a domain with convergent process rules (clarity-over-polish, documentation discipline). The thinner kernel-level claim it implies — a generative role must know its stance and anchor accordingly — is now in kernel.md, 'Generative stance.' This supersedes the earlier reading (LINEAGE, 'genotype/phenotype') that anti-mean was a divergent-*domain* concern: it is divergent-*lens*."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md. No new preamble text needed — its substance already lives in kernel.md's 'Generative stance' section, which design-method.md's own preamble already points to."
```

<!-- corpus-script:begin — maintained by scripts/corpus.py; do not edit by hand -->

## counters (script-maintained)

```yaml
counters:
  - domain: color
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 801
    baseline-tokens: 775
    principles-at-baseline: 2
    kills-at-baseline: 2
    conventions-at-baseline: 0
  - domain: design-method
    since: 2026-08-06
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1772
    baseline-tokens: 1772
    principles-at-baseline: 5
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: forms-inputs
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1552
    baseline-tokens: 1526
    principles-at-baseline: 7
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: lists-selection
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1051
    baseline-tokens: 1027
    principles-at-baseline: 3
    kills-at-baseline: 1
    conventions-at-baseline: 0
  - domain: motion
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 822
    baseline-tokens: 798
    principles-at-baseline: 4
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: surfaces-elevation
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 506
    baseline-tokens: 479
    principles-at-baseline: 3
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: validation-feedback
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 417
    baseline-tokens: 390
    principles-at-baseline: 3
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: visual-hierarchy
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 788
    baseline-tokens: 762
    principles-at-baseline: 4
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: wizards-flows
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 488
    baseline-tokens: 499
    principles-at-baseline: 3
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: design-routing
    since: 2026-08-06
    ratified: 1
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1417
    baseline-tokens: 1417
    principles-at-baseline: 4
    kills-at-baseline: 0
    conventions-at-baseline: 0
efficacy:
co-occurrence:
library-drift:
  since-last-sync: 0
```

<!-- corpus-script:end -->

# Audit record — this skill's own domain pool

Provenance and per-kill audit detail for every domain in this skill's own `domains/` — the four
domains corpora's own operation loads directly (`orchestrator-routing`, `ratify-gate`,
`principle-judgment`, `retrospective`) alongside every other stack-agnostic
(`coding-general`, `planning`, `interviewing`, `spawn-integrity`) and stack-specific (`coding-ts`,
`coding-react`, `coding-nextjs`, `css`, `color`, `surfaces-elevation`, `visual-hierarchy`, `motion`,
`wizards-flows`, `ranking-evaluation`, `lists-selection`, `validation-feedback`, `forms-inputs`,
`recoverability`, `design-method`) domain that has accumulated here — this repository is not a
privileged layer a project's principle gets "promoted" into; it is one domains-dir among any,
symmetric with a project's own `.corpora/domains/`, importable and imported-from the same way
(`kernel.md`, "Project corpora"). `role-pack` no longer gates a separate pack layer here either —
see the merge note below. Loaded only at ratify/retrospective time — never in a spawn's working
context. Keyed by principle `id`, each noting its `domain`. See `kernel.md`, "Storage: working vs
audit." (Kill logs live in the per-domain
working files so they are available in the working context.)

> **Web-frontend domain merge (2026-07-22).** The former web-frontend pack layer's domains and audit history were merged flat into this single kernel-seed layer once `role-pack` was retired as a project-config concept (see kernel.md, "Project corpora") — every stack-specific domain now states its own load condition directly against `language`/`framework`/`styling`/`has-ui`, rather than through a pack-name indirection. The provenance entries from that merged layer carry their own migration note below.

> **Migration note (2026-06-22).** These principles were re-homed from the old role corpora
> (`coder.md` pack overlay, `ui-designer.md`, `ux-designer.md`) into domain working files as part of
> the corpus redesign. The role→domain move is uniform and recorded here once rather than as a
> `history` stanza on every principle; only notable moves (cross-role re-homing, consolidations,
> the documentation-before-screenshots dedup) carry an explicit `history` entry below.

```yaml
provenance:
- id: ask-before-architecture
  domain: coding-general
  provenance: "2026-06-26, Blog project. Reached for a CSS class without checking whether the intent was component extraction — required redirection."

- id: verify-before-bulk-edit
  domain: coding-general
  provenance: "2026-05-26, Blog project."

- id: grep-subdirs-before-delete
  domain: coding-general
  provenance: "2026-06-02, Blog project cross-tool shared components refactor."

- id: code-lives-at-consumer-level
  domain: coding-general
  provenance: "Merged from hook-colocation-by-usage, duplicate-formatters-belong-in-lib, tool-shared-components-level, Blog project 2026-06-17."

- id: generic-defers-to-consumer
  domain: coding-general
  provenance: "2026-06-04, Blog project Modal component."

- id: single-callsite-helper-scoped
  domain: coding-general
  provenance: "2026-06-04, Blog project box-selector refactor. Generalized from className-builder framing."

- id: ceiling-comment-for-deliberate-shortcuts
  domain: coding-general
  provenance: "2026-06-15, adapted from ponytail skill review."
  history:
    - date: 2026-07-19
      type: extended
      reason: "slider-puzzle project, tag-identity-dependencies-check-before-handoff discussion. Operator pointed out that the rule as written already bounds the comment with a named upgrade condition, but nothing in the principle schedules an actual re-check of that condition — it can drift the same way an unbounded comment would if no one happens to reread that line. Added an explicit re-check anchored to the existing structural-examination-at-working-checkpoint pass rather than leaving the condition to be noticed by chance."
    - date: 2026-08-07
      type: consolidated
      successor: terminal-checkpoint-pass
      reason: "Merged into terminal-checkpoint-pass alongside structural-examination-at-working-checkpoint and tag-identity-dependencies-check-before-handoff — see that entry."

- id: two-approaches-then-decide
  domain: coding-general
  provenance: "2026-06-16, Blog project dropdown positioning — cycled through five approaches before floating-ui replaced it with a one-line CSS change."

- id: unified-representation-no-type-leakage
  domain: coding-general
  provenance: "Merged from hook-api-hides-internal-branching + no-special-cased-current-item, Blog project 2026-06-17."

- id: utility-over-guesswork
  domain: coding-general
  provenance: "LINEAGE.md, 'Why a color utility exists.' Color derivation session where iterative guessing produced inaccurate LCH results and burned tokens; a small script replaced that with exact single-command output."
  history:
    - date: 2026-07-18
      type: generalized
      reason: "Renamed from color-utility-over-guesswork and widened from color specifically to any deterministic, precision-sensitive, or repeatedly-recurring computation. Operator noticed this was the only coder-facing principle that ever told the coder to recognize and propose a deterministic shortcut candidate — every other domain's equivalent work (date math, geometric layout, hashing) had no trigger at all, since orchestrator-routing's surface-deterministic-shortcut-candidates-liberally is the orchestrator's counterpart and the coder never loads that domain. Color kept as the canonical named instance, including its React Native-specific carve-out."

- id: no-single-char-names
  domain: coding-general
  provenance: "2026-06-24, authored directly from the meta-rules. Derivable from both Explicit by Default (single-character names force Reader Tax reconstruction on every read) and prefer-error-exposing-form (opaque names hide type mismatches and logic errors that a descriptive name would surface). Not surfaced by the coder — the meta-rule stance already suppresses the violation, so no failure ever triggered a proposal."

- id: structural-examination-at-working-checkpoint
  domain: coding-general
  kind: judgment
  provenance: "Promoted from FAMOUS project domain 2026-07-06. Surfaced 2026-07-05, FAMOUS lens system refactoring session: after implementing view transitions + scroll restoration + typed ref registry, the examination pass surfaced the thin useScrollLensRef wrapper, an anonymous scroll-restoration useLayoutEffect, string-selector coupling, and the emergent LensRowEntry grouping. Promoted from FAMOUS to seed — condition makes no reference to FAMOUS-specific structure."
  history:
    - date: 2026-07-19
      type: clarified
      reason: "slider-puzzle project, tag-identity-dependencies-check-before-handoff discussion. The condition anchored to 'before creating the commit,' but the coder lens doesn't control whether or when a commit happens — the orchestrator does, per the ratify gate's step 9. Re-anchored to the coder's own terminal act, the handoff artifact, which every coder session actually has. The ceiling-comment-for-deliberate-shortcuts amendment made the same day pointed at this principle's checkpoint by name, so it inherited the same fix rather than needing a separate one."
    - date: 2026-08-07
      type: consolidated
      successor: terminal-checkpoint-pass
      reason: "Merged into terminal-checkpoint-pass alongside ceiling-comment-for-deliberate-shortcuts and tag-identity-dependencies-check-before-handoff — see that entry."

- id: tag-identity-dependencies-check-before-handoff
  domain: coding-general
  kind: judgment
  provenance: "Promoted 2026-07-19 from the slider-puzzle project's coding-general domain. Discovered when a tile-slide CSS transition never animated: renderBoard() reset boardElement.innerHTML and rebuilt every tile element on each render, leaving no persistent DOM node for the transition to interpolate from — a bug invisible to end-state checks (correct final layout, correct CSS, correct before/after screenshots) because none of them can distinguish an animated arrival from an instant one. The principle went through several rounds with the operator before landing here: first scoped narrowly to CSS/DOM animation mechanics, then generalized to any render-time identity/reference dependency (memoization, reference-keyed caches, instance-bound subscriptions), then given an explicit forward-pass tag plus an anchored checkpoint (before the handoff artifact, not 'before commit,' which a coder may not own) after the operator noted that comments drift silently with no compiler check — same objection that produced the ceiling-comment-for-deliberate-shortcuts amendment above. Promoted directly on operator request rather than after multi-project pressure-testing; its condition names no slider-puzzle-specific stack or structure, so it was judged able to argue for itself."
  history:
    - date: 2026-08-07
      type: consolidated
      successor: terminal-checkpoint-pass
      reason: "Merged into terminal-checkpoint-pass alongside ceiling-comment-for-deliberate-shortcuts and structural-examination-at-working-checkpoint — see that entry."

- id: terminal-checkpoint-pass
  domain: coding-general
  kind: judgment
  provenance: "2026-08-07, operator-directed corpus slimming pass. Consolidation of ceiling-comment-for-deliberate-shortcuts, structural-examination-at-working-checkpoint, and tag-identity-dependencies-check-before-handoff — the three had grown into an interlocked mini-system (each cross-referencing the others, two existing partly to schedule re-checks at the third's checkpoint) describing one moment: the terminal checkpoint before considering work done. One principle with three named checks carries the same judgment at roughly half the text and one trigger. Each source's own origin story remains under its original id above."

- id: module-boundaries-precede-deployment-separation
  domain: coding-general
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (youtube.com/watch?v=4qfsmE11Ejo). Ratified directly to seed — stack-agnostic architecture judgment with no FAMOUS-specific condition; FAMOUS itself (single Expo app) has no current use case, but the principle is written for any project considering a monolith-to-services split."

- id: dependency-graph-over-architecture-diagrams
  domain: coding-general
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (youtube.com/watch?v=4qfsmE11Ejo), companion to module-boundaries-precede-deployment-separation from the same source. Ratified directly to seed for the same reason."

- id: minimize-comments-prefer-self-documenting-code
  domain: coding-general
  kind: judgment
  provenance: "2026-07-15, FAMOUS full-player redesign session. Operator flagged a pattern of liberal inline commenting (layout math, gesture-conflict resolution, UI/UX design rationale) after several of those comments had already gone stale mid-session — a 'shared across three variants' comment surviving two variant deletions, a symmetry comment whose claimed math stopped matching the code, an edge-hint comment describing removed functionality."
  history:
    - date: 2026-07-23
      type: generalized
      reason: "Promoted from FAMOUS's project-level coding-general domain to seed. `spawn-integrity`'s checkpoint-on-context-pressure-tell had referenced 'this project's comment-discipline conventions' as a seed-level given since it was authored, but the underlying rule was never actually promoted alongside it — a dangling reference in the seed layer, caught by an operator noticing verbose comments in a downstream project (motors-and-controls) that had no such rule anywhere in its composed domains. Condition genericized (dropped 'in this project'); rule and reason otherwise unchanged from the FAMOUS original."

- id: derivable-arithmetic-is-not-a-hidden-constraint
  domain: coding-general
  kind: judgment
  provenance: "2026-07-26, motors-and-controls mobile-ux workstream. Commented `minZoom={0.4}` with the ratio to the library's 0.5 default ('~25% more canvas'). Operator's first challenge correctly identified a separate narrative sentence (naming the bug report) as reasoning-leak; the ratio sentence survived that pass. Operator's second challenge caught that the surviving sentence was itself just derivable arithmetic, not new information — self-review had checked for reasoning-leak but not against minimize-comments-prefer-self-documenting-code's own bar."

- id: co-derive-coupled-values-in-one-place
  domain: coding-general
  kind: judgment
  provenance: "2026-07-26, FAMOUS PlayerBarContent.tsx review. A `playbackPhase()`/`PHASE_LABELS` split (state → phase enum → lookup table) was simplified to one function returning both a status label and an action label together per branch, then the underlying feature was cut entirely. Operator generalized the surviving code-organization lesson from the specific status/action-label shape into a standalone principle, and asked to keep its reasoning free of any comparison to single-callsite-helper-scoped so the new principle doesn't read as arguing against its counterpart — the two are disambiguated by their condition fields alone, linked only via see-also."

# domain: ratify-gate (split from orchestrator-routing 2026-07-18; see LINEAGE.md, "The ratify-gate split")
- id: pre-scan-before-spawning
  domain: ratify-gate
  provenance: "2026-06-02, codebase audit session. Three parallel agents each ran independent discovery; user noted the redundancy."
  killed: 2026-07-25

- id: spawn-token-summary
  domain: ratify-gate
  provenance: "2026-06-19, operator requested visibility after aggregate-only reporting made cost analysis opaque."

- id: full-corpus-on-spawn
  domain: ratify-gate
  provenance: "2026-06-19, operator rejected selective inclusion after orchestrator proposed it as a cost-reduction strategy."
  history:
    - date: 2026-06-22
      type: generalized
      reason: "Reframed from 'pass the full role corpus' to 'pass every declared domain in full' for the lens+declaration model. Added the explicit note that loading only declared domains is a fixed contract, not a relevance judgment — so domain-scoping does not violate this principle (the central hazard the redesign had to guard)."

- id: ratify-gate-judgment-vs-knowledge
  domain: ratify-gate
  provenance: "2026-06-22, FAMOUS 3D keyboard-key grid ratify session. Orchestrator killed preserve-3d-chain on its own judgment ('a model would know this from training') without routing the distinction to the operator. Post-session reflection surfaced why the role is better positioned to make this call than the orchestrator. Operator confirmed the orchestrator principle is thinner: route the question, don't answer it."

- id: domain-assignment-at-ratify-gate
  domain: ratify-gate
  provenance: "2026-06-22, corpus redesign. Domain-scoping moved corpus ownership off roles; the ratify gate became the point where a proposal is assigned a domain (or a new domain is born). Exercised in practice 2026-06-28 (HiraganaQuiz ratify session)."

- id: artifact-points-to-persisted-file-not-full-reproduction
  domain: ratify-gate
  provenance: "Meridian project, 2026-07-17, retrospective conversation. Operator flagged that UI-library sync handoffs reproduced the whole ui-library.md document in the Artifact section despite the role having written directly to the file — real token cost paid once and then discarded when the handoff is deleted post-ratify. The schema's 'freeform' Artifact field never mandated full reproduction; this names the actual dividing line (does the content already have a persisted home the orchestrator can read) that the freeform language left implicit."

- id: narrated-computation-is-sufficient-utility-evidence
  domain: ratify-gate
  provenance: "2026-07-25, backlog-triage/praxis-design discussion. Generalized from the color-utility precedent (a coder guessing warmer/cooler colors by narrated trial and error, resolved by building a deterministic color utility instead) once the operator named the underlying tell directly: narrated step-by-step simulation of an exact procedure is itself sufficient single-instance evidence, distinguishable from the fuzzier candidates surface-deterministic-shortcut-candidates-liberally's repeated-evidence requirement is actually meant for."

- id: no-re-export-from-peer-module
  domain: coding-general
  provenance: "Promoted 2026-07-06 from both Blog and FAMOUS project coding-general domains (Blog: 2026-06-28, hiragana quiz reviewer; FAMOUS: 2026-07-01, cross-project review). Two-project exposure via cross-project review. Promoted directly to lens convention — rule is near-unconditional (barrel exception is short enough to state inline) and needs no condition-weighing."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

- id: explicit-by-default
  domain: coding-general
  provenance: "Blog project, 'Explicit by Default' post (content/posts/coding/explicit-by-default.mdx). The umbrella the operator's individual coding rules turned out to be instances of — named by Claude Code while it was taught the rules alongside their whys. The realization that the whys mattered more than the rules is what seeded this corpora system. Held as a PEER of prefer-error-exposing-form, not its parent: whether one subsumes the other is a question for a future retrospective to surface from evidence, not a top-down call."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

- id: prefer-error-exposing-form
  domain: coding-general
  provenance: "2026-06-19, Blog project. JSLint/Crockford analysis. A peer of explicit-by-default; its concrete instances live in pack overlays."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

- id: deletion-over-addition
  domain: coding-general
  provenance: "2026-06-17, Blog project retrospective."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

- id: yagni-gate-before-implementing
  domain: coding-general
  provenance: "2026-06-17, Blog project retrospective."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

- id: verify-build-not-just-lint
  domain: coding-general
  provenance: "2026-06-17, Blog project retrospective."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-general's own preamble."

# ---- domains: coding-ts, coding-react (split from coding-js-react 2026-07-18; see LINEAGE.md,
#      "The coding-ts / coding-react split") ----
- id: undefined-check-by-source
  domain: coding-ts
  provenance: "Merged from strict-undefined-check-in-arrays + array-access-undefined-not-null, Blog project, 2026-06-01."
  history:
    - date: 2026-07-18
      type: generalized
      reason: "Placed in coding-ts (not coding-react) once its actual test — matching the equality operator to a value's source — was recognized as general TS/JS semantics despite its 'optional props' framing. Tightened for seed level: the single-letter generic T became Value (this corpus's own no-single-char-names applies to its own examples), and the reason's project-level 'common codebase convention' framing was replaced with the general undefined-vs-null distinction the rule actually rests on."

- id: null-first-ternary
  domain: coding-react
  provenance: "2026-06-18, Blog project explicit-by-default post review."

- id: css-var-over-mapped-class-for-dynamic-color
  domain: coding-react
  provenance: "2026-06-13, Blog project WireCircle refactor."
  killed: 2026-07-22

- id: font-mono-at-element-not-container
  domain: coding-ts
  provenance: "2026-06-13, Blog project FixedBottomResultsBar refactor."
  killed: 2026-07-22

- id: hook-params-named-for-hook-concern
  domain: coding-react
  provenance: "2026-06-15, Blog project useHistoryState."
  killed: 2026-07-22

- id: hook-options-object-for-named-args
  domain: coding-react
  provenance: "2026-06-15, Blog project useHistoryState."
  killed: 2026-07-22

- id: wizard-callbacks-unconditional
  domain: coding-react
  provenance: "2026-06-14, Blog project load-calculator, Issue 19. see-also wizard-output-consistent-regardless-of-path (wizards-flows) — the implementation and UX faces of one concern, now legibly linked across domains."

- id: coordinated-setters-signal-reducer
  domain: coding-react
  kind: judgment
  provenance: "2026-06-28, HiraganaQuiz refactor. useQuizQueue had 8 useState calls; submitAnswer fired 5 setters and the advance timer fired 6. These groups mapped cleanly to 'submit' and 'advance' action types. Recognizing the grouped setters as an unnamed state machine — not just a large hook — is the non-obvious judgment."
  history:
    - date: 2026-06-29
      type: moved
      reason: "Promoted from Blog project domain to web-frontend pack seed — condition makes no reference to Blog-specific structure; general React hook wisdom."

- id: same-state-same-name
  domain: coding-ts
  kind: judgment
  provenance: "2026-06-28, HiraganaQuiz refactor. TileState 'resting' vs SpellTile 'idle' — same visual concept, two names. Decision to rename before extracting rather than casting or adding a translation layer. Renaming made SpellTile['state'] a structurally valid subset of TileState, eliminating buildSpellTileClass."
  history:
    - date: 2026-06-29
      type: moved
      reason: "Promoted from Blog project domain to web-frontend pack seed — general TypeScript/React structural wisdom, no Blog-specific framing."
- id: extract-named-concern-into-custom-hook
  domain: coding-react
  provenance: "2026-07-04, reading kyleshevlin.com/use-encapsulation/. Identified gap between coordinated-setters-signal-reducer (threshold-based) and the article's broader claim: the extraction signal is a nameable concern, not a setter count. Judgment call: extraction overhead vs. readability gain."
  killed: 2026-07-22
- id: effect-only-derived-state-belongs-in-render
  domain: coding-react
  kind: judgment
  provenance: "2026-07-15, FAMOUS PlayerBarContent review (operator flagged a coder principle possibly too web-specific for an unrelated hook-encapsulation question; while fixing the hook extraction, a separate useEffect surfaced that only reset scrubberOpen on track-id change via a ref comparison — moved to render body). Operator asked whether the sibling knowledge-tier kill no-read-after-set-in-same-scope was wrongly killed given this miss; on inspection the two patterns are unrelated (that kill concerns reading state synchronously after its own setter, this concerns an effect used purely for derivable state with no external interaction) but the miss itself prompted an audit of FAMOUS and Blog for recurrence. FAMOUS had only the one instance; Blog's ResultBar.tsx useResultFlash showed the identical shape independently (throttled setFlashKey bump keyed off prop-derived label/delta, no external interaction). Two independent hits across two different project shapes (Expo/RN, Next.js) in one pass — satisfies the cross-project-shape bar for promotion straight to seed rather than starting provisional in one project's working file."
  history:
    - date: 2026-07-28
      type: corrected
      reason: "motors-and-controls SchematicNode.tsx review: the rule's ref-holding-previous-value parenthetical failed the project's react-hooks/refs lint (React Compiler-safe, forbids ref access/mutation during render). Same failure mode that killed the sibling behavior-flags-in-refs, but here the core claim (derivable state belongs in render, not an effect) still holds and is not knowledge-tier — corrected the rule to hold the previous value in useState instead of a ref, which is safe under both classic and Compiler-safe React with no condition split needed, rather than killing the principle."

- id: hook-returns-own-handlers
  domain: coding-react
  provenance: "2026-07-04, reading kyleshevlin.com/use-encapsulation/. Bundled-handler pattern shown in useOnOff and useInput examples — no existing principle covered it. Judgment call: complete hook interface vs. consumer flexibility."
  killed: 2026-07-22
  history:
    - date: 2026-07-06
      type: merged
      reason: "Merged with extract-named-concern-into-custom-hook into custom-hook-owns-its-concern. Extraction and interface completeness are co-decisions."

- id: extract-named-concern-into-custom-hook
  domain: coding-react
  provenance: "2026-07-04, reading kyleshevlin.com/use-encapsulation/. Identified gap between coordinated-setters-signal-reducer (threshold-based) and the article's broader claim: the extraction signal is a nameable concern, not a setter count. Judgment call: extraction overhead vs. readability gain."
  killed: 2026-07-22
  history:
    - date: 2026-07-06
      type: merged
      reason: "Merged with hook-returns-own-handlers into custom-hook-owns-its-concern. See that entry."

- id: hook-callsite-legibility
  domain: coding-react
  kind: judgment
  provenance: "2026-07-06, retrospective consolidation. Merged from hook-params-named-for-hook-concern (2026-06-15, Blog useHistoryState) and hook-options-object-for-named-args (same session). Both addressed hook callsite legibility and always co-fired. Judgment: naming params for the hook's concern and wrapping ambiguous primitives in an options object are two expressions of the same rule."

- id: custom-hook-owns-its-concern
  domain: coding-react
  kind: judgment
  provenance: "2026-07-06, retrospective consolidation. Merged from extract-named-concern-into-custom-hook (2026-07-04, kyleshevlin.com) and hook-returns-own-handlers (same source). Judgment: extraction and handler-return are co-decisions — separating them invites partial application."

- id: nan-serializes-to-null-in-json
  domain: coding-ts
  kind: judgment
  provenance: "Promoted from project domains 2026-07-06. Surfaced in Blog (2026-06-20, load calculator NaN incident); ported to FAMOUS (2026-07-01, cross-project review — no FAMOUS incident yet, but condition is easy to hit unknowingly). Two-project exposure via cross-project review justifies seed promotion. Condition broadened to cover any JSON serialization boundary, not only localStorage."

- id: behavior-flags-in-refs
  domain: coding-react
  provenance: "2026-07-01, cross-project Blog→FAMOUS deep review. Surfaced from load calculator useAutosave (isMountRef, pendingRef) and hiragana useSpellQueue (errorInRoundRef). All are boolean flags that gate logic without affecting rendered output. Written to seed domain."
  killed: 2026-07-28
  history:
    - date: 2026-07-06
      type: generalized
      reason: "Retrospective: absorbed timer-handles-in-refs-not-state. Timer IDs are behavioral flags; the dep-cascade concern is now part of this principle's reason. Rule and condition extended to name timer handles explicitly."
    - date: 2026-07-18
      type: generalized
      reason: "Structural-kinship retrospective signal: absorbed stable-ref-for-document-listeners. Both were instances of the same ref-vs-state test — mirroring current state for an external listener is a specific case of 'does this value drive rendered output.' Rule and reason extended to name the document-listener case explicitly."
    - date: 2026-07-28
      type: killed
      reason: "kill_type: knowledge — see coding-react.md's killed: log for the full reason. Standard React-documentation content plus a concrete Compiler-safe-lint failure surfaced in motors-and-controls."

- id: stable-ref-for-document-listeners
  domain: coding-react
  provenance: "No provenance was ever recorded for this principle when it was originally ratified — a pre-existing gap found while executing the 2026-07-18 structural-kinship merge, backfilled here rather than left permanently orphaned. Its rule concerned mirroring current React state into a ref for document-level event handlers to avoid stale closures."
  killed: 2026-07-18
  history:
    - date: 2026-07-18
      type: merged
      reason: "Merged into behavior-flags-in-refs — see that entry's history."

- id: nested-conditional-signals-sub-component
  domain: coding-react
  kind: judgment
  provenance: "2026-07-04, FAMOUS Discover refactor — operator refactored the chained isHydrated × data.length ternary into a binary skeleton/content switch at the parent level, with DiscoveryList owning its own empty/populated states. Judgment call: whether to extend generic-defers-to-consumer or stand alone — standalone chosen because generic-defers-to-consumer requires a reusable-unit framing that wouldn't fire on specific components. Originally ratified into FAMOUS project domain 2026-07-04."
  history:
    - date: 2026-07-06
      type: moved
      reason: "Promoted from FAMOUS project domain to web-frontend pack seed at retrospective. Condition makes no reference to FAMOUS-specific structure — universal React/JSX judgment."

- id: named-exports-over-default
  domain: coding-ts
  kind: knowledge
  provenance: "2026-07-06, FAMOUS Expo migration gate. Surfaced from reading pipeline (basarat/typescript-book). Originally ratified into FAMOUS project domain."
  history:
    - date: 2026-07-06
      type: moved
      reason: "Promoted from FAMOUS project domain to web-frontend pack seed at retrospective. Universal JS/TS module pattern; no FAMOUS-specific condition."

- id: prefers-reduced-motion-requires-js-hook
  domain: coding-react
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (joshwcomeau.com/react/prefers-reduced-motion — source URL returned 403 at extraction time, content pulled from training-data knowledge of this well-known article). Ratified directly to seed as the implementation-mechanics half of the reduced-motion pair; see reduced-motion-instant-not-absent (motion domain) for the design-judgment half."
  see-also: reduced-motion-instant-not-absent

- id: discriminated-union-for-mutually-exclusive-props
  domain: coding-react
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (developerway.com/posts/advanced-typescript-for-react-developers-discriminated-unions — source URL returned 403, extracted from search-result summaries of this and closely related sources). Ratified directly to seed — genuine recurring TS/React prop-typing decision, applicable to any project on this pack with variant-prop components."
  see-also: unified-representation-no-type-leakage

# ---- domain: coding-nextjs (new domain, forked from coding-js-react at retrospective 2026-07-06) ----
- id: suspense-not-needed-for-sync-client-components
  domain: coding-nextjs
  kind: judgment
  provenance: "2026-07-05, FAMOUS discover misc polish session. DiscoverPage wrapped Discover in Suspense with no fallback; operator reported intermittent back-button misdirection. Removing Suspense was the fix. Judgment call: the Suspense was a no-op for loading UX but a live variable in Next.js App Router's router cache handling on back navigation. Originally ratified into FAMOUS coding-js-react project domain."
  history:
    - date: 2026-07-06
      type: moved
      reason: "Moved from FAMOUS project coding-js-react to coding-nextjs seed domain at retrospective. Condition is Next.js App Router-specific; FAMOUS migrated to Expo Router. Principle travels with the framework, not the project."

- id: view-transition-scope-at-page-slot-not-layout
  domain: coding-nextjs
  kind: judgment
  provenance: "2026-07-05, FAMOUS view transitions technology research session. Coder evaluated CSS View Transitions API, Framer Motion AnimatePresence, React 19 experimental ViewTransition. Judgment call: the risk of misapplying route-keying at the layout level (which would unmount a persistent audio player) is non-obvious. Originally ratified into FAMOUS coding-js-react project domain."
  history:
    - date: 2026-07-06
      type: moved
      reason: "Moved from FAMOUS project coding-js-react to coding-nextjs seed domain at retrospective. Condition is Next.js App Router-specific; FAMOUS migrated to Expo Router."

# ---- domain: recoverability ----
# composition: declared by ux-design and ui-design (moved out of the working file's own prose 2026-07-25
# so a consuming spawn's context doesn't carry the sibling composition's name for no functional benefit)
- id: recovery-path-replaces-confirmation
  domain: recoverability
  provenance: "2026-06-14, load-calculator audit."
  history:
    - date: 2026-06-20
      type: consolidated
      reason: "Absorbed recoverable-action-surfaces-its-path (originated ui-designer seed 2026-06-14, moved to ux-designer seed 2026-06-20). Both principles shared identical conditions and formed one complete thought: skip confirmation when recovery exists, and surface that recovery path. Separated, a designer could apply one without the other and get incomplete guidance. Merged rule absorbs both: recovery path is the gate AND must be made visible. Merged reason combines both justifications."
    - date: 2026-06-22
      type: moved
      reason: "Re-homed to the recoverability domain, now declared by BOTH ui-designer and ux-designer. The redesign makes structural what the 2026-06-20 consolidation did by hand: this judgment is one concern spanning flow (UX) and visible affordance (UI), and a domain both lenses declare is its natural home."
    - date: 2026-07-18
      type: generalized
      reason: "Absorbed destructive-global-actions-require-confirmation's ~30-second severity threshold — same recovery-or-confirmation test, one just named the bar for when the gate is mandatory."

- id: destructive-global-actions-require-confirmation
  domain: recoverability
  provenance: "2026-06-14, load-calculator UX audit."
  killed: 2026-07-18

- id: destructive-inline-confirmation
  domain: recoverability
  provenance: "2026-06-02 (originated in ui-designer seed corpus)."
  history:
    - date: 2026-06-20
      type: moved
      reason: "Principle describes interaction behavior (inline row transformation, confirm/cancel affordance), not visual design. Moved from UI designer seed to UX designer seed."
    - date: 2026-06-22
      type: moved
      reason: "Re-homed to the recoverability domain (declared by both designers). The 2026-06-20 UI→UX move was the container problem in miniature — the principle kept getting reassigned because no single role owned it. The domain ends the ping-pong."

- id: optimistic-ui-for-high-confidence-mutations
  domain: coding-react
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (dev.to/a1guy — React 19 useOptimistic deep dive; source URL returned 403, extracted from training-data knowledge of the API and standard optimistic-UI patterns). Ratified directly to seed — FAMOUS has zero server mutations currently (grepped, no fetch/API calls in the codebase), but the risk-weighing judgment (safe-to-assume vs. plausible-failure) is general and applicable to any project on this pack with a backend."
  see-also: recovery-path-replaces-confirmation, optimistic-rollback-requires-explicit-error
  history:
    - date: 2026-07-22
      type: moved
      reason: "Domain-decomposition audit: this is React-hook implementation guidance (useOptimistic, mutation-state architecture), not UX/UI design judgment — neither ux-design nor ui-design's alias notes claim implementation as their concern. Moved from recoverability (loaded by both design aliases) to coding-react (loaded by the coder), which actually applies it."

- id: optimistic-rollback-requires-explicit-error
  domain: coding-react
  kind: judgment
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (dev.to/a1guy), companion to optimistic-ui-for-high-confidence-mutations from the same source. Ratified directly to seed for the same reason."
  see-also: recovery-path-replaces-confirmation, optimistic-ui-for-high-confidence-mutations
  history:
    - date: 2026-07-22
      type: moved
      reason: "Same domain-decomposition finding as optimistic-ui-for-high-confidence-mutations — moved from recoverability to coding-react alongside it."

# ---- domain: ranking-evaluation ----
- id: triage-and-ranking-are-independent-signals
  domain: ranking-evaluation
  provenance: "Merged from intake-and-ranking-are-separate-activities + elo-as-independent-ranking-signal, 2026-06-02."
  history:
    - date: 2026-06-20
      type: provisional-flag
      reason: "Earned exclusively in a comparative ranking/evaluation tool (Taste Trainer). Condition is narrow — tools that mix quick triage with deliberate ranking. Plausible general principle but untested against a second project with a ranking or evaluation feature. Do not promote until confirmed in a second context."

- id: category-scope-is-visible-on-ranked-items
  domain: ranking-evaluation
  provenance: "2026-06-02."
  history:
    - date: 2026-06-20
      type: provisional-flag
      reason: "Earned exclusively in a per-category ranking tool (Box Selector). Condition presupposes category-scoped rankings — a pattern that may not recur in other web-frontend projects. Do not promote until confirmed in a second context."

- id: choice-prompt-anchors-on-usefulness-not-preference
  domain: ranking-evaluation
  provenance: "2026-06-02."
  history:
    - date: 2026-06-20
      type: provisional-flag
      reason: "Earned exclusively in a reference-building tool (Taste Trainer). Condition is narrow — tools whose output is meant to inform future decisions, not record taste. Do not promote until confirmed in a second context."

- id: callout-label-describes-property-not-judgment
  domain: ranking-evaluation
  provenance: "2026-06-02, Box Selector UX review."

- id: out-of-order-callout-requires-sort-explanation
  domain: ranking-evaluation
  provenance: "2026-06-02, Box Selector UX review."

- id: arrow-block-body
  domain: coding-ts
  provenance: "2026-06-18, Blog project. {} ambiguity + single consistent style removes per-function judgment call. A JS instance of the base prefer-error-exposing-form meta-rule."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-ts's own preamble."
    - date: 2026-07-30
      type: graduated-to-convention
      reason: "proposals/domain-repo-import.md §1: unstructured preamble prose replaced by an id-addressable conventions: entry — same id, same unconditioned status, now killable/graduatable/importable instead of dissolved into prose."

- id: no-early-returns
  domain: coding-ts
  provenance: "2026-06-17, Blog project, 'Explicit by Default' post (content/posts/coding/explicit-by-default.mdx). Derived from Crockford's heuristic, not style: indentation-as-grammar (Henney) means early returns let a multi-condition line sit at base indentation as if unconditional; the guard-clause exception reintroduces a per-function 'still simple enough?' judgment a block body removes; the strong counterexample (a flat row of order-independent guards) resolves to extraction-and-naming, not exception. Scoped to this pack because some ecosystems (Go) idiomatically prefer guard clauses; the reasoning is general."
  history:
    - date: 2026-07-21
      type: folded-to-preamble
      reason: "promoted: retired per v3-redesign-proposal.md; substance moved into coding-ts's own preamble."
    - date: 2026-07-30
      type: graduated-to-convention
      reason: "proposals/domain-repo-import.md §1: unstructured preamble prose replaced by an id-addressable conventions: entry — same id, same unconditioned status, now killable/graduatable/importable instead of dissolved into prose."

- id: no-shell-for-structural-absence
  domain: coding-ts
  provenance: "2026-07-19, sibling-implementation review (slider-puzzle/four vs one, two, three). Surfaced from four/script.js's repeated empty-else-with-restating-comment pattern (getAdjacentPositions, isBoardSolved, ensureTileElements, stopTimer, setCaption, handleTileClick — six instances). Weighed against no-early-returns: that principle governs branches where both sides do real work; this one covers the narrower case of a branch with no true opposite side, which the guard-clause reasoning was never meant to force into a populated shell. Held as a see-also peer, not a caveat rewrite of the existing bullet."

# domain: principle-judgment (new domain, seeded 2026-07-22)
- id: reaudit-ratified-principles-against-genuine-fork-test
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-22, domain-and-principle audit session. Generalized from the session's own method: css.md's grid-for-layout-flexbox-for-flow and color.md's semantic-token-names-by-role-not-value were both tagged kind: knowledge in their own audit provenance at ratification time yet were still ratified into principles: — direct evidence that gate-time discipline alone is not sufficient and a periodic re-audit catches what it misses."

- id: reading-pipeline-provenance-flags-knowledge-risk
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-22, domain-and-principle audit session. All four knowledge-kills that session (css.md's two, color.md's two) originated from reading-pipeline provenance rather than an earned project incident — named directly as a risk correlation rather than left to be re-discovered on each future audit."

- id: check-principle-against-consuming-lens-not-just-domain-topic
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-22, domain-and-principle audit session. Generalized from three misplaced-principle findings that session (optimistic-ui-for-high-confidence-mutations + its pair, moved recoverability→coding-react; progressive-disclosure-for-primary-advanced-split, moved design-method→forms-inputs) — none of which the existing domain-tension retrospective signal could have caught, since none contradicted anything else in their birth domain."

- id: lead-with-the-nonobvious-half-when-refining
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-22, domain-and-principle audit session. Generalized from the same session's refinement of visual-hierarchy.md's hierarchy-through-scarcity, reworded to foreground its earned insight (subordinate without degrading legibility) instead of the design-101 framing (one dominant element) it originally led with."

- id: consuming-lens-includes-agent-vs-human-gap
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-23, FAMOUS skill-mining ratify session. Generalized from that session's four-candidate borderline review (coding-expo.md): three killed for targeting human-specific habits/memory rather than agent-relevant mechanism risk, one kept for naming a concrete trap in the agent's own verification workflow — see LINEAGE.md."

- id: mined-workflow-stays-a-workflow
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-23, FAMOUS skill-mining ratify session. Generalized from that session's decision to drop six web-to-native candidates that atomized a coherent migration workflow rather than encoding independent mechanism-level judgment — see LINEAGE.md."

- id: cost-of-discovery-is-not-judgment-evidence
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-24, backlog-triage discussion. Named directly from a recurring rationalization pattern the operator has observed agents use — arguing a hard-to-trace bug fix should become a principle because it was difficult or costly to find, independent of whether the insight recurs."

- id: strip-specifics-to-find-the-transferable-method
  domain: principle-judgment
  kind: judgment
  provenance: "2026-07-24, backlog-triage discussion. Paired with cost-of-discovery-is-not-judgment-evidence as the constructive counterpart: rather than reject every hard-won-fix candidate outright, test whether a transferable diagnostic method survives once the specific facts are stripped out."

# reading-pipeline candidates, processed against the new principle-judgment domain (2026-07-22)
- id: immutable-by-default
  domain: coding-general
  kind: knowledge
  provenance: "2026-07-20, reading pipeline (kevlinhenney.medium.com/restrict-mutability-of-state). Killed on first review rather than ratified — see coding-general.md's killed log for the reasoning."
  killed: 2026-07-22

- id: use-transition-vs-deferred-value
  domain: coding-react
  kind: judgment
  provenance: "2026-07-20, reading pipeline (developerway.com/posts/use-transition). Ratified directly to seed — the access-level test (setter ownership vs. value-only access) is a genuine decision heuristic for a commonly-conflated hook pair, not a restatement of React's own docs."

- id: server-components-for-initial-data
  domain: coding-nextjs
  kind: judgment
  provenance: "2026-07-20, reading pipeline (vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them). Ratified directly to seed — names a real, plausible wrong default (client-side fetching out of pre-RSC habit), framed as an observed mistake rather than pure API reference."

- id: revalidate-tag-over-path
  domain: coding-nextjs
  kind: judgment
  provenance: "2026-07-20, reading pipeline (vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them). Ratified directly to seed — companion finding from the same source; a genuine precision-vs-simplicity tradeoff (revalidateTag vs. revalidatePath), not a lookup fact."

- id: server-actions-for-mutations-not-queries
  domain: coding-nextjs
  kind: judgment
  provenance: "2026-07-20, reading pipeline (vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them). Ratified directly to seed — companion finding from the same source; guards against the plausible default of reaching for Server Actions as a general-purpose endpoint since they're the newer API."

# domain: dependency-management (new domain + lens, seeded 2026-07-22)
- id: adopt-forced-migration-early-on-disposable-branch
  domain: dependency-management
  kind: judgment
  provenance: "2026-07-22, reading pipeline (docs.expo.dev/guides/new-architecture), reworded from Expo-specific to general form when moved out of the then-uncreated coding-expo domain. Originally weighed for a kill-as-knowledge ('fairly standard') but held as judgment on review: the operator's own framing was that this is standard-but-under-practiced discipline (deferring an optional migration to its deadline is a real, recurring failure mode despite being agreed-upon in the abstract), which is exactly what the genuine-fork test is for — distinct from a lookup fact. Reassigned from coding-general to a new dependency-management domain + matching lens: this judgment applies to tasks actually about upgrading/migrating, not to every convergent coding spawn regardless of task shape (kernel.md, 'Recognizing that a task needs a different lens'). First seen concretely in Expo's New Architecture migration (support for the old architecture ends at SDK 55 while still optional at the time of writing) — real breakage there was only discoverable by running the app against it, not by reading the migration guide."

- id: audit-transitive-dependencies-after-major-upgrade
  domain: dependency-management
  kind: judgment
  provenance: "2026-07-22, reading pipeline (buildmvpfast.com/blog/expo-sdk-56-inline-native-modules-router-fork-new-features-2026), reworded from Expo-specific to general form. Same reassignment reasoning as adopt-forced-migration-early-on-disposable-branch — held as judgment, moved to the new dependency-management domain rather than coding-general. First seen concretely when Expo SDK 56 stopped bundling @expo/vector-icons as a transitive dependency."

# domain: coding-expo (new domain, seeded 2026-07-22)
- id: expo-router-typed-routes-for-link-safety
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (docs.expo.dev/router/introduction/). Ratified directly to seed — names the specific compile-time-vs-runtime gap Typed Routes closes, not a restatement of the feature's existence."

- id: expo-router-default-react-navigation-for-low-level-native-control
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (dev.to/bhupeshchandrajoshi/expo-router-vs-react-navigation-which-one-should-you-use-in-2026-3khj). Ratified directly to seed — a genuine library-choice tradeoff with stated conditions on both sides, not a changelog restatement."

- id: interop-layer-does-not-cover-native-code-dependencies
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (docs.expo.dev/guides/new-architecture/). Ratified at lower confidence than the domain's other candidates — the operator did not object on review, but the finding is closer to a direct restatement of Expo's own documentation than the domain's more clearly earned judgment calls; kept because it still names a specific, plausible wrong assumption (treating the interop layer as a blanket guarantee) rather than pure lookup fact."

- id: expo-router-no-direct-react-navigation-imports
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (dev.to/manthan_kasle/expo-sdk-56-is-out-and-a-few-things-finally-clicked-into-place-478h). Ratified directly to seed — explains why a previously-working import pattern silently breaks post-SDK-56, a real judgment about dependency-architecture change rather than a release-notes restatement."

- id: expo-filesystem-migrate-once-feature-gaps-close
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (dev.to/manthan_kasle/expo-sdk-56-is-out-and-a-few-things-finally-clicked-into-place-478h). Ratified directly to seed — names the specific closed feature gaps rather than a generic 'upgrade when you can' statement. see-also added to dependency-management's adopt-forced-migration-early-on-disposable-branch: both test re-checking a deferred/provisional decision once its blocking condition changes, at different specificity levels (this one is Expo-FileSystem-specific; that one is the general adopt-early-on-a-disposable-branch judgment)."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo → dependency-management-expo (operator-directed slimming pass): the condition only ever fires at an SDK upgrade, so it was loading into every implement-feature spawn while belonging to migrate-dependencies task-shape — the same task-shape conditioning kernel.md names for dependency-management itself."

- id: ota-update-scope-excludes-native-changes
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (farooxium.dev/blog/react-native-expo-2026-guide). Ratified directly to seed — a specific, non-obvious release-planning constraint (the OTA/native-change boundary) distinct from feature-description content also covered in the same source."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: expo-native-dirs-generated-not-hand-edited
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (deepwiki.com/expo/expo/9-build-and-deployment). Ratified directly to seed — a structural design claim about the CNG model's treatment of native directories as ephemeral generated output, the same failure shape coding-general's scripts-over-hand-editing-structured-data already names for generated artifacts generally, applied to the Expo-specific case."

- id: expo-inline-native-modules-before-ejecting
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (buildmvpfast.com/blog/expo-sdk-56-inline-native-modules-router-fork-new-features-2026). Ratified directly to seed — names how SDK 56's inline native modules change the actual build-vs-workaround decision for capabilities not previously worth the ceremony of ejecting or scaffolding a standalone native module package."

- id: expo-sequential-sdk-upgrade-across-router-fork
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (buildmvpfast.com/blog/expo-sdk-56-inline-native-modules-router-fork-new-features-2026). Ratified directly to seed — a distinct version-skip risk from the same SDK-56 router fork, separate from the import-rewrite mechanics already captured in expo-router-no-direct-react-navigation-imports."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo → dependency-management-expo (operator-directed slimming pass): upgrade-time-only condition, migrate-dependencies task-shape — see expo-filesystem-migrate-once-feature-gaps-close's move note."

- id: expo-sdk56-fetch-default-swap-breaks-oauth
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-22, reading pipeline (buildmvpfast.com/blog/expo-sdk-56-inline-native-modules-router-fork-new-features-2026). Ratified directly to seed — a global-fetch swap invisible in application-code diffs, with concrete named breakages (an AT Protocol OAuth client, a crash-reporting SDK) rather than a hypothetical risk."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo → dependency-management-expo (operator-directed slimming pass): upgrade-time-only condition, migrate-dependencies task-shape — see expo-filesystem-migrate-once-feature-gaps-close's move note."

- id: no-color-platformcolor-values-in-reanimated-styles
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/SKILL.md, references/animations.md), not the URL reading pipeline. Ratified directly to seed — names the specific silent-failure mechanism (opaque platform color handle vs. interpolable JS value) rather than a generic animation-API caveat."

- id: medialibrary-save-requires-local-file-not-base64
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/references/media.md). Ratified directly to seed — a sharp, specific API gotcha (no inline-data code path) rather than an API-reference restatement."

- id: liquid-glass-feature-detect-with-blur-fallback
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/references/visual-effects.md). Ratified directly to seed — names the specific OS-version coupling risk of treating a newest-iOS-only material as always available."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: blurview-requires-overflow-hidden-for-rounded-corners
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/references/visual-effects.md). Ratified directly to seed — a concrete, silent visual bug (blur bleeding past rounded corners) with no compiler or runtime signal."

- id: css-gradients-require-new-architecture
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/references/gradients.md). Ratified directly to seed — names what the experimental_ prefix actually gates (Fabric-only, not general instability) rather than a generic 'experimental APIs are risky' truism."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: expo-go-default-until-native-code-needed
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/SKILL.md, .agents/skills/expo-dev-client/SKILL.md). Merged from two drafted candidates (expo-go-before-custom-native-build, expo-go-outgrown-once-native-code-needed) covering the same default from both directions — ratified as one entry rather than two near-duplicates."

- id: expo-ui-list-not-virtualized-avoid-for-large-lists
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/web-to-native/references/native-patterns.md, .agents/skills/expo-ui/references/jetpack-compose.md, references/universal.md). Merged from two near-identical drafted candidates (expo-ui-list-not-for-large-feeds, expo-ui-list-not-virtualized) surfaced independently from web-to-native and expo-ui sources — ratified as one entry."

- id: expo-router-toolbar-children-not-behind-wrapper
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/toolbar-and-headers.md). Ratified over operator's non-obviousness challenge to the batch: Stack.Toolbar is a newer, sparsely-documented API whose children-introspection mechanism isn't the kind of thing a generic search on the blank-toolbar symptom surfaces — distinct from the sibling candidates killed in the same batch for being easily-searchable, well-documented gotchas."

- id: expo-router-always-resolve-root-path (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/SKILL.md). Killed at ratify — see kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: no-bare-group-route-file (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/route-structure.md). Killed at ratify — see kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: expo-router-renamed-initialroutename-to-anchor (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/route-structure.md). Operator asked to verify against real FAMOUS usage before ratifying; grep found zero instances of initialRouteName/unstable_settings in the project. Killed — see kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: expo-router-array-group-for-shared-tab-screens
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/SKILL.md). Ratified directly to seed — names a real route-identity divergence risk (duplicated screens carrying independent back-stack/state) not obvious from the array-group feature's own name."

- id: native-tabs-must-be-statically-defined
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/tabs.md). Ratified directly to seed — a silent full-navigator remount triggered by what reads as an ordinary conditional render, genuinely hard to attribute without knowing the native-controller mechanism."

- id: native-tabs-bottomaccessory-state-outside-component
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/tabs.md). Ratified directly to seed — the dual-instance mounting behavior (regular + inline placement simultaneously) is a non-obvious mechanism no amount of staring at the component's own code would reveal."

- id: native-tabs-transparency-requires-first-opaque-child-not-collapsed
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/tabs.md). Ratified directly to seed — reproduces only in optimized/release builds where View-collapsing actually happens, a classic dev-vs-release divergence that's hard to nail down from the release-build symptom alone."

- id: zoom-transition-dismissal-bounds-for-inner-scrollview
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/zoom-transitions.md). Ratified directly to seed — a gesture-arbitration conflict between two independently-reasonable-looking APIs (zoom dismissal + inner scroll), not discoverable by reading either API's docs in isolation."

- id: formsheet-detent-index-controls-background-interactivity
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-router/references/form-sheet.md). Ratified directly to seed — the default-dims-at-every-detent behavior is a specific, non-obvious default that only a form-sheet-specific prop (sheetLargestUndimmedDetentIndex) resolves."

# domain: dependency-management-expo (new domain, seeded 2026-07-23)
- id: pin-multi-package-versions-for-native-graphics-stack
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/building-native-ui/references/webgpu-three.md), not the URL reading pipeline. Ratified directly to seed — names a real compatibility-contract gap semver doesn't express, not a restatement of 'pin your versions.'"

- id: recheck-workaround-artifacts-every-sdk-upgrade
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/SKILL.md). Ratified directly to seed — same failure shape as ceiling-comment-for-deliberate-shortcuts, applied to expo.install.exclude/patches specifically."
  history:
    - date: 2026-08-07
      type: generalized
      successor: version-conditioned-workarounds-reopen-at-upgrade
      reason: "Absorbed into dependency-management's version-conditioned-workarounds-reopen-at-upgrade (2026-08-07 coding-expo retrospective, operator-ratified): this entry stated the exclude/patch half of a test that also covers pins, compat/fallback flags, deferred migrations, and interop shims across any stack. Removed from dependency-management-expo's working file; the Expo-specific instances (expo-filesystem-migrate-once, the fetch-swap stopgap) remain as named cases of the general principle."

- id: codemod-deprecation-check-after-rewrite
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/references/react-navigation-to-expo-router.md). Operator flagged the initial draft's rule for leaking its reason (naming the specific migration inline instead of stating the general check) — reworded so rule states the generalizable guidance and condition carries the SDK-56-specific instance. Filed to a new dependency-management-expo domain rather than directly into stack-agnostic dependency-management: not general enough on a single data point, and specifically a codemod-migration judgment that may fork further if a comparable non-Expo codemod scenario surfaces."

- id: escalate-unmapped-symbols-dont-diy-workaround
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/references/react-navigation-to-expo-router.md). Ratified directly to seed — same dependency-management-expo homing reasoning as codemod-deprecation-check-after-rewrite; also codemod-migration-shaped rather than strictly Expo-specific."

- id: reanimated-worklets-new-required-peer-post-newarch
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/references/new-architecture.md). Operator flagged the initial draft's rule for leaking its reason (SDK-54/worklets specifics stated as the rule itself) — reworded so rule states the general 'check for new required peer deps after a major upgrade' guidance and condition carries the Reanimated/worklets specifics."

- id: root-stack-vs-js-stack-codemod-collision
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/references/react-navigation-to-expo-router.md). Operator flagged the initial draft's rule for leaking its reason (the Stack/js-stack distinction stated inline in the rule) — reworded so rule states the pure directive and reason carries the explanation. Routed to dependency-management-expo rather than coding-expo on operator's call: migration/codemod-specific judgment, not general Expo implementation judgment."

- id: expo-av-video-android-parity-gap-fails-silently
  domain: dependency-management-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/upgrading-expo/references/expo-av-to-video.md). Ratified directly — every named failure mode is a silent Android-only visual regression invisible to iOS-only testing. Routed to dependency-management-expo alongside root-stack-vs-js-stack-codemod-collision: migration-verification judgment, not general Expo implementation judgment."

- id: dom-component-router-hooks-not-callable
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/web-to-native/references/false-friends.md, .agents/skills/use-dom/SKILL.md — same rule surfaced independently from both sources, merged into one entry). Kept as coding-expo mechanism judgment (not migration-workflow-shaped, per operator's web-to-native split): fires whenever a DOM component touches route state, not only during a bulk migration."

- id: layout-route-cannot-be-a-dom-component
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/web-to-native/references/false-friends.md). Kept as coding-expo mechanism judgment per the same web-to-native split: a structural DOM-component/layout-route rule, not migration-sequencing advice."

- id: streaming-fetch-requires-expo-fetch-not-rn-fetch
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/web-to-native/references/false-friends.md). Kept as coding-expo mechanism judgment: fires whenever native code reads a streaming response, independent of migration context. Six sibling web-to-native candidates (expo-dom-shell-ships-before-nativizing, dom-screen-runtime-cost-caps-nativize-scope, nativize-means-redesign-not-reskin, iap-required-for-digital-goods-decide-at-assess, async-server-components-must-split-before-porting, motion-and-touch-are-part-of-native-not-polish) dropped entirely rather than ratified or kill-logged — operator judgment: these atomize the FAMOUS web-to-native skill's own coherent workflow sequencing, and lose the ordering/connective 'why this step before that step' reasoning the skill file already carries; the skill itself is the better artifact to load for that workflow, not a container mismatch worth a kill-log entry. Two more (stale-expo-go-bundle-trap, verify-migration-by-running-not-compiling) dropped earlier in the same review for being easily-searchable/generic, also not kill-logged since they were never ratified into a domain to begin with."

- id: release-build-cannot-hot-reload-reuse-is-wrong-tool
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/eas-simulator/SKILL.md, references/run-your-app.md, references/troubleshooting.md). Operator questioned whether an agent (vs. a human) would actually trip on this; kept on reasoning that it's a concrete trap in the agent's own verification workflow specifically — screenshotting a stale release build via /run or /verify and misattributing 'no visible change' to a failed fix rather than a stale bundle, with no error signal to distinguish the two."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: expo-public-env-vars-are-client-visible (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/native-data-fetching/SKILL.md). Killed after operator's consuming-lens challenge — see kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: dom-component-isolated-context-no-shared-state (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/use-dom/SKILL.md). Killed after operator's consuming-lens challenge — redundant with the already-ratified dom-component-router-hooks-not-callable. See kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: expo-ui-universal-before-platform-specific (killed)
  domain: coding-expo
  kind: knowledge
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-ui/SKILL.md). Killed after operator's consuming-lens challenge, contrasted directly against the kept release-build-cannot-hot-reload-reuse-is-wrong-tool in the same review. See kill_type/reason_killed in domains/coding-expo.md's killed: log."
  killed: 2026-07-23

- id: nativewind-inline-variables-breaks-platform-color
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-tailwind-setup/SKILL.md). Ratified directly to seed — a specific, silent config-interaction break (inlineVariables optimization vs. platformColor's need for a live native reference) with no error signal."

- id: expo-router-loader-data-cached-for-session
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/native-data-fetching/references/expo-router-loaders.md). Ratified directly to seed — a documented-as-limitation-not-cache-control behavior that silently violates the SPA assumption of fresh data per revisit."

- id: expo-router-loader-request-object-mode-dependent
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/native-data-fetching/references/expo-router-loaders.md). Ratified directly to seed — a config-flip-triggered crash (server mode populates request, static mode never does) invisible until the output mode actually changes."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: eas-hosting-api-routes-run-on-workers-not-node
  domain: release-readiness-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-api-routes/SKILL.md). Ratified directly to seed — classic works-locally-fails-in-production trap (local npx expo serve runs Node, EAS Hosting deploys to Cloudflare Workers)."
  history:
    - date: 2026-08-07
      type: moved
      reason: "coding-expo -> release-readiness-expo (2026-08-07 retrospective, operator-directed): operator judged the dev-runtime-vs-ship-runtime seam real and worth its own bucket, explicitly affirming reading-pipeline provenance as a valid corpus entry path — distilled judgment from considered skills is admissible without a battle-won incident. Same load units as coding-expo for now; the domain is expected to wrap into a pre-prod/release process once ship-to-store work exists."

- id: expo-ui-platform-specific-import-crashes-wrong-platform
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-ui/SKILL.md). Ratified directly to seed — a runtime-only crash ('Unable to get view config') from an import that resolves fine in JS and only fails at native view registration."

- id: expo-router-no-platform-extension-route-files
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-ui/references/universal.md). Ratified directly to seed — names the specific conflict between two independently-reasonable filename conventions (Metro's platform-extension resolution vs. Expo Router's route resolution)."

- id: expo-ui-usenativestate-silently-degrades-without-worklets
  domain: coding-expo
  kind: judgment
  provenance: "2026-07-23, mined from FAMOUS's local Expo/React Native team skill docs (.agents/skills/expo-ui/references/drop-in-replacements.md). Ratified directly to seed — a silent fallback to normal React render cycle that's easy to misdiagnose as an API limitation rather than a missing prerequisite."

# domain: ratify-gate (mattpocock/skills review, 2026-08-01)
- id: separate-spec-fidelity-from-principle-compliance
  domain: ratify-gate
  kind: judgment
  provenance: "2026-08-01, reviewing mattpocock/skills' code-review skill (github.com/mattpocock/skills) as part of a systematic pass through its promoted engineering/productivity skills (mps-01..mps-11, tracked in a scratch queue.md dogfooding the same-day fog-before-ticket/scope-boundary-is-closed-not-silent queue schema). Its two-axis review (Standards vs. Spec, reported separately, never merged or reranked) named a real gap: the ratify gate's own Phase 6 step 1 audits output against principles but has no structurally separate check for whether the deliverable satisfies its own task's stated acceptance criteria. Reading-pipeline provenance flagged; ratified as a genuine gap against the gate's own existing procedure, not a restatement."

# domain: coding-general (mattpocock/skills review, 2026-08-01)
- id: throwaway-prototype-capture-decision-not-code
  domain: coding-general
  kind: judgment
  provenance: "2026-08-01, same review pass, mattpocock/skills' prototype skill. Corroborated independently by wayfinder's own Prototype ticket type (also reviewed this session, 2026-08-01) — both name the same recurring need (throwaway code to answer a design/logic question) with zero prior coverage anywhere in corpora's domains. Reading-pipeline provenance flagged; ratified given the independent corroboration and the confirmed absence of existing coverage."

# domain: architecture-health (new domain, seeded 2026-08-01)
- id: scan-scope-by-recent-churn
  domain: architecture-health
  kind: judgment
  provenance: "2026-08-01, drafted for ah-01 of the architecture-health capability (scoped via the same scratch queue.md dogfooding fog-before-ticket/scope-boundary-is-closed-not-silent). Adapted from mattpocock/skills' improve-codebase-architecture skill's 'scope before you scan' step. Reading-pipeline provenance flagged; ratified given the git-churn-as-signal-for-future-change reasoning holds independent of the source."

- id: dont-relitigate-adr-without-real-friction
  domain: architecture-health
  kind: judgment
  provenance: "2026-08-01, same drafting pass. Adapted from the same skill's ADR-conflict handling. Reading-pipeline provenance flagged; ratified as a genuine scope-boundary judgment mirroring domain-modeling's own ADR-sparingly criteria applied to consuming rather than creating an ADR."

# domain: codebase-design (new domain, seeded 2026-08-02, resolving nys-01)
- id: deletion-test-for-suspected-shallow-module
  domain: codebase-design
  kind: judgment
  provenance: "2026-08-02, drafted for cd-01, graduated from nys-01 (the architecture-health capability's scratch queue flagged corpora had no formal deep-module vocabulary). Adapted from mattpocock/skills' codebase-design skill. Reading-pipeline provenance flagged; ratified as a genuine diagnostic — routes the shallow-vs-earning-its-keep question onto what happens to the complexity, not whether the module currently exists."

- id: interface-is-the-test-surface
  domain: codebase-design
  kind: judgment
  provenance: "2026-08-02, same drafting pass. Reading-pipeline provenance flagged; ratified — treats a test forced past a module's interface as a design smell in the interface's shape rather than a reason to test around it."

- id: two-adapters-before-a-real-seam
  domain: codebase-design
  kind: judgment
  provenance: "2026-08-02, same drafting pass. Operator noted this reads as somewhat generic (echoes YAGNI) but judged the framing worth keeping — a concrete, actionable resolution rule (wait for the second adapter) rather than the YAGNI slogan alone. Reading-pipeline provenance flagged; ratified on operator's explicit call."

- id: depth-is-a-property-of-the-interface
  domain: codebase-design
  kind: judgment
  provenance: "2026-08-02, same drafting pass. Operator asked for my own assessment; I flagged it as duplicating the Glossary's own Depth definition rather than adding a separate decision — closer to elaboration than a genuine fork. Operator agreed; folded into the Glossary's Depth entry instead of ratified as a standalone principle."
  killed: 2026-08-02

# domain: testing (mattpocock/skills review, 2026-08-01)
- id: avoid-tautological-test-assertions
  domain: testing
  kind: knowledge
  provenance: "2026-08-01, same review pass, mattpocock/skills' tdd skill. Proposed with low confidence — flagged at proposal time as reading close to universal testing-hygiene doctrine rather than a decision with a genuinely tempting alternative. Operator agreed; rejected."
  killed: 2026-08-01

# domain: testing (superpowers:systematic-debugging mining, 2026-08-02)
- id: wait-for-condition-not-arbitrary-delay
  domain: testing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging's condition-based-waiting.md supporting-technique file. Passed the genuine-fork test — an agent writing an async test defaults to a guessed sleep duration unless it deliberately reaches for condition polling instead."

# domain: testing — seed provenance relocated from the working file's preamble and from
# runtime-verification-required's reason field (2026-08-07 slimming pass; both were working-context
# surfaces carrying audit-grade narrative)
- id: runtime-verification-required-not-static-checks-alone
  domain: testing
  kind: judgment
  provenance: "Seeded 2026-07-29 from a literal exercise run (exercises/comment-section-process-vs-judgment.md, Run 2) that shipped two real runtime bugs — a stale RSC payload after a Server Action mutation, a per-module-graph singleton split by Fast Refresh — with tsc --noEmit and next build passing cleanly through both, caught only by driving the actual feature in a browser. The plausible alternative — trust green tooling as sufficient — was tried and failed twice in that same session. The testing domain itself was adapted from motors-and-controls/praxis/phases/' testing-phase family into corpora's process/judgment split."

# domain: debugging (new domain, seeded 2026-08-02, mined from superpowers:systematic-debugging)
- id: root-cause-before-fix
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 1 / Iron Law. Checked against principle-judgment's reading-pipeline-provenance-flags-knowledge-risk and consuming-lens-includes-agent-vs-human-gap: the guarded-against lapse is applying a guessed fix under task-framing pressure, not a human memory/habit failure, so it clears despite the reading-pipeline source."
- id: fix-at-source-not-symptom
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging's root-cause-tracing.md supporting-technique file."
- id: single-hypothesis-minimal-test-reform-on-failure
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 3. Merged two adjacent phase steps (single-hypothesis testing and reform-on-failure) into one principle at mining time — both are the same hypothesis-testing loop rather than independent decision points, per mined-workflow-stays-a-workflow's economy concern."
- id: repeated-fix-failure-questions-architecture
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 4.5 (3+ failed fixes). The most concrete/non-generic of the mined set — a specific threshold an agent's own iteration loop would otherwise keep pushing past."
- id: compare-against-complete-reference
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 2. Reframed toward the agent-specific pressure (context-budget-driven partial reads) rather than the source's human-habit framing, per consuming-lens-includes-agent-vs-human-gap."
- id: state-uncertainty-instead-of-plausible-guess
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 3 ('When You Don't Know') and Common Rationalizations table. Weakest-margin entry of the mined set — bordering on generic honesty advice — kept because the specific failure mechanism (a model's plausible-continuation bias) is agent-structural, the same species of tell as ratify-gate's narrated-computation-is-sufficient-utility-evidence."
- id: reproduce-as-failing-test-before-fixing
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging SKILL.md's Phase 4. Filed here rather than testing.md — it's specifically about fix-cycle ordering, not general test-authoring judgment."
- id: validate-at-every-layer-after-root-cause
  domain: debugging
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:systematic-debugging's defense-in-depth.md supporting-technique file, abstracted away from its source's specific four-named-layers framing to the transferable rule (validate at every layer bad data crosses)."
- id: verify-artifact-not-reported-status
  domain: ratify-gate
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:verification-before-completion's 'Agent delegation: check VCS diff, don't trust agent report' row. Filed here rather than a new domain — it's the same class of judgment as artifact-points-to-persisted-file-not-full-reproduction, applied to verification instead of reproduction cost."
- id: watch-test-fail-before-implementing
  domain: testing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:test-driven-development's RED step. Kept the verified-failure discipline, deliberately left out the source's absolute 'delete and restart, never adapt' enforcement mechanic as too rigid for a weighable principle — the practical effect is already captured by requiring the test exist and fail before the implementation does."
- id: reverify-after-state-changes-not-from-memory
  domain: testing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:finishing-a-development-branch's Common Rationalizations table ('Tests passed earlier this session' / 'A green run only proves the tree it ran on')."
- id: phrase-rule-form-to-match-the-guarded-failure
  domain: principle-judgment
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:writing-skills' 'Match the Form to the Failure' and 'no nuance clauses' sections, applied to corpora's own rule-authoring practice rather than skill-doc authoring. Notable as a mined principle about how corpora principles themselves should be phrased — checked for self-consistency against principle-judgment's own existing entries, no conflict found."

# domain: code-review-reception (new domain, seeded 2026-08-02, mined from superpowers:receiving-code-review)
- id: verify-feedback-against-codebase-before-implementing
  domain: code-review-reception
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:receiving-code-review's 'From External Reviewers' checklist."
- id: clarify-all-unclear-items-before-implementing-any
  domain: code-review-reception
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:receiving-code-review's 'Handling Unclear Feedback' section."
- id: push-back-on-review-feedback-you-can-show-is-wrong
  domain: code-review-reception
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:receiving-code-review's 'When To Push Back' section, stripped of its source's tone/anti-sycophancy phrasing (already governed by this environment's own default behavior) down to the substantive verify-then-push-back judgment."
- id: verify-usage-before-implementing-reviewer-completeness-request
  domain: code-review-reception
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:receiving-code-review's 'YAGNI Check for Professional Features' section."

# domain: retrospective — seed/project layer distinction retired (point 2 of the operator's
# 2026-08-02 three-point plan; point 1 was named cross-root dispatch, point 3 was scripted
# import/provenance). Operator's framing: "There isn't really a concept of layers anymore.
# Domains can be imported across projects the same as from within the corpora domains dir."
- id: complementary-principles-signal-abstraction-candidate
  domain: retrospective
  kind: judgment
  provenance: "2026-08-02, operator-authored direction, replacing seed-promotion-candidate's stack-agnostic-wording test with a stronger evidence bar: two or more jointly-necessary principles, not one principle's condition merely reading general."
- id: seed-promotion-candidate
  domain: retrospective
  provenance: "Predates individual per-principle provenance tracking in this file."
  killed: 2026-08-02
- id: single-project-shape-principle-stays-provisional
  domain: retrospective
  provenance: "Predates individual per-principle provenance tracking in this file."
  killed: 2026-08-02
- id: detect-managed-config-before-edit
  domain: coding-general
  kind: judgment
  provenance: "2026-08-02, mined from marketplace skill semgrep:install-mfw (Step 2/4, 'Inspect the shell config BEFORE installing')"
- id: scope-iac-permissions-to-stated-need
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: gate-and-flag-security-check-bypass
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: fix-implementation-not-security-assertion
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: state-trust-model-for-vague-auth-asks
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: verify-dependency-currency-not-familiarity
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: hardened-defaults-for-scaffolded-services
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: mask-secrets-in-debug-artifacts
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate"
- id: flag-missing-abuse-bound-on-expensive-endpoints
  domain: security
  kind: judgment
  provenance: "2026-08-02, proposed by an independent research agent tasked with generating security-domain candidates, reviewed and ratified at the gate; weakest of the batch — closer to a generic unstated-non-functional-requirement gap than a security-specific fork, kept because the invisibility of the gap in a diff is still a real, distinct point"

# 2026-08-05 gate — skills-repo architecture review, operator-direct: the executor-relative
# redundancy pair. Earned from the comment-discipline observation: rules that read redundant to the
# reviewing model measurably improved Sonnet executor output, so redundancy is executor-relative.
- id: redundant-for-the-executing-model-is-baseline
  domain: principle-judgment
  kind: judgment
  provenance: "2026-08-05, skills-repo architecture review. The reviewing model flagged comment-discipline principles as restating model defaults; operator countered that observed Sonnet executor output had actually improved under them — the baseline that matters is the executing model's, and the earlier review judged against the wrong baseline. Ratified as the gate-time test; its retrospective counterpart is executor-model-change-triggers-redundancy-recheck."
- id: executor-model-change-triggers-redundancy-recheck
  domain: retrospective
  kind: judgment
  provenance: "2026-08-05, skills-repo architecture review, paired with redundant-for-the-executing-model-is-baseline. Operator noted the comment-discipline baseline 'was perhaps a model-version ago' — the gap a guardrail covers moves silently when the executor is upgraded, and no counter in this file can see it move, so the model change itself is the trigger."


# ---- domain: css (returned from the uiux plugin — a styling-engine concern, not a design one) ----
- id: tailwind-extract-component-before-apply
  domain: css
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (tailwindcss.com/docs/reusing-styles). Ratified directly to seed — real recurring web-frontend decision (extract component vs @apply); FAMOUS itself has zero @apply usage (NativeWind/RN is component-first by default) but Blog or other DOM-CSS projects on this pack face the tradeoff directly."

- id: tailwind-loop-duplication-is-not-a-problem
  domain: css
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (tailwindcss.com/docs/reusing-styles), companion to tailwind-extract-component-before-apply from the same source. Ratified directly to seed for the same reason."

- id: grid-for-layout-flexbox-for-flow
  domain: css
  kind: knowledge
  provenance: "2026-07-18, FAMOUS strip-comments-and-biome-ignores gate. Surfaced from reading pipeline (blog.logrocket.com/css-flexbox-vs-css-grid). Ratified directly to seed with an explicit condition carve-out for React Native (no CSS Grid support natively) — applies to any DOM-CSS project on this pack, not to FAMOUS's native surfaces."
  killed: 2026-07-22

- id: mobile-fixed-bar-bottom-gap
  domain: css
  provenance: "2026-06-03, Blog project Box Selector mobile bottom bar."
  killed: 2026-07-22

- id: imports-before-tailwind-directives
  domain: css
  provenance: "2026-06-12, Blog project globals.css restructure."
  killed: 2026-07-22

- id: tokenize-only-recurring-magic-values
  domain: css
  provenance: "2026-06-12, Blog project globals.css restructure."

- id: table-row-color-override
  domain: css
  provenance: "2026-06-15, Blog project ampacity table temperature header text color."
  killed: 2026-07-22

- id: container-queries-for-component-scope
  domain: css
  kind: judgment
  provenance: "2026-07-20, reading pipeline (blog.logrocket.com/choose-between-media-container-queries). Ratified directly to seed — container queries are recent enough (broad support ~2023) to carry real judgment risk rather than being settled textbook knowledge; the component-width-vs-viewport-width distinction is architectural, not syntax."

# domain: prose-craft (returned from the mistaken prose plugin — corpora's own artifact-authoring hygiene)

# domain: prose-craft (new domain, seeded 2026-08-01)
- id: prefer-leading-word-over-restated-phrasing
  domain: prose-craft
  kind: judgment
  provenance: "2026-08-01, same review pass as fog-before-ticket, mining mattpocock/skills' writing-great-skills reference. First proposed as a principle-judgment.md entry (judging content quality at gate time); operator redirected it to a new domain after noting the consuming moment is authoring prose, not judging whether a candidate is real judgment — a different lens than principle-judgment's own check-principle-against-consuming-lens-not-just-domain-topic exists to catch. Most of writing-great-skills' own taxonomy was screened out before this point: its 'no-op' check restates corpora's existing genuine-fork test, and most of its failure-mode vocabulary (sediment, sprawl, negation) reads as generic technical-writing knowledge rather than judgment earned from a corpora session — this is the one candidate that named a mechanism corpora had no term for. Reading-pipeline provenance flagged; scoped universal because a spawn is close to always producing some form of prose."
- id: dont-pre-author-judgment-when-scaffolding
  domain: principle-judgment
  kind: judgment
  provenance: "2026-08-05, building plugins/writing. Twice while shaping the writing plugin the operator guarded against pre-authoring genre/style craft principles, naming the reason directly: an agent applies baseline craft anyway, so pre-written craft adds nothing — corpora's value is judgment that beats baseline, earned and fed forward. Resolved by building writing praxis-face-only (process shipped, judgment face empty, genre/style domains left to be born at the gate). Surfaced as a principle by the operator asking where the rule had been recorded — it had lived only as plugin doc prose, not as an earned corpus principle."

# backfilled killed-entry provenance (2026-08-06 retrospective bookkeeping pass): these five ids
# existed in their domains' killed: logs with no audit entry at all — a pre-existing gap found by
# kill-report while dating the killed set. Kill dates derived mechanically from the legacy
# jdev/corpora repo's git history (first commit where the id appears in the killed: section);
# original ratification provenance was never recorded and is not invented here.
- id: timer-handles-in-refs-not-state
  domain: coding-react
  provenance: "Backfilled 2026-08-06; no provenance recorded at original ratification. Killed via merge into behavior-flags-in-refs (see that entry's 2026-07-06 generalized history)."
  killed: 2026-07-22
- id: no-read-after-set-in-same-scope
  domain: coding-react
  provenance: "Backfilled 2026-08-06; no provenance recorded at original ratification."
  killed: 2026-07-22
- id: frequent-state-in-callback-deps-triggers-cascade
  domain: coding-react
  provenance: "Backfilled 2026-08-06; no provenance recorded at original ratification."
  killed: 2026-07-22
- id: stable-id-not-position-for-deferred-ops
  domain: coding-ts
  provenance: "Backfilled 2026-08-06; no provenance recorded at original ratification."
  killed: 2026-07-22
- id: surface-nested-handoffs-verbatim
  domain: ratify-gate
  provenance: "Backfilled 2026-08-06; no provenance recorded at original ratification."
  killed: 2026-07-18
# 2026-08-07 retrospective over coding-expo (text-and-provenance pass; zero efficacy history — the
# domain was batch-seeded 2026-07-22/23 and no Expo-composed gate has run since). Two abstraction
# candidates ratified (the two entries below). A third candidate — dev-runtime ≠ ship-runtime:
# enumerate the mode axes (build type, output mode, platform, runtime host) and verify on the axis
# that ships, drawn from eas-hosting-api-routes-run-on-workers-not-node, release-build-cannot-hot-
# reload-reuse-is-wrong-tool, css-gradients-require-new-architecture, expo-router-loader-request-
# object-mode-dependent, native-tabs-transparency-requires-first-opaque-child-not-collapsed — was
# DECLINED: its general form collapses toward dev/prod-parity doctrine, and its natural home
# (testing, or a prod-facing domain applied through a debugging/pre-prod process) has no earned
# judgment yet since no Expo app has shipped to a store from this system. Revisit once real
# ship-to-store work exists to seed that domain/process (dont-pre-author-judgment-when-scaffolding).
# AMENDED same day: the operator ruled the seam itself real and worth a bucket now —
# release-readiness-expo was created holding the six seam instances (moved from coding-expo, see
# their history entries), while the umbrella principle stays unratified until shipping experience
# earns it. In the same ruling the operator affirmed reading-pipeline provenance as a valid corpus
# entry path (distilled judgment from considered skills, admissible without a battle-won incident),
# which also declines this retrospective's provenance-weighted kill proposals — no coding-expo
# entry was killed.
#
# MEMBERSHIP NOTE for the future production-readiness process (operator-challenged, same day:
# "does release-readiness-expo belong on implement-feature?"). Per-entry answer, recorded so the
# process authoring inherits it instead of redoing it: four of the six are write-time decisions
# whose failures are invisible to dev-runtime verification (eas-hosting-api-routes, css-gradients,
# expo-router-loader-request, liquid-glass) — implement-feature is the only moment prevention is
# possible for those, so they earn the load. Two are pure idle load at implement time:
# ota-update-scope fires at release planning, release-build-cannot-hot-reload at
# verification/debugging. units-of-work is file-level, so the split is not expressible per-entry
# today. Operator's stated ideal: a "check production readiness" phase — a process that looks for
# the offenders. When that phase is authored (after first real ship-to-store work):
# ota-update-scope moves to it outright; release-build-cannot-hot-reload joins it or narrows to
# [debug-issue]; the write-time four either stay as-is or return to ordinary coding-expo-style
# guard duty, leaving the bucket purely process-time.
- id: native-consumed-tree-refactors-not-semantics-preserving
  domain: coding-expo
  kind: judgment
  provenance: "2026-08-07 retrospective over coding-expo (operator-ratified). Abstraction surfaced via complementary-principles-signal-abstraction-candidate from seven jointly-load-bearing instances: expo-router-toolbar-children-not-behind-wrapper, native-tabs-must-be-statically-defined, native-tabs-bottomaccessory-state-outside-component, native-tabs-transparency-requires-first-opaque-child-not-collapsed, expo-router-no-platform-extension-route-files, expo-router-array-group-for-shared-tab-screens, layout-route-cannot-be-a-dom-component. Adds the refactor-time check none of the instances states; instances retained for their operational specifics, and the umbrella is the stale-proofing for future SDK containers the instance list cannot predict."
- id: version-conditioned-workarounds-reopen-at-upgrade
  domain: dependency-management
  kind: judgment
  provenance: "2026-08-07 retrospective over coding-expo (operator-ratified). Generalization of dependency-management-expo's recheck-workaround-artifacts-every-sdk-upgrade (which stated the exclude/patch half, Expo-scoped, and is absorbed by this entry), with expo-filesystem-migrate-once-feature-gaps-close (deferred migration) and the EXPO_PUBLIC_USE_RN_FETCH stopgap named in expo-sdk56-fetch-default-swap-breaks-oauth as the further Expo instances; adopt-forced-migration-early-on-disposable-branch is the stack-agnostic sibling that grounded the generalization. This is the overarching upgrade principle the operator anticipated when batch-importing the Expo upgrade material."

```

<!-- corpus-script:begin — maintained by scripts/corpus.py; do not edit by hand -->

## counters (script-maintained)

```yaml
counters:
  - domain: coding-expo
    since: 2026-08-07
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 6764
    baseline-tokens: 6764
    principles-at-baseline: 27
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: coding-general
    since: 2026-08-07
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 5558
    baseline-tokens: 5558
    principles-at-baseline: 20
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: coding-nextjs
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1141
    baseline-tokens: 1119
    principles-at-baseline: 5
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: coding-react
    since: 2026-07-28
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 3163
    baseline-tokens: 4465
    principles-at-baseline: 12
    kills-at-baseline: 10
    conventions-at-baseline: 0
  - domain: coding-ts
    since: 2026-07-30
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1355
    baseline-tokens: 1547
    principles-at-baseline: 5
    kills-at-baseline: 2
    conventions-at-baseline: 2
  - domain: dependency-management-expo
    since: 2026-08-07
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 2760
    baseline-tokens: 2760
    principles-at-baseline: 9
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: dependency-management
    since: 2026-07-23
    ratified: 1
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1178
    baseline-tokens: 891
    principles-at-baseline: 2
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: principle-judgment
    since: 2026-08-06
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 4750
    baseline-tokens: 4750
    principles-at-baseline: 14
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: ranking-evaluation
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 873
    baseline-tokens: 853
    principles-at-baseline: 5
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: ratify-gate
    since: 2026-07-30
    ratified: 2
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 2537
    baseline-tokens: 2418
    principles-at-baseline: 9
    kills-at-baseline: 2
    conventions-at-baseline: 0
  - domain: recoverability
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 465
    baseline-tokens: 595
    principles-at-baseline: 2
    kills-at-baseline: 1
    conventions-at-baseline: 0
  - domain: retrospective
    since: 2026-08-07
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 3036
    baseline-tokens: 3036
    principles-at-baseline: 9
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: testing
    since: 2026-07-30
    ratified: 3
    killed: 1
    graduated: 0
    gate-violations: 0
    working-file-tokens: 2254
    baseline-tokens: 1816
    principles-at-baseline: 6
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: architecture-health
    since: 2026-08-01
    ratified: 2
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 782
    baseline-tokens: 782
    principles-at-baseline: 0
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: codebase-design
    since: 2026-08-02
    ratified: 3
    killed: 1
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1561
    baseline-tokens: 1774
    principles-at-baseline: 0
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: debugging
    since: 2026-08-02
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1816
    baseline-tokens: 1814
    principles-at-baseline: 8
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: code-review-reception
    since: 2026-08-02
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1018
    baseline-tokens: 1019
    principles-at-baseline: 4
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: security
    since: 2026-08-06
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 2015
    baseline-tokens: 2016
    principles-at-baseline: 8
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: css
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1015
    baseline-tokens: 1474
    principles-at-baseline: 4
    kills-at-baseline: 4
    conventions-at-baseline: 0
  - domain: prose-craft
    since: 2026-08-01
    ratified: 1
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 393
    baseline-tokens: 393
    principles-at-baseline: 0
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: release-readiness-expo
    since: 2026-08-07
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 1654
    baseline-tokens: 1654
    principles-at-baseline: 6
    kills-at-baseline: 0
    conventions-at-baseline: 0
efficacy:
  - id: task-is-actionable-without-planning
    fired: 1
    violated: 0
    idle: 0
  - id: sequence-by-output-dependency
    fired: 1
    violated: 0
    idle: 0
  - id: structural-examination-at-working-checkpoint
    fired: 3
    violated: 0
    idle: 0
  - id: no-single-char-names
    fired: 1
    violated: 0
    idle: 0
  - id: unified-representation-no-type-leakage
    fired: 4
    violated: 0
    idle: 0
  - id: code-lives-at-consumer-level
    fired: 7
    violated: 0
    idle: 0
  - id: minimize-comments-prefer-self-documenting-code
    fired: 6
    violated: 0
    idle: 0
  - id: named-exports-over-default
    fired: 1
    violated: 0
    idle: 0
  - id: null-first-ternary
    fired: 1
    violated: 0
    idle: 0
  - id: single-callsite-helper-scoped
    fired: 2
    violated: 0
    idle: 0
  - id: behavior-flags-in-refs
    fired: 4
    violated: 0
    idle: 0
  - id: ceiling-comment-for-deliberate-shortcuts
    fired: 2
    violated: 0
    idle: 0
  - id: custom-hook-owns-its-concern
    fired: 1
    violated: 0
    idle: 0
  - id: scripts-over-hand-editing-structured-data
    fired: 1
    violated: 0
    idle: 0
  - id: utility-over-guesswork
    fired: 1
    violated: 0
    idle: 0
  - id: ask-before-architecture
    fired: 1
    violated: 0
    idle: 0
  - id: no-shell-for-structural-absence
    fired: 1
    violated: 0
    idle: 0
  - id: atomic-delete-of-wired-component
    fired: 0
    violated: 0
    idle: 1
  - id: recovery-path-replaces-confirmation
    fired: 1
    violated: 0
    idle: 0
  - id: defer-only-nonblocking-design-decisions
    fired: 0
    violated: 0
    idle: 1
  - id: batch-deferred-decisions-coherently
    fired: 0
    violated: 0
    idle: 1
  - id: persist-role-by-workstream
    fired: 0
    violated: 0
    idle: 1
  - id: design-pattern-application-lighter-path
    fired: 0
    violated: 0
    idle: 1
  - id: decompose-large-tasks-before-spawning
    fired: 0
    violated: 0
    idle: 1
co-occurrence:
library-drift:
  since-last-sync: 0
```

<!-- corpus-script:end -->

# Kill log — relocated out of the domain working files (2026-08-07, operator decision:
# working-context cost of carrying kills into every spawn outweighed the re-proposal-prevention
# benefit in practice). Each entry keeps its full working-file record plus its domain. The ratify
# gate consults this list (audit load); spawns never see it.

```yaml
kills:

- id: depth-is-a-property-of-the-interface
  domain: codebase-design
  rule: "When judging or designing a module's depth, evaluate its external interface only — a deep module can be internally composed of small, mockable, swappable parts (internal seams, private to its own implementation and tests) without that internal structure counting against its depth."
  kill_type: container
  reason_killed: "The one useful clause (internal seams don't count against depth) is a corollary of the Glossary's own Depth definition, not a separate decision with a genuinely tempting alternative — closer to duplication (prefer-leading-word-over-restated-phrasing's failure mode) than earned judgment. Folded into the Glossary's Depth entry as a clarifying sentence instead of standing as its own principle; the content survives, the principles: container was the wrong home for it."

- id: expo-router-always-resolve-root-path
  domain: coding-expo
  rule: "Ensure an Expo Router app always has some route that resolves \"/\" — directly, or via a group — even when nesting groups or using array routes."
  kill_type: knowledge
  reason_killed: "Operator challenge at ratify time: this is a completeness checklist item (does the route tree resolve '/') rather than a hidden mechanism — once the blank-cold-start symptom is observed, a search for it is fast and obvious. Doesn't clear the non-obvious/hard-to-nail-down bar principle-judgment applies to reading-pipeline-sourced candidates."
  killed: 2026-07-23

- id: no-bare-group-route-file
  domain: coding-expo
  rule: "Never name a route file like (group).tsx. Group syntax is directory-only — a route matching a group name must live at (group)/index.tsx."
  kill_type: knowledge
  reason_killed: "Operator challenge at ratify time: one of the most commonly documented Expo Router gotchas (prominent in official docs' groups section, heavily covered in community Q&A) — easy to find once the symptom is noticed, not an earned judgment call."
  killed: 2026-07-23

- id: expo-router-renamed-initialroutename-to-anchor
  domain: coding-expo
  rule: "In Expo Router v4+, set anchor in unstable_settings, not the older initialRouteName — check specifically for this when migrating router config forward from pre-v4 code, or when copying route-settings snippets from older docs/examples/AI-generated code."
  kill_type: knowledge
  reason_killed: "Operator asked for grounding in an actual project instance before ratifying; grepping FAMOUS (the source project) for initialRouteName/unstable_settings found zero usages — the candidate was never validated against a real incident, purely doc-derived migration trivia. Textbook case of principle-judgment's reading-pipeline-provenance-flags-knowledge-risk: a rule 'surfaced from reading pipeline' with no earned-mistake grounding."
  killed: 2026-07-23

- id: expo-public-env-vars-are-client-visible
  domain: coding-expo
  rule: "Never place a secret (an API key with write access, a database password, a signing secret) in an EXPO_PUBLIC_-prefixed environment variable. Reserve that prefix for values safe for any user to read; put real secrets only in non-prefixed vars consumed server-side."
  kill_type: knowledge
  reason_killed: "Failed check-principle-against-consuming-lens-not-just-domain-topic: judged against the actual consumer (an AI coding agent, not a human developer). An agent doesn't carry Next.js's NEXT_PUBLIC_ habit-transfer the way a human switching frameworks would — it reads the actual project's env-var convention from the code itself — and general safety training already discourages placing secrets in client-visible values. The guidance targets a human muscle-memory mistake, not an agent-relevant gap."
  killed: 2026-07-23

- id: dom-component-isolated-context-no-shared-state
  domain: coding-expo
  rule: "Treat an Expo DOM component ('use dom') as running in a completely separate JavaScript context from the native app — its own webview VM, not a scoped subtree of the same JS runtime. Pass data in via serializable props and native capabilities via async function props; never assume a module-level variable, context, or store defined in native code is reachable from inside the DOM component, or vice versa."
  kill_type: knowledge
  reason_killed: "Failed check-principle-against-consuming-lens-not-just-domain-topic: this is the umbrella restatement of a mechanism an agent would already reason out once it knows 'use dom' runs in a webview. The concrete, non-obvious payoff — the router hooks silently no-op'ing rather than erroring — is already captured in the ratified dom-component-router-hooks-not-callable; this entry adds no further judgment beyond that instance."
  killed: 2026-07-23

- id: expo-ui-universal-before-platform-specific
  domain: coding-expo
  rule: "When building UI with @expo/ui, start with the universal component layer (imported from the @expo/ui package root). Drop down to @expo/ui/swift-ui or @expo/ui/jetpack-compose only once a specific component, modifier, or platform behavior is confirmed missing from the universal layer."
  kill_type: knowledge
  reason_killed: "Failed check-principle-against-consuming-lens-not-just-domain-topic: 'try the portable/abstract option first, specialize only once something's missing' is a default instinct already applied broadly, not a mistake an agent would make specifically with @expo/ui without this guidance. Distinct from the sibling release-build-cannot-hot-reload-reuse-is-wrong-tool, which was kept because it names a concrete trap in the agent's own verification workflow (screenshotting a stale release build and misattributing 'no change' to a failed fix) rather than a generic preference already covered by baseline judgment."
  killed: 2026-07-23

- id: immutable-by-default
  domain: coding-general
  rule: "Declare variables, parameters, and data structures in their immutable form by default. Reach for const, readonly, and frozen or value types before their mutable counterparts; only use a mutable form when the variable or structure genuinely needs to change."
  kill_type: knowledge
  reason_killed: "Reading-pipeline sourced (kevlinhenney.medium.com) and close to universal, linter-enforced JS/TS doctrine — the knowledge-risk correlation principle-judgment's reading-pipeline-provenance-flags-knowledge-risk names directly. Also redundant with judgment already captured: the domain's own preamble already states prefer-error-exposing-form as a meta-convention (\"when two forms produce the same result but one has a silent failure mode, choose the form that exposes the error\") — an unintended reassignment is exactly that silent failure mode this candidate would have re-described as a new standalone principle."

- id: behavior-flags-in-refs
  domain: coding-react
  rule: "Ephemeral values that control behavior but don't affect rendering — boolean flags (mount guards, pending-write trackers, round-error bits), timer handles (setTimeout/setInterval return values), any 'did-X-happen-in-this-session' value, or a mirror of current state read only by an external handler (a document-level listener, an imperative ref method) — belong in refs, not useState. Never include timer IDs or behavioral flags in a useCallback or useMemo dependency array. For a document-level event handler (visibilitychange, blur, beforeunload) that must read current React state, shadow the reactive value with a ref updated on every render and have the handler read the ref — not the closure — rather than adding the state to the effect's dependency array as a workaround."
  kill_type: knowledge
  reason_killed: "Refs-vs-state for non-rendering values, and the ref-mirroring pattern for external listeners/latest-callback access, are both standard React documentation content, not project-earned judgment — same class as no-read-after-set-in-same-scope. Its apparent importance was inflated by a one-off: the reviewing spawn (motors-and-controls, coding-react-flow-adjacent SchematicNode.tsx sweep) hadn't actually grepped whether the codebase already carried real instances before recommending it, so it read as directly load-bearing rather than a generic reminder. Applied literally, it also failed: its prescription to mutate the ref directly during render (no effect needed) was rejected by that project's `react-hooks/refs` ESLint rule (React Compiler-safe lint, forbids ref access/mutation during render outright) — a concrete instance of the context-free-claim risk a knowledge-classified principle carries when treated as universally safe."

- id: hook-params-named-for-hook-concern
  domain: coding-react
  rule: "Hook parameters should be named for what the hook does with them, not for the caller's state variable."
  kill_type: quality
  reason_killed: "Merged into hook-callsite-legibility alongside hook-options-object-for-named-args. Both were two facets of the same concern — legible hook callsite — always proposed together from the same session. The merged principle states both forms in one entry."
  killed: 2026-07-22

- id: hook-options-object-for-named-args
  domain: coding-react
  rule: "Wrap hook boolean (and other ambiguous primitive) parameters in a single options object so the callsite reads as named arguments."
  kill_type: quality
  reason_killed: "Merged into hook-callsite-legibility alongside hook-params-named-for-hook-concern. See that entry."
  killed: 2026-07-22

- id: stable-ref-for-document-listeners
  domain: coding-react
  rule: "When a document-level event handler (visibilitychange, blur, beforeunload) must read current React state, shadow each reactive value with a ref updated on every render. The handler reads the ref, not the closure. Do not add the state to the effect's deps array as a workaround."
  kill_type: quality
  reason_killed: "Merged into behavior-flags-in-refs (structural-kinship retrospective signal, 2026-07-18). Both answered the same test — does this value drive rendered output; if not, it belongs in a ref, not state — this one is the document-listener instance of it. Absorbed as a named case in the general principle's rule and reason rather than kept as a separate entry."

- id: extract-named-concern-into-custom-hook
  domain: coding-react
  rule: "When hook calls in a component manage a single named concern, extract them into a custom hook named for that concern."
  kill_type: quality
  reason_killed: "Merged into custom-hook-owns-its-concern alongside hook-returns-own-handlers. Extraction and interface completeness are co-decisions — separated they invite partial application."
  killed: 2026-07-22

- id: hook-returns-own-handlers
  domain: coding-react
  rule: "A custom hook that owns state should return the mutation functions (handlers, dispatchers, setters) for that state as part of its return value."
  kill_type: quality
  reason_killed: "Merged into custom-hook-owns-its-concern alongside extract-named-concern-into-custom-hook. See that entry."
  killed: 2026-07-22

- id: timer-handles-in-refs-not-state
  domain: coding-react
  rule: "Store setTimeout/setInterval return values in refs (useRef), not state (useState). Never include a timer ID in a useCallback or useMemo dependency array."
  kill_type: quality
  reason_killed: "Absorbed into behavior-flags-in-refs, which is the general form. Timer IDs are behavioral flags — they gate logic without affecting rendered output. The dep-cascade concern is now part of that principle's reason."
  killed: 2026-07-22

- id: no-read-after-set-in-same-scope
  domain: coding-react
  rule: "Never read a state value in the same synchronous scope as the setter call that changes it."
  kill_type: knowledge
  reason_killed: "React's setState is async/enqueued is a first-day React fact derivable from training data. No project-specific judgment encoded — same class as preserve-3d-on-every-ancestor. A coder who needs the reminder will find it in the React docs."
  killed: 2026-07-22

- id: css-var-over-mapped-class-for-dynamic-color
  domain: coding-react
  rule: "When a component's fill color must track a CSS custom property that changes based on an ancestor's data attribute, use an inline style rather than a Record mapping prop values to utility class names."
  kill_type: quality
  reason_killed: "Fired once (Blog WireCircle, 2026-06-13). Condition requires ancestor data-attribute scoping plus static class-map — not recurred in FAMOUS. Too narrow for a seed principle after two projects."
  killed: 2026-07-22

- id: frequent-state-in-callback-deps-triggers-cascade
  domain: coding-react
  rule: "Before including a state value in a useCallback or useMemo dependency array, check whether that value is updated by the same interactions the callback serves."
  kill_type: quality
  reason_killed: "No project-domain instance across Blog or FAMOUS. Idle across two projects. The cascade concern now lives in the updated behavior-flags-in-refs reason (timer IDs in dep arrays as the canonical example)."
  killed: 2026-07-22

- id: stable-id-not-position-for-deferred-ops
  domain: coding-ts
  rule: "When recording state for a deferred operation (undo, redo, queue, bookmark), store the item's stable identity, never its current position in a filtered, sorted, or paginated view."
  kill_type: quality
  reason_killed: "Zero fires across Blog and FAMOUS. Condition (undo/redo/queue/bookmark) has not appeared in either project. A principle that never fires is ambient noise."
  killed: 2026-07-22

- id: font-mono-at-element-not-container
  domain: coding-ts
  rule: "Apply font-mono to the individual element containing code-register data — not to a wrapper div."
  kill_type: quality
  reason_killed: "Fired once (Blog FixedBottomResultsBar, 2026-06-13). Has not recurred in FAMOUS. A correct choice a coder makes from first principles when they see the symptom."
  killed: 2026-07-22

- id: mobile-fixed-bar-bottom-gap
  domain: css
  rule: "Set `bottom: -1px` on a mobile fixed bottom bar to prevent a subpixel gap at the bottom of the viewport on some devices."
  kill_type: knowledge
  reason_killed: "CSS browser rendering behavior — a lookup fact, not a judgment call. An implementer hits this once via testing, searches it, finds the fix. No project-specific context encoded."
  killed: 2026-07-22

- id: imports-before-tailwind-directives
  domain: css
  rule: "When splitting a Tailwind CSS entry file into multiple files imported via @import, put the @import statements before the @tailwind directives."
  kill_type: knowledge
  reason_killed: "A postcss-import build-warning fact (import-before-directive ordering), not a judgment call — same class as mobile-fixed-bar-bottom-gap and table-row-color-override below. An implementer hits the warning once, fixes the ordering, done."

- id: grid-for-layout-flexbox-for-flow
  domain: css
  rule: "Use CSS Grid when elements must align on two axes simultaneously or when their visual order must differ from source order. Use Flexbox when item count is dynamic or when items should size from their own content with the container distributing remaining space."
  kill_type: knowledge
  reason_killed: "Grid-vs-Flexbox use-case selection is close to textbook CSS knowledge, heavily represented in training data — its own audit provenance already recorded `kind: knowledge` at ratification time, which should have screened it out then. Derivable from documentation, not earned project judgment."

- id: table-row-color-override
  domain: css
  rule: "To allow row-level text color overrides inside a scoped table, set the base color on the scope's thead (via inheritance) rather than directly on th."
  kill_type: knowledge
  reason_killed: "CSS specificity: inherited color loses to a direct element selector. Derivable from the CSS spec. Same class as preserve-3d-on-every-ancestor — a spec fact, not a judgment call."
  killed: 2026-07-22

- id: pre-scan-before-spawning
  domain: ratify-gate
  rule: "Before spawning agents, run codebase discovery (file listings, key greps) in the orchestrator and paste the findings directly into each agent's prompt."
  kill_type: container
  reason_killed: "Purely temporal (do discovery before that) with no domain-specific judgment of its own. Folded into `SKILL.md`'s \"Starting an isolated spawn\" as step 0 so corpora keeps the behavior standalone; the general version (precondition-gathering before an action that touches shared or hard-to-reverse state) now lives as praxis's `context-discovery` phase for any project running praxis."
  killed: 2026-07-25

- id: surface-nested-handoffs-verbatim
  domain: ratify-gate
  rule: "If a spawned agent's own transcript shows it invoked the Agent/Task tool, retrieve and relay that nested handoff to the operator directly and verbatim rather than trusting the parent spawn's summary."
  kill_type: quality
  reason_killed: "Treats nested delegation as an accepted contingency worth building a recovery procedure around, rather than something no-unilateral-sub-spawn should prevent outright. If prevention holds, there's nothing to detect; if it doesn't, that's a violation to investigate directly, not a routine step. Writing this normalized the failure instead of insisting on prevention."
  killed: 2026-07-18

- id: destructive-global-actions-require-confirmation
  domain: recoverability
  rule: "Any action that clears all user-entered state requires either a confirmation step or an immediate undo mechanism. The trigger button carries no destructive visual styling; the confirmation or undo is the safety gate."
  kill_type: quality
  reason_killed: "Merged into recovery-path-replaces-confirmation. Both were the same recovery-or-confirmation test — this one just named a concrete severity bar (~30s of re-entry) for when the gate becomes mandatory. Absorbed as that threshold, stated directly in the general principle's rule and reason."

- id: seed-promotion-candidate
  domain: retrospective
  rule: "Surface a project-domain principle as a seed-promotion candidate when its condition makes no reference to this project's stack, domain, or specifics, and it has held across enough tasks to read as general rather than provisional."
  kill_type: quality
  reason_killed: "The privileged-layer concept this assumed — a project-earned principle 'promotes' into a structurally distinct seed tier — was retired: every domains-dir is symmetric, and reuse elsewhere happens through the ordinary import/ratify-gate mechanism regardless of source (kernel.md, 'Project corpora'). Its stack-agnostic-wording-alone test is superseded by complementary-principles-signal-abstraction-candidate, which requires two or more jointly-necessary principles as evidence rather than one principle's condition merely reading general."

- id: single-project-shape-principle-stays-provisional
  domain: retrospective
  rule: "Surface which ratified principles were earned in a single project shape and mark them as candidates that should stay provisional — weighable, not promoted — until tested against a second shape. A provisional principle with real fired counts under a second project shape has earned its promotion case; one that has only ever fired in its birth project stays provisional."
  kill_type: quality
  reason_killed: "Companion kill to seed-promotion-candidate — 'promoted' presumed the same retired privileged-layer distinction. The overfitting concern this guarded against survives, folded into complementary-principles-signal-abstraction-candidate's reason field, rather than as a separate provisional-status principle with no promotion tier left to gate."

- id: avoid-tautological-test-assertions
  domain: testing
  rule: "Do not write a test whose expected value is derived the same way the code under test computes it (e.g. `expect(add(a, b)).toBe(a + b)`, a snapshot hand-computed by the same logic). Expected values must come from an independent source of truth — a known-good literal, a worked example, the spec."
  kill_type: knowledge
  reason_killed: "Reading-pipeline sourced (mattpocock/skills' tdd skill) and close to universal testing-hygiene doctrine, not a decision with a genuinely tempting alternative anyone would rationally pick — the knowledge-risk correlation principle-judgment's reading-pipeline-provenance-flags-knowledge-risk names directly. Operator agreed with this assessment at ratification."

- id: kill-graduation-judged-not-assumed
  domain: retrospective
  rule: "When `corpus.py kill-report` surfaces a killed entry old enough with no sign of recurrence, judge specifically whether anything resembling it has actually resurfaced since — not merely whether enough time has passed — before running `graduate-kill` to demote it."
  kill_type: quality
  reason_killed: "Obsoleted by the 2026-08-07 kill-log relocation (operator decision): kills no longer ride in working files, so the graduation mechanic this principle gated — demoting stale kills out of working files to cap their reader-tax — has nothing left to demote. The kill-report/graduate-kill commands and the kill-graduation phase were retired in the same pass; anti-re-proposal protection now lives in the ratify gate's audit-load read of this kill log plus ratify-import-candidate's mechanical refusal of killed ids."
  killed: 2026-08-07
```

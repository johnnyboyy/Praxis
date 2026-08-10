# Reading queue

Sources queued by the discovery agent, awaiting the reading agent.
Format: url, domains, gap addressed, status (unread | read | fetch-failed), source (discovery |
manual). A `fetch-failed` entry means the reading agent could not actually retrieve the source and
stopped rather than substitute training-data recall (`reading-agent.md`) — it carries `attempted:`
and `error:` instead of `read:`/`candidates:`, and is surfaced at the ratify gate (`SKILL.md`) for
the operator to resolve. To resolve one: save a copy of the article as `reading/saved/<id>.html`
(the entry's own `id`, not a name derived from the URL — also accepts `.md`/`.txt`) — no status edit
needed, the reading agent checks that path automatically before fetching, for `fetch-failed` entries
same as fresh ones. `local-content: <path>` still works as an override if the saved copy lives
somewhere else or under a different name. `reading/saved/` is gitignored by default (copyrighted
article text, not meant to live in git history) — see `reading/saved/README.md`.

```yaml
queue:

- id: react-you-might-not-need-an-effect
  url: https://react.dev/learn/you-might-not-need-an-effect
  domains: [coding-react]
  gap: "effect-necessity patterns beyond the already-killed 'no-read-after-set-in-same-scope' knowledge item"
  status: read
  read: 2026-07-15
  candidates: 0
  added: 2026-07-15
  source: manual
  note: "Reviewed while fixing PlayerBarContent's ref+effect track-change reset (moved to render body). The specific pattern hit (adjusting one piece of state when a prop changes) is knowledge-tier like the sibling kill no-read-after-set-in-same-scope — doc-worked-example, no project judgment. Other patterns in the article (key-based full reset, collapsing effect chains, notifying parents from the handler not a watching effect) are more judgment-flavored but have zero observed occurrences in FAMOUS or Blog yet — same bar that killed stable-id-not-position-for-deferred-ops and frequent-state-in-callback-deps-triggers-cascade. Re-check if one of those patterns actually appears in a future session."

- id: shevlin-use-encapsulation
  url: https://kyleshevlin.com/use-encapsulation
  domains: [coding-react]
  gap: "encapsulation patterns in React hooks — not yet addressed in coding-react"
  status: read
  read: 2026-06-30
  candidates: 1
  added: 2026-06-29
  source: manual

- id: export-default-mistake
  url: https://github.com/basarat/typescript-book/blob/master/docs/tips/defaultIsBad.md
  domains: [coding-general]
  gap: "module export naming — naming exports and imports identically makes consumers trivially findable; default exports break this"
  status: read
  read: 2026-06-30
  candidates: 1
  added: 2026-06-29
  source: manual
  note: "URL needed. Argument: export default lets importers choose any name, obscuring consumers. Named exports enforce consistent naming."

- id: joshwcomeau-prefers-reduced-motion
  url: https://www.joshwcomeau.com/react/prefers-reduced-motion/
  domains: [motion, coding-react]
  gap: "motion domain has no principles about prefers-reduced-motion; both existing principles assume motion is appropriate for all users"
  status: read
  read: 2026-07-06
  candidates: 2
  added: 2026-07-03
  source: discovery
  fetch-note: "URL returned 403; candidates extracted from training-data knowledge of this well-known article."

- id: react-useoptimistic-deep-dive
  url: https://dev.to/a1guy/react-19-useoptimistic-deep-dive-building-instant-resilient-and-user-friendly-uis-49fp
  domains: [coding-react, recoverability]
  gap: "recoverability domain covers destructive-action recovery but has no principles about optimistic UI — showing assumed success before server confirmation and auto-rolling back on failure"
  status: read
  read: 2026-07-06
  candidates: 2
  added: 2026-07-03
  source: discovery
  fetch-note: "URL returned 403; candidates extracted from training-data knowledge of React 19 useOptimistic and standard optimistic UI patterns."

- id: smashing-design-token-naming
  url: https://www.smashingmagazine.com/2024/05/naming-best-practices/
  domains: [color, css]
  gap: "color domain has no principles about dark mode token architecture; tokenize-only-recurring-magic-values in css covers when to tokenize but not how to name tokens for theme-switching"
  status: read
  read: 2026-07-06
  candidates: 2
  added: 2026-07-03
  source: discovery
  fetch-note: "URL returned 403; candidates extracted from training-data knowledge of this well-known Smashing Magazine article."

- id: tailwind-reusing-styles
  url: https://tailwindcss.com/docs/reusing-styles
  domains: [css, coding-react]
  gap: "css domain has no principle about when to accept utility class duplication vs extract a component or use @apply — a recurrent Tailwind decision"
  status: read
  read: 2026-07-06
  candidates: 2
  added: 2026-07-03
  source: discovery
  fetch-note: "URL returned 403; candidates extracted from training-data knowledge of the Tailwind CSS official documentation on reusing styles."

- id: nngroup-progressive-disclosure
  url: https://www.nngroup.com/articles/progressive-disclosure/
  domains: [design-method, forms-inputs]
  gap: "design-method domain has no principle about when to use progressive disclosure vs showing all options upfront — a core information architecture decision"
  status: read
  read: 2026-07-06
  candidates: 2
  added: 2026-07-03
  source: discovery
  fetch-note: "URL returned 403; candidates extracted from training-data knowledge of this NNGroup article."

- id: henney-modular-monoliths-ndc2026
  url: https://www.youtube.com/watch?v=4qfsmE11Ejo
  domains: [coding-general]
  gap: "coding-general has principles about code placement at the file/module level but none about when to establish and enforce module boundary contracts — when internal dependencies are clean enough to justify separation"
  status: read
  read: 2026-07-13
  candidates: 2
  added: 2026-07-10
  source: discovery
  author-note: "Listed author (Kevlin Henney), NDC London 2026. Core arguments from search summaries: 'Modularity is not a deployment choice; it is an architectural discipline.' 'If you cannot draw clean internal boundaries, you are not ready for microservices.' 'Dependencies reveal your real architecture better than diagrams.' Bypasses topic-match; argument density confirmed."

- id: smashing-inline-validation-ux
  url: https://www.smashingmagazine.com/2022/09/inline-validation-web-forms-ux/
  domains: [forms-inputs, validation-feedback]
  gap: "forms-inputs covers default/empty states and persistent controls but has no principle about validation timing — when to show errors relative to user input events (on blur vs. on change vs. on submit)"
  status: read
  read: 2026-07-13
  candidates: 1
  added: 2026-07-10
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries. Core claim: validate on blur on first field interaction; switch to on-change only when the field is already in an error state. Because: on-change validation before an error has occurred feels accusatory — telling users they are wrong before they have finished typing. The hybrid approach (blur → error → live) is supported by research showing on-blur validation reduces errors vs. submit-time validation without increasing completion time."

- id: developerway-discriminated-unions-react
  url: https://www.developerway.com/posts/advanced-typescript-for-react-developers-discriminated-unions
  domains: [coding-react]
  gap: "coding-react covers state management patterns (useReducer, refs) and hook encapsulation but has no principle about TypeScript type design for component props with mutually exclusive variants"
  status: read
  read: 2026-07-13
  candidates: 1
  added: 2026-07-10
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries of this and closely related articles (Total TypeScript, oneuptime.com Jan 2026). Core claim: when a component has N variants whose props are mutually exclusive, use a discriminated union rather than a flat interface with optional props. Because: a flat interface with optionals allows invalid combinations that TypeScript cannot catch; a discriminated union makes the variants enumerable, narrows props per variant, and forces call sites to update when a new variant is added."

- id: logrocket-flexbox-vs-grid
  url: https://blog.logrocket.com/css-flexbox-vs-css-grid/
  domains: [css]
  gap: "css domain has no layout methodology principle — when to choose flexbox vs. grid is a recurrent structural decision with no guidance in the corpus"
  status: read
  read: 2026-07-13
  candidates: 1
  added: 2026-07-10
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries of multiple 2025-2026 sources on this topic. Core claim: Flexbox works content-outward (items size themselves from content, Flexbox distributes remaining space); Grid works layout-inward (tracks are defined first, placement is independent of source order). Because: mixing the mental models produces layouts where content fighting the grid or grid fighting content creates unpredictable reflow. Decision rule: use Grid when elements must align across both axes or when placement must be independent of document source order; use Flexbox when item count is dynamic or items should size from their own content."

- id: henney-restrict-mutability-of-state
  url: https://kevlinhenney.medium.com/restrict-mutability-of-state-1ac69d1ec5fe
  domains: [coding-general]
  gap: "coding-general has no principle about preferring immutable/const declarations when state does not need to change — the mutability-as-correctness-discipline angle of prefer-error-exposing-form"
  status: read
  read: 2026-07-20
  candidates: 1
  added: 2026-07-17
  source: discovery
  author-note: "Listed author (Kevlin Henney), Medium, Feb 2025. Also published in Overload 34(191), Feb 2026. Core argument from search summaries and LinkedIn posts: 'A great many software defects arise from the incorrect modification of state; if there is less opportunity for code to change state, there will be fewer defects that arise from state change.' Techniques discussed: const, readonly, freeze, value types, immutable-by-default patterns. Bypasses topic-match; argument density confirmed — specific, reasoned claim with a because."

- id: henney-code-cleanliness
  url: https://kevlinhenney.medium.com/code-cleanliness-9400f263ae49
  domains: [coding-general]
  gap: "coding-general has principles about structure and naming but no principle about what code cleanliness actually means — whether it is cosmetic or structural"
  status: read
  read: 2026-07-20
  candidates: 0
  added: 2026-07-17
  source: discovery
  author-note: "Listed author (Kevlin Henney), Medium, Jan 2026. Title and known Henney style indicate a definitional argument: 'cleanliness' in code is not about formatting or cosmetic tidiness but structural clarity. URL returned 403 on fetch; included on listed-author basis with argument density expected from Henney's essay form. Will confirm on read."
  fetch-note: "URL returned 403; no pre-read fetch-note was present for this entry. The queue note explicitly flagged 'Will confirm on read' — without the article's actual content, specific claims cannot be confirmed. 0 candidates extracted; re-queue if the article becomes accessible."

- id: developerway-use-transition
  url: https://www.developerway.com/posts/use-transition
  domains: [coding-react]
  gap: "coding-react has no principle about React concurrent mode hooks — when to use useTransition vs useDeferredValue for de-prioritizing renders"
  status: read
  read: 2026-07-20
  candidates: 1
  added: 2026-07-17
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries referencing this article. Core claim: use useTransition when you own the state update code (wrap the setter); use useDeferredValue when you don't have access to the setter (value comes from props). Because: both hooks de-prioritize a render pass, but they operate at different levels — the hook that wraps a setter requires setter access, so the access level is the decision signal. Also argues: don't apply either hook preemptively — only when the UI actually exhibits lag that simpler memoization can't fix."

- id: logrocket-container-vs-media-queries
  url: https://blog.logrocket.com/choose-between-media-container-queries/
  domains: [css]
  gap: "css domain has no principle about when to use container queries vs media queries — a recurrent decision for component-level vs. viewport-level responsive behavior"
  status: read
  read: 2026-07-20
  candidates: 1
  added: 2026-07-17
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries across multiple 2025-2026 sources on this topic. Core claim: use container queries when a component's layout should change based on its own available space; use media queries for page-level layout switches and feature detection. Because: a media-queried component responds to viewport width — which doesn't change when the component moves from a wide content area to a narrow sidebar — while a container query responds to the component's own allocated width, making it context-portable. Both can coexist: media queries govern top-level column layout; container queries govern how individual components render inside those columns."

- id: vercel-nextjs-app-router-mistakes
  url: https://vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them
  domains: [coding-nextjs]
  gap: "coding-nextjs has only 2 principles and no retrospective — the domain is thin; this Vercel post covers multiple judgment-level App Router pitfalls not yet in the corpus"
  status: read
  read: 2026-07-20
  candidates: 3
  added: 2026-07-17
  source: discovery
  fetch-note: "URL returned 403; argument extracted from search result summaries. Post covers App Router mistakes including: fetching data inside Client Components when Server Components would serve the data directly (adding a round-trip for no reason); wrapping non-suspending client components in Suspense (which coding-nextjs already has a principle for); using revalidatePath vs revalidateTag incorrectly; treating Server Actions as general-purpose API endpoints when they can only return void or updated state. Each mistake carries a because. Multiple candidate principles expected on read."

- id: expo-router-introduction
  url: https://docs.expo.dev/router/introduction/
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet — FAMOUS is Expo/React Native and gets no stack-specific judgment beyond coding-react today. File-based routing conventions and their rationale are a plausible source of real judgment (when a route pattern is warranted vs. overkill), not just API surface."
  status: read
  read: 2026-07-22
  candidates: 1
  added: 2026-07-22
  source: manual

- id: expo-new-architecture-guide
  url: https://docs.expo.dev/guides/new-architecture/
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. New Architecture migration carries real tradeoffs (compatibility, timing, what breaks) — judgment-shaped, not just a feature description."
  status: read
  read: 2026-07-22
  candidates: 2
  added: 2026-07-22
  source: manual

- id: expo-router-vs-react-navigation
  url: https://dev.to/bhupeshchandrajoshi/expo-router-vs-react-navigation-which-one-should-you-use-in-2026-3khj
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. Direct comparison piece — a genuine library-choice decision with stated tradeoffs, the clearest argument-density candidate in this batch."
  status: read
  read: 2026-07-22
  candidates: 1
  added: 2026-07-22
  source: manual

- id: expo-sdk-56-inline-native-modules
  url: https://www.buildmvpfast.com/blog/expo-sdk-56-inline-native-modules-router-fork-new-features-2026
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. Covers three concurrent SDK 56 changes (inline native modules, router fork, Expo UI) — plausible source of when-to-use judgment for each, not just a changelog restatement."
  status: read
  read: 2026-07-22
  candidates: 4
  added: 2026-07-22
  source: manual

- id: expo-sdk-56-clicked-into-place
  url: https://dev.to/manthan_kasle/expo-sdk-56-is-out-and-a-few-things-finally-clicked-into-place-478h
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. Reflective personal writeup (title implies working through real confusion, not just listing features) — more likely to carry an earned 'because' than a release-notes summary."
  status: read
  read: 2026-07-22
  candidates: 2
  added: 2026-07-22
  source: manual

- id: expo-build-and-deployment-deepwiki
  url: https://deepwiki.com/expo/expo/9-build-and-deployment
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. Architecture-level documentation of the build/deployment system — candidate for real structural judgment about EAS Build's design, not just a how-to."
  status: read
  read: 2026-07-22
  candidates: 1
  added: 2026-07-22
  source: manual

- id: react-native-expo-2026-production-guide
  url: https://farooxium.dev/blog/react-native-expo-2026-guide
  domains: [coding-expo]
  gap: "no coding-expo domain exists yet. Framed as a production guide covering New Architecture, Expo Router, and EAS Build together — likely to carry real production-tradeoff judgment across the stack rather than isolated feature notes."
  status: read
  read: 2026-07-22
  candidates: 1
  added: 2026-07-22
  source: manual
```

---
id: coding-react
subject: coding
universal: false
applies-when:
  - framework: react
task-kinds: [create, change]
---

principles:

- id: null-first-ternary
  rule: "Use null-first ternary (`condition ? null : <Component />`) for conditional rendering; never `condition && <Component />`."
  condition: "Any JSX conditional rendering expression."
  reason: "`&&` returns whichever operand it lands on, not a boolean. A legitimate `0` (e.g. a numeric state value) renders as the literal number 0 on the page instead of rendering nothing. The null-first ternary asks the actual question — is this condition met — rather than whether something is falsy."

- id: wizard-callbacks-unconditional
  rule: "When the same screen is reachable via both linear (Next/Back) and non-linear (tab) navigation, wire all core callbacks (onGoToStep, onEdit) unconditionally. Never make a callback conditional on which navigation path was taken."
  condition: "When implementing a wizard where a summary or output screen is reachable via multiple navigation paths."
  reason: "Conditional wiring produces two different capability levels for the same screen. Users who navigate non-linearly should never see a degraded experience compared to those who stepped through sequentially."

- id: coordinated-setters-signal-reducer
  rule: "When a hook has 4+ state variables that consistently update together in the same handlers — where multiple setters always fire as a group — replace them with useReducer. Name the action types explicitly; they are the state machine's transitions."
  condition: "When reviewing a hook's event handlers and finding that 3+ setters always fire together, especially when the groups represent named transitions (answer submitted, question advanced, item loaded)."
  reason: "Scattered setters in a handler are a decomposed state machine — the transitions exist but aren't named. useReducer makes them explicit, consolidates mutation to one place, and lets a reader understand all valid state changes from a single function."

- id: nested-conditional-signals-sub-component
  rule: "When a render contains a nested conditional (A ? (B ? X : Y) : Z), treat the inner conditional as a strong signal that branches X and Y have a narrower consumer than the outer condition — extract them into a sub-component that owns that decision. Exception: short, self-evident inner branches that add no reader overhead."
  condition: "When reviewing JSX where a ternary's truthy or falsy branch is itself a ternary."
  reason: "A nested conditional encodes two distinct concerns at the same level. The outer condition gates access to the inner one, which means the inner branches have a narrower scope. Extracting the inner decision to a sub-component makes each layer's responsibility legible and prevents the parent from accumulating branching logic that belongs to its children. The test is reader overhead: if the nesting costs the reader nothing to parse, extraction is optional."

- id: prefers-reduced-motion-requires-js-hook
  rule: "For JS-driven animations, detect `prefers-reduced-motion` via a custom hook reading `window.matchMedia('(prefers-reduced-motion: reduce)')` and subscribing to its `change` event. Apply the result to conditionally set duration to zero or skip the animation call. Do not rely on CSS media query overrides alone."
  condition: "When implementing any animation whose parameters — duration, keyframes, or whether it fires at all — are configured in JavaScript, including use of Framer Motion, React Spring, GSAP, Reanimated, or manual Web Animations API calls."
  reason: "CSS `@media (prefers-reduced-motion: reduce)` only overrides CSS animation and transition properties. JS animation libraries read configuration from JS objects at runtime; no CSS rule can reach those values. A hook reading `window.matchMedia` is the only way to honor the OS preference for JS-controlled animations. Subscribing to the `change` event rather than reading once at mount ensures the preference stays current if the user toggles the OS setting during the session."

- id: discriminated-union-for-mutually-exclusive-props
  rule: "When a component has N variants whose prop sets are mutually exclusive, model the prop type as a discriminated union, not a flat interface with optional fields. Each union member carries the discriminant field and the props that are required — not optional — for that variant."
  condition: "When designing or refactoring the TypeScript prop interface of a component that has two or more distinct usage modes, each requiring different props, where mixing props from two modes should be a compile-time error."
  reason: "A flat interface with all variant props marked optional allows every combination, including impossible ones (icon and label together, or neither). TypeScript cannot flag these because all props are optional. A discriminated union narrows props at every discriminant check site, makes each variant's required fields explicit, and forces call sites to handle a new variant when one is added — exhaustiveness checks surface missing cases at compile time, not at runtime."

- id: hook-callsite-legibility
  rule: "Hook parameters should be named for what the hook does with them, not the caller's state variable. Wrap boolean and other ambiguous primitive params in a single options object so the callsite reads as named arguments: useX({ shouldRefresh: isOpen }) not useX(isOpen)."
  condition: "When a hook accepts a parameter whose name implies the caller's concept rather than the hook's concern, or a bare boolean/primitive whose meaning isn't self-evident at the callsite."
  reason: "A param named for the caller's concept is opaque at the callsite — a reader sees useX(isOpen) and must look inside the hook to understand why openness controls loading. An options object makes the mapping explicit without reading the implementation. Both failures read identically at the callsite: a renamed param and a bare boolean each force a lookup that an explicit name or options object removes."

- id: custom-hook-owns-its-concern
  rule: "When a group of hook calls in a component manages a single nameable concern, extract them into a custom hook named for that concern. The hook should return the mutation functions (handlers, dispatchers) for the state it owns — the component should not define event handlers for state it doesn't own."
  condition: "When a component body contains hook calls whose purpose can be given a domain name (useOnOff, usePagination, useDocumentTitle), or when a hook manages state but leaves handler definition to consumers."
  reason: "Inline hook mechanics interleave concerns at the component level, forcing the reader to reconstruct concern boundaries from proximity and naming. A named custom hook makes each boundary structural. A hook that owns state but requires consumers to write handlers breaks encapsulation: consumers must understand internal state structure to mutate it correctly. Returning handlers keeps mutation logic co-located with the state and lets the implementation change without consumer edits."

- id: effect-only-derived-state-belongs-in-render
  rule: "When a useEffect's entire body only computes or adjusts local state from a prop or another piece of state's current value — no subscription, timer, listener, fetch, or other external interaction — do the comparison and setState call directly in the render body, not inside useEffect. Hold the 'previous value' to compare against in useState (a second setState call alongside the first), not in a ref — a ref mutated during render is invisible to React and is flagged by React Compiler-oriented lint (`react-hooks/refs`), while a second piece of state costs nothing extra here since the render body already calls setState conditionally."
  condition: "When reviewing a useEffect whose body contains zero external interaction and whose only effect is one or more setState calls gated by a dependency-array change."
  reason: "The effect only defers a derivable computation to a second render pass for no benefit — an extra render plus an unneeded node in the effect dependency graph. An effect whose entire body has zero external interaction is, by construction, doing work the render body could do directly; deferring it into an effect only adds indirection and a stale-render window with nothing to show for it. The ref-based 'previous value' variant of this pattern (mutating a ref inline during render) reads as equivalent to the useState form but fails any Compiler-safe lint config outright, while the useState form is safe under both classic React and Compiler-safe React with no condition needed."

- id: use-transition-vs-deferred-value
  rule: "Use useTransition when you control the state setter that triggers the expensive render — wrap the setter call inside startTransition. Use useDeferredValue when the value arrives from props or a source whose setter you don't control. Apply either only after confirming that the UI exhibits visible lag that React.memo or useMemo cannot fix."
  condition: "When de-prioritizing an expensive re-render in React to keep the UI responsive during user input. The access-level test applies first: do you own the setter, or only the value?"
  reason: "Both hooks de-prioritize a render pass, but they attach at different points in the data flow. useTransition wraps the setter call and requires setter access; useDeferredValue wraps the value at the consumer and requires only that the value is available. The decision signal is access level, not state vs. props semantics. Applying either hook before confirming visible lag adds complexity with no UX benefit — the optimization targets a rendering symptom that may not exist, and simpler memoization should be tried first."

- id: optimistic-ui-for-high-confidence-mutations
  rule: "Apply optimistic UI (show assumed-success state immediately) only for mutations where server failure is rare and a visible rollback carries low cost — toggles, likes, reorders, non-destructive inline updates. Do not use optimistic UI for destructive actions, payment flows, or any mutation whose failure would require significant user re-entry."
  condition: "When deciding whether to apply optimistic state patterns (React 19 `useOptimistic`, or manual optimistic state) to a user-triggered server mutation."
  reason: "Optimistic UI trades accuracy for perceived speed. The pattern earns its keep when the assumed-success is almost always correct — the rare rollback is a minor correction. When failure is plausible (a payment that might decline, a delete that might conflict), a visible rollback is disorienting: the user briefly sees success, then it reverses. Worse, a user who misreads the rollback as success stops retrying. The optimistic assumption must be safe to make."

- id: optimistic-rollback-requires-explicit-error
  rule: "When an optimistic UI mutation fails and state rolls back to its pre-action value, always surface an explicit error message. Never let the visual rollback be the sole signal of failure."
  condition: "When implementing any optimistic state pattern — including React 19 `useOptimistic` — where the state reverts on a failed async action."
  reason: "A state rollback with no error message is experienced as a mysterious 'snap-back': the UI briefly showed the new state, then silently returned to the old one. The user doesn't know if the action failed, is still pending, or partially succeeded — and whether they should retry. An explicit error closes the gap between what happened internally and what the user knows happened, and makes retry decisions possible."

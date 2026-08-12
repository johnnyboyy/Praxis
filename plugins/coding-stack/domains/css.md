---
id: css
subject: coding
universal: false
applies-when:
  - styling: not-none
task-kinds: [create]
---

principles:

- id: tokenize-only-recurring-magic-values
  rule: "When introducing CSS custom properties during a refactor, tokenize only values that recur with the same conceptual meaning. Single-use literals stay inline with a documentary comment citing the spec range if one is defined."
  condition: "When migrating literal CSS values to tokens during a token-introduction refactor."
  reason: "A token for a single consumer is a rename with extra indirection — the value's meaning is clearer inline next to its only use. Token sprawl makes the token file harder to skim."

- id: tailwind-extract-component-before-apply
  rule: "When a Tailwind utility pattern needs to be centralized, extract a React component (or template partial) rather than using `@apply`. Reserve `@apply` for contexts where a component abstraction is impossible — CSS-only environments, base-layer overrides for third-party HTML, or legacy non-component templates."
  condition: "When the same set of Tailwind utility classes appears on multiple independent elements in a React codebase and needs to be deduplicated."
  reason: "A React component is a structural boundary that accepts props, renders conditionally, and is tracked by IDE find-references. `@apply` in a CSS file creates a hidden coupling between a class name and a utility set, with no mechanism for props or conditions. Centralizing with a component keeps style and behavior co-located and visible; centralizing with `@apply` creates a second source of truth (markup + stylesheet) that can drift."

- id: tailwind-loop-duplication-is-not-a-problem
  rule: "Repeated Tailwind utility strings inside a template loop do not require extraction. The loop body is the single source of truth; runtime duplication across rendered instances is not authoring duplication."
  condition: "When reviewing Tailwind markup and finding the same utility class string in multiple iterations of a `map()`, `for`, or template loop."
  reason: "Extracting a component from a loop to 'remove duplication' creates a component with exactly one callsite — the loop body — adding indirection with no reuse benefit. The authoring-level source of truth is already unique; only the rendered output repeats. The duplication concern that motivates component extraction is when independent elements in different templates share a style — not when one template loop generates identical markup."

- id: container-queries-for-component-scope
  rule: "Use container queries when a component's layout should adapt to its own available width, regardless of viewport size. Use media queries for page-level layout breakpoints and browser feature detection. The two coexist: media queries set top-level column structure; container queries govern how individual components render within those columns."
  condition: "When adding responsive behavior to a CSS component that may be placed in varying container widths across different page contexts — sidebars, dialogs, full-width slots — or when the component needs to change layout independently of the viewport size."
  reason: "A media-queried component responds to viewport width, which does not change when the component moves from a wide content area to a narrow sidebar. A container query responds to the component's own allocated width, making it context-portable. Relying on media queries for component-level layout adaptations creates a hidden coupling between the component's style and its position in the page — moving it to a different context breaks its layout. Container queries remove that coupling."

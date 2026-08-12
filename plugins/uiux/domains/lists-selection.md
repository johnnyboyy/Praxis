---
id: lists-selection
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: indicator-weight-matches-job
    rule: When an active-item indicator is the primary way a user orients themselves in a low-differentiation list, it must carry enough visual weight to be the first thing the eye finds. Subtle indicators that work as secondary signals in rich-content lists are insufficient when items have little visual differentiation.
    condition: When an active/selected indicator must orient the user in a list where items have low visual differentiation — e.g., all items show only timestamps.
    reason: A dot works as a secondary signal when items have rich content to anchor it. In a sparse list, the dot can read as decoration. Full-row treatment is the established selection affordance users already know.
  - id: active-row-is-inert-exact-route-only
    rule: The currently active entry in a selection list must suppress its hover state and produce no action on click ONLY when its active state corresponds to the exact current page/state — clicking it would navigate to exactly where the user already is. When an item's active state is determined by a broader match spanning multiple distinct pages/routes (a section/prefix match, e.g. a nav item highlighted across an entire route subtree), keep it a normal interactive element — real hover feedback, real click behavior — and use the active indicator (tint, accent bar) only to signal 'you're in this section,' not 'clicking does nothing.'
    condition: When a list or nav allows switching the active item by clicking a row, and one row represents the currently active item. Before applying full inertness, check whether 'active' means the exact current route/state or a broader section match — only the former is inert.
    reason: A section/prefix-matched 'active' state can span a list screen and every one of its detail sub-pages; applying blanket inertness to it makes a real, meaningful click (returning from a detail page to the list) silently do nothing — the exact confidence-breaking failure inert-active-rows exist to prevent, just inverted onto the wrong scope. The label 'active' alone doesn't say whether it means 'exact page' or 'entire section,' and only the former should ever suppress hover/click. The original insight (an item meaning 'you are exactly here' should not offer false affordance) is still correct; it was being applied past its actual scope. The current-route/current-section split spelled out above is the fix.
  - id: section-level-explanation-not-row-level
    rule: Explanatory tooltips or help text that apply uniformly to all rows in a list belong on the section header, not repeated per row.
    condition: When every row in a repeatable list carries the same info tooltip with identical content. Does not apply when tooltip content is row-specific.
    reason: Per-row repetition of identical explanatory content adds visual noise without adding information. A single tooltip on the section heading correctly signals that the concept applies to the section as a class.

---
id: visual-hierarchy
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: hierarchy-through-scarcity
    rule: Subordinating a non-dominant element means withholding extra emphasis from it, never degrading its legibility (dimming, low-contrast text, shrinking below reading size) to make the dominant element stand out more. Every element stays fully readable; only one element per section carries the emphasis signals (differentiation, color, elevation) that mark it as dominant.
    condition: When composing any screen or section layout and deciding which elements receive visual weight through color, size, differentiation, or elevation.
    reason: Degrading non-dominant elements is a plausible, common shortcut for creating contrast — it reads as hierarchy-by-subtraction and is easy to reach for. But it destroys those elements' communicative function without actually improving the dominant signal, which comes from elevating one element, not diminishing the rest. The corollary that only one element gets the emphasis signals is the more familiar half of this — worth keeping so it isn't restated as its own principle.
  - id: control-grouping-encodes-unity
    rule: Visual grouping of controls — capsule, joined buttons, bordered cluster — signals that all segments operate on the same value or target (e.g. −/0/+ on a count, or 1/2/3 as states of a single selection). Apply a grouped form only when that relationship holds; keep controls visually separate when they are distinct actions, even if related or adjacent.
    condition: Any interactive control group — steppers, toggles, segmented selectors, button rows.
    reason: The shape of a control should encode the relationship of its options to each other. Visual grouping communicates 'these are all aspects of one thing.' Joining distinct actions into a group for visual tidiness creates false affordance.
  - id: redundant-badge-sublabel
    rule: When a badge already communicates status, no sub-label repeating that status is needed. Badge alone.
    condition: When a list item has both a badge and explanatory text that say the same thing.
    reason: Redundancy adds visual weight without adding information.
  - id: responsive-text-by-viewport-distance
    rule: Apply responsive text size bumps independently of density decisions. Mobile-primary density (airy spacing) does not imply mobile-primary text sizes — desktop users read at ~2x the viewing distance and need one size step up on any text that carries legibility weight.
    condition: Any page with small text elements that carry data or instruction weight. Apply regardless of whether the project is mobile-primary or desktop-primary.
    reason: Mobile density and mobile text size are independent concerns. Density governs spacing and touch-target sizing. Viewport distance governs text legibility.

---
id: surfaces-elevation
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: disclosure-panel-vs-modal
    rule: Use a floating disclosure panel (anchored dropdown) rather than a modal for secondary utility content that does not require the user's full attention before proceeding. A panel stays in context; a modal demands a decision.
    condition: When designing secondary content display triggered by a button — history lists, saved states, settings overviews — where the user may want to reference while still seeing the page behind.
    reason: Modals carry an implicit 'you must deal with me now' contract. Reference content should let the user glance and close without a context break.
  - id: dark-floating-surface-fill
    rule: In dark mode, a floating surface (dropdown panel, popover, tooltip panel) must use a fill perceptibly lighter than the surface it floats over — border and shadow alone are insufficient to establish elevation in dark-on-dark contexts.
    condition: When a surface floats over any dark surface in dark mode (appears above content via z-index).
    reason: Drop shadows have negligible contrast on near-black backgrounds. A border at low opacity marks an edge but does not assert depth. The fill must carry the elevation signal.
  - id: scroll-fade-gradient-surface-match
    rule: Scroll-fade gradients must fade to the surface's own fill color, not to the page background.
    condition: When a scrollable area inside any panel has top/bottom fade gradients.
    reason: A gradient fading to the wrong color creates a bleed-through appearance — the gradient edge looks like a different surface is showing through, rather than content disappearing into the panel.

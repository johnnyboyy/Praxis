---
subject: design
posture: guardrail
applies-when:
  - has-ui: yes
units-of-work: [design-ui-surface, bootstrap-ui-surface]
universal: false
---

# Domain: color

Palette and hue judgment. Audit metadata lives in
`domains/audit.md`, loaded only at ratify/retrospective time.

```yaml
last-retrospective: 2026-06-20

principles:

- id: color-palette-inspiration
  rule: "When a color reference or taste palette informs a design direction, extract what it embodies — hue relationships, saturation register, warmth or coolness, depth contrast — rather than sourcing values from it directly."
  condition: "When making a color decision where a reference palette or taste example has been provided. Does not apply when selecting an existing project token by name."
  reason: "A palette submitted as a taste example encodes relationships and sensibilities, not prescriptions. Pulling hex values directly overfits — the example encodes what worked in that context, not a color system."

- id: palette-chromatic-depth
  rule: "Ensure the color system has at least 3–4 distinct hues available for semantic roles. Each hue should occupy its own corner of the wheel at controlled saturation — no two semantic colors should be close enough in hue to be confused. Avoid single-accent-on-monochrome schemes."
  condition: "Any UI with more than two distinct semantic roles (interaction, reference, state feedback, etc.)."
  reason: "A binary palette (background + one accent) flattens hierarchy — everything that isn't the accent reads as the same undifferentiated surface. Chromatic variety at low saturation lets each element carry meaning through color relationships rather than relying solely on light/dark contrast."

killed:

- id: semantic-tokens-required-for-theme-switching
  rule: "Any color token system that must support dark mode or theme switching needs at least two tiers: a primitive tier (raw values, e.g. `--color-blue-500: oklch(...)`) and a semantic tier (role-named aliases, e.g. `--color-action-primary: var(--color-blue-500)`). Theme switching redefines only semantic token values. Components reference only semantic tokens."
  kill_type: knowledge
  reason_killed: "Primitive/semantic token-tier separation is now close to universal design-systems doctrine, heavily represented in training data — derivable from documentation, not earned project judgment. Companion entry semantic-token-names-by-role-not-value was already tagged `kind: knowledge` in its own audit provenance at ratification; this one should have been screened the same way."
  see-also: semantic-token-names-by-role-not-value

- id: semantic-token-names-by-role-not-value
  rule: "Semantic token names must describe the color's role or purpose, never its visual appearance. Use `--color-text-danger`, `--color-surface-interactive`, `--color-border-subtle` — never `--color-red-text`, `--color-light-gray-bg`."
  kill_type: knowledge
  reason_killed: "Role-based vs. value-based token naming is standard design-token-system doctrine, not an earned judgment call — its own audit provenance already recorded `kind: knowledge` at ratification time."
  see-also: semantic-tokens-required-for-theme-switching
```

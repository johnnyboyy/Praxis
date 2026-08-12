---
id: color
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: color-palette-inspiration
    rule: When a color reference or taste palette informs a design direction, extract what it embodies — hue relationships, saturation register, warmth or coolness, depth contrast — rather than sourcing values from it directly.
    condition: When making a color decision where a reference palette or taste example has been provided. Does not apply when selecting an existing project token by name.
    reason: A palette submitted as a taste example encodes relationships and sensibilities, not prescriptions. Pulling hex values directly overfits — the example encodes what worked in that context, not a color system.
  - id: palette-chromatic-depth
    rule: Ensure the color system has at least 3–4 distinct hues available for semantic roles. Each hue should occupy its own corner of the wheel at controlled saturation — no two semantic colors should be close enough in hue to be confused. Avoid single-accent-on-monochrome schemes.
    condition: Any UI with more than two distinct semantic roles (interaction, reference, state feedback, etc.).
    reason: A binary palette (background + one accent) flattens hierarchy — everything that isn't the accent reads as the same undifferentiated surface. Chromatic variety at low saturation lets each element carry meaning through color relationships rather than relying solely on light/dark contrast.

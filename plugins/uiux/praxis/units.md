# Units of work — lease declarations (uiux seed fragment)

Seed fragment for `<root>/.praxis/units.md` — the praxis lease file (`praxis/scripts/units.py`).
Provisioning appends this beside the engine's own fragment and tunes the globs to the project.
These surfaces are the hard design→code boundary: a design unit's work lands in documents
(`.corpora/` libraries, `docs/` specs, markdown), never in source — the first source edit under a
design frame is a different unit of work and the gate bounces it into its own `begin_work`
(observed live: an entire implementation ran to completion under a design-ux-flow composition).

## design-ux-flow
edit-surface: docs/*, *.md, .corpora/*
output: a UX-flow decision document (ux-library.md update or spec) — implementing it is a separate implement-feature unit

## design-ui-surface
edit-surface: docs/*, *.md, .corpora/*
output: a UI-surface decision document (ui-library.md update or spec) — implementing it is a separate implement-feature unit

## bootstrap-ux-surface
edit-surface: docs/*, *.md, .corpora/*
output: the bootstrapped ux/ui library documents

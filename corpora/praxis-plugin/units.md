# Units of work — lease declarations (corpora seed fragment)

Seed fragment for `<root>/.praxis/units.md` — the praxis lease file (`praxis/scripts/units.py`).
Provisioning appends this fragment (plus any other plugin's fragment, e.g. the uiux plugin's
design units) into the root's own `units.md`, then tunes the surfaces to the project's actual
layout — the globs below assume libraries under `.corpora/` and specs under `docs/`; a self-hosted
domains dir (like the skills repo's `corpora/domains`) needs its ratify/retrospect surfaces
widened to match. `*` crosses `/`. An undeclared unit restricts nothing (fail-open).

## implement-feature
output: implemented, verified code — plus the unit's handoff

## debug-issue
output: the diagnosed root cause and its verified fix

## scan-architecture
edit-surface: docs/*, *.md, .corpora/*
output: an architecture report — findings land as docs/proposals, never as source edits

## ratify
edit-surface: .corpora/*, docs/*
output: gate verdicts recorded in the domain files

## retrospect
edit-surface: .corpora/*, docs/*
output: retrospective updates recorded in the domain files

## migrate-dependencies
output: migrated manifests and code, verified

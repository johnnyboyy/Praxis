# Units of work — lease declarations

From the corpora seed fragment, surfaces tuned to this self-hosted repo: the domain pool lives at
`corpora/domains/` (not `.corpora/domains/`), so ratify/retrospect write there. No uiux fragment —
this project has no UI.

## implement-feature
output: implemented, verified code — plus the unit's handoff

## debug-issue
output: the diagnosed root cause and its verified fix

## scan-architecture
edit-surface: docs/*, *.md, NOTES.md
output: an architecture report — findings land as docs/proposals, never as source edits

## ratify
edit-surface: corpora/domains/*, plugins/*/corpora/domains/*, .corpora/*, docs/*
output: gate verdicts recorded in the domain files

## retrospect
edit-surface: corpora/domains/*, plugins/*/corpora/domains/*, .corpora/*, docs/*
output: retrospective updates recorded in the domain files

## migrate-dependencies
output: migrated manifests and code, verified

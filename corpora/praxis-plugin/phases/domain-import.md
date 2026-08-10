# Phase: domain-import

Re-propose an already-ratified principle or convention from another domains-dir into this project's
own `.corpora/domains/`, through the ordinary ratify gate. Migrated from corpora
`processes/domain-import.md`. Almost entirely mechanical — the one judgment point (which destination
domain a picked entry belongs to) is the ratify gate's existing `domain-assignment-at-ratify-gate`
judgment, reused, not new. So this phase is thin over the script that carries the sequence.

**Entry condition:** a project wants to pull ratified content from another corpora location (the
skill's own `domains/`, another project's `.corpora/domains/`) — at bootstrap (the default-pool fast
path), during a domain-repo migration, or any time later to pick up new/updated content.

**Stance:** none of its own. Browsing and filing a candidate needs no design or code judgment.

**Invocations:** the judgment engine only at the ratify gate, per candidate, for the
domain-assignment call — the same judgment any freshly-mined proposal gets. `kind: judgment` is the
default (the entry already cleared the fork test once, in its source), but the fork test stays
available to re-examine a specific entry rather than rubber-stamp it.

## Deterministic facts / sequence — the praxis script

`domain_import.py` carries the sequence with its browse-before-propose discipline (each verb is an
engine call through the single binding; the read-only step has no side effects, so it can never
silently file):

1. **`browse --source <domains-dir>`** — `import-list`: every principle/convention at the source,
   flagging ids that already exist in the project. Read-only, proposes nothing.
2. **`file --source … --domain … --id …`** (one) or **`file-pool [--source …]`** (a shape-matched
   bulk pull) — files candidate(s) into `.corpora/import-candidates.md` with `imported-from`
   provenance.
3. **`ratify --id … [--as-domain …] [--as-id …]`** — after the gate's per-entry judgment,
   `ratify-import-candidate` writes the ratified entry into its destination domain, files provenance,
   records the gate, and removes the candidate — one atomic step. A convention-shaped candidate (no
   `condition`) has no scripted path yet — hand-write it into `conventions:` (this is one of
   `ratify_writeback.py`'s manual verbs' territory).

**Artifact:** the ratified entries in the destination domains, with `imported-from` provenance in the
audit layer.

**Surfaced/lacking:** to track a source's content as it evolves, **repeat rather than fork** — re-run
this sequence periodically; there is no separate sync mechanism to maintain.

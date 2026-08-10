# Phase: retrospective

The periodic, backward-looking counterpart to per-task routing: read a domain's accumulated corpus
and gate history for fork, convergence, drift, promotion, and condensation signals.
Migrated from corpora `processes/retrospective.md`. Its judgment is heavy and stays entirely in the
engine (the `retrospective` domain reads what the history means); praxis contributes the
deterministic sliver it already scripts — the ledger summary — and
the discipline that every signal is a *proposal to the operator*, never an automatic write.

**Entry condition:** operator command only (`retrospective <domain>` or `<composition-name>`). Never
automatic. A fired mechanical trigger (`ratified ≥ 6`, `working-file-tokens` +50%, `gate-violations
≥ 3`) is a *suggestion* the engine prints at the gate — it replaces "am I watching carefully
enough," not the retrospective's own judgment.

**Stance:** convergent. This is an **audit-mode load** (the full working file plus `audit.md` per
domain under review, plus the `retrospective` domain unconditionally), not a composed spawn's working
load — praxis relays that the engine loads this differently; it does not itself decide the set.

**Invocations:** the judgment engine, in audit mode, per domain under review. Every signal it
surfaces (contamination, domain-tension split, convergence, composition drift, abstraction
candidate, structural kinship, anti-overfitting, efficacy, co-firing) is advisory — a proposal, not
a write.

## Deterministic facts — run first (praxis scripts)

- **ledger summary** — the praxis chunk ledger's `chunk_ledger.py summary` aggregates a finished
  workstream's chunks for the review. Read-only.

## The judgment (engine's)

Apply the `retrospective` domain to what was read. Present every signal and every graduation
judgment to the operator: ratify, reject, or edit, same as any proposal. Two steps stay a *live
conversation* deliberately, with no script and no automatic path: an approved **domain-tension
split** (decide names/boundaries, move each principle, add a `moved`/`split` history entry) and any
**graduate-to-convention** (apply promotion restraint first). Both are `ratify_writeback.py`'s
*manual* verbs — praxis names them manual rather than faking a scripted write.

**Artifact:** the operator-reviewed set of ratified/rejected/edited signals and graduations. On
completion the engine resets counters (`retro-done` per domain; `sync-done` after a library sync).

**Surfaced/lacking:** a domain-tension split whose new boundaries the operator could not settle in
the session is surfaced as an open decision, not guessed at.

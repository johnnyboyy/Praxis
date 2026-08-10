# Phase: plugin-authoring

Extract a concern out of the cores (or another plugin) into its own plugin, or move a domain between
plugins — the process that ties the deterministic authoring scripts together and marks the one seam
where judgment, not mechanics, decides. Standalone: run on operator command, never automatically.

The split this phase exists to hold: **what and whether are judgment; the moves are mechanics.**
Deciding that a concern *should* be a plugin, which domains belong to it, and whether its judgment
ships or is left to accrete — none of that is scripted here (it is earned, the same reason a new
concern's judgment face starts empty). Once those calls are made, every file operation that carries
them out is deterministic and runs through a tested script, never by hand.

**Entry condition:** operator command — "extract `<concern>` into a plugin", or "move domain `<D>`
from `<A>` to `<B>`". The concern boundary and the domain list arrive decided; this phase does not
choose them.

**Stance:** none of its own — it executes a decided extraction. The judgment it depends on was made
before entry.

**Invocations:** the judgment engine only where a moved domain's principles must be re-staged through
its gate (a judgment-face import is never a raw copy); the mechanical moves invoke no judgment.

## Deterministic facts / steps — run as scripts, not by hand

1. **Scaffold** the target plugin's shape — `plugin_scaffold.py new` writes its `plugin.json` and face
   dirs; `plugin_scaffold.py validate` confirms the manifest and layout. Generic, engine-free.
2. **Relocate each decided domain** — the engine's `relocate-domain` capability moves a domain's
   working file *and* its whole audit trail (provenance, counter, efficacy) between domains-dirs in
   one step. This is the move that was, before the script existed, done by hand and got miscounted;
   it is now a fact, not a chore. Praxis names the capability; the registered engine maps it to its
   verb.
3. **Re-validate** — `plugin_scaffold.py validate` on the new plugin, and the core purity check
   (`grep` the process core for any engine reference) — both deterministic gates that must pass before
   the extraction is considered done.

## The judgment seam (not scripted)

- **Whether** the concern is a plugin at all, and **which** domains move — decided before this phase,
  left to the operator and the engine's own judgment about decomposition; the scripts above refuse to
  make that call for you.
- **Whether the new plugin ships judgment or an empty face** — a judgment call the scaffolder
  deliberately cannot make: it creates the face dir; what (if anything) fills it is earned at the gate.

**Artifact:** the extracted/relocated plugin — scaffolded, its domains moved with their audit trails
intact, validated, and the core still purity-clean.

**Surfaced/lacking:** any decomposition judgment the extraction *surfaced* (a domain that turned out
to belong elsewhere, a concern boundary that only became clear mid-move) is a candidate for the
engine's gate — the extraction process is deterministic, but what it teaches about where things belong
is judgment, and accrues there.

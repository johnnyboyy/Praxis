---
id: coding-ts
subject: coding
universal: false
applies-when:
  - language: typescript
task-kinds: [create, change]
---

conventions:

- id: arrow-block-body
  rule: "Use block arrow bodies always (`() => { return value; }`)."
- id: no-early-returns
  rule: "Use if/else block bodies, not early returns or guard clauses. A flat row of guards whose order doesn't matter is a signal to extract and name the combined condition (`const error = validateRequest(req)`), then use if/else. Scoped to this pack because some ecosystems (e.g. Go) idiomatically prefer guard clauses. See also no-shell-for-structural-absence for the narrower case of a branch with no true opposite side."

principles:

- id: undefined-check-by-source
  rule: "Match the equality operator to the source of the value: an optional object field typed `Value | undefined` uses `=== undefined` / `!== undefined`; array element access and `Array.find()` results also use `!== undefined`. Never `== null` for either."
  condition: "When guarding any value that may be absent — an optional object field, array element access, or `Array.find()` results."
  reason: "Both sources yield `undefined`, not `null` — distinguishing them by name keeps intent clear at the point of use. A loose `== null` silently absorbs both, hiding which case actually occurred."

- id: named-exports-over-default
  rule: "Prefer named exports over export default. Export a binding under the name it's defined with, and import it by that same name."
  condition: "When adding or refactoring a JS/TS module's exports."
  reason: "A default export lets every importer choose its own local name for the same binding, so the same value can appear under different names across the codebase, and find-references / auto-import tooling has no canonical name to anchor on. Named exports fix the name at the source, so grep and IDE find-references locate every consumer reliably."

- id: same-state-same-name
  rule: "When two sibling types have states that produce the same visual output, unify the state vocabulary before extracting a shared renderer. A naming mismatch signals the same concept split across two types — rename first, then the shared function compiles without casting."
  condition: "When two types have parallel state fields that map to identical visual output, differing only in the name of the base/default state."
  reason: "Separate names for the same visual concept force either a translation layer or casts at the merge point. Renaming removes the impedance mismatch and makes the subset relationship structurally visible to TypeScript — the narrower type becomes assignable to the wider one without casting."

- id: nan-serializes-to-null-in-json
  rule: "Never store NaN in state that will be JSON-serialized. Use undefined for 'not yet entered' — JSON.stringify omits it; NaN becomes null and silently corrupts reads. The ?? operator does not catch NaN (NaN is not null/undefined)."
  condition: "Any controlled numeric input whose onChange handler parses with parseFloat or parseInt, or any state that is JSON.stringify'd to a serialization boundary."
  reason: "JSON.stringify(NaN) === 'null'. An input cleared to '' → parseFloat('') → NaN → ??(default) still evaluates to NaN. That NaN reaches localStorage as null, breaking any consumer that assumes the TypeScript number type."

- id: no-shell-for-structural-absence
  rule: "If one side of a conditional is a true structural absence — not skipped logic, just nothing to do by definition — don't wrap it in an if/else. Reach for a construct that has no empty branch to begin with, e.g. filter."
  condition: "A branch where one outcome does nothing at all — typically filtering a collection or checking a predicate."
  reason: "An empty branch beside a real one gives 'nothing happens' the same weight as the real case, though it's incidental, not meaningful. Making it explicit then forces a stray empty block or a comment that just restates the condition. A branchless construct has nothing to fill or comment. Narrower than this domain's no-early-returns convention — that convention was never meant to force a true structural absence into a populated if/else shell."

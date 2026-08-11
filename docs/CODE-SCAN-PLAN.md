# Code scan + cleanup plan (praxis package)

Driven through praxis (plan registered in the journal): `comments → refactor + gate-tests`.
Judgment composed by the conductor for an `explore/architecture-scan`: architecture-health,
codebase-design, coding-general, testing, security, prose-craft, dependency-management, debugging,
code-review-reception.

## Governing bar for comments
`minimize-comments-prefer-self-documenting-code`: default to NO comment; a comment survives only for
a genuinely non-obvious constraint/invariant/workaround not recoverable from the code — never to
describe what the code does or restate a value domain. Operator overlay: treat every comment as a
signal to make the code explicit (name / type / assert / docstring); keep a survivor only with its
condition (why-it-must-stay / replace-when).

---

## Unit 1 — `comments` (IN PROGRESS)

### Done (pruned; value domains left to the existing module constants / `__post_init__` validators)
`journal.py`, `run.py`, `situation.py`, `schedule.py`, `plan.py` (+ dead `by_id` removed),
`accretion.py`, `policy.py`, `adapters.py`, `views.py`, `handoff.py` (kept one tightened invariant:
payload_read is the gate precondition).

### Remaining
- **`providers.py`** — remove the 3 type-alias shape comments (L60–63), the `unclassified` continue
  note (L100), the `fit==none` compose-key note (L139). Consider a `TypedDict` for the callable
  return shapes instead of the removed comments (explicit > comment); optional.
- **`conduct.py`** — remove L97 (redact-judgment narration), L124 (clean-exit narration), L206
  (no-gap-on-preview). For L206 the intent (`root=None` suppresses gap recording) is a non-obvious
  side effect — make it explicit with a named arg/local (`suppress_gap = None`) rather than a comment.
- **`cascade.py`** — L197 (lock early-return) and L204 (broad-except rationale): keep L204 tightened
  (justifies an `except Exception`), remove L197 (the `return 0` under a failed `flock` is clear).
- **`scripts/gate.py`** — L33 (journal path) remove; the `parents[1]` + import is self-evident.
- **`scripts/root_tree.py`** — KEEP tightened: the `.claude` skip rationale (L58–60, a real
  non-obvious constraint: symlinked skills carry their own config marker) and the marker choice
  (L32–36, trim to the `.praxis`-vs-`praxis` reason). Remove L75 (`prune in place`) and L99
  (`marker owning dir`) as narration.
- **`scripts/units.py`, `scripts/churn.py`** — audit the 2–3 remaining comments; remove narration.
- **`mcp_server.py`** — verify none remain beyond tool docstrings (keep the tool docstrings; they are
  the MCP tool contract, not code comments).

### Close-out
Run full suite (`python3 -m unittest discover -s tests`); re-grep the comment inventory to confirm
only conditioned survivors remain; commit.

---

## Unit 2 — `refactor` (depends on `comments`)
- **Dedup verifier construction** (3 sites: `conduct.run_task`, `conduct.run_tasklist`,
  `cascade.run_cascade`): extract `verifier_from_test_cmd(test_cmd) -> Verifier | None` (into `run.py`
  beside `CommandVerifier`, or a small `_verifier` helper) and call it from all three.
- **Dedup tasks-JSON parse** (2 sites in `mcp_server.py`, `plan`/`register_plan`): extract
  `_parse_tasks(tasks) -> list | error-dict`.
- **Dead field check** — `Policy.verify_required` is loaded but never enforced in `run`/`run_dag`.
  Decide: enforce it (a plan without a verifier is rejected/warned) OR delete it. Do not leave a
  guard that guards nothing.
- Run suite; commit.

---

## Unit 3 — `gate-tests` (depends on `comments`)
`gate.py` is the security-critical edit gate with only incidental coverage. Add `tests/test_gate.py`
(feature-level, adversarial per `probe-one-adversarial-case-beyond-happy-path`), through the public
`gate_decision` / `mark_payload_read` surface (per `interface-is-the-test-surface`):
- no open unit → `no_unit`;
- open unit, file within lease surface → `allow`;
- open unit, file OUTSIDE lease surface → `deny` (out-of-surface reason);
- open unit, `delivery` in {file, spawn}, payload unread → `deny`; after `mark_payload_read` → `allow`;
- corrupt/garbage journal → fail-open (`no_unit`), never a hard deny;
- `mark_payload_read` with no open unit → no-op `False`.
Run suite; commit.

---

## Decision (not auto-planned) — S3: speculative `Planner` seam
`two-adapters-before-a-real-seam`: the `Planner` protocol has three adapters but only
`PassthroughPlanner` is wired to production; `CallablePlanner` / `SubprocessPlanner` are exercised
only by tests (the real planner — the interactive agent — sits outside the seam and hands in finished
specs). Options:
1. **Keep** — if a spawned/inline planner is concretely imminent (the docs describe it). Cost: a
   maintained seam serving no live variation.
2. **Collapse** — apply the deletion test: drop the `Planner` protocol + the two unused adapters,
   inline `PassthroughPlanner` into `plan_tasks`; re-introduce the seam when the second real adapter
   lands. Removes speculative generality.
Recommend (2) unless the spawned planner is next on the roadmap. Operator's call.

---

## Out of scope (confirmed healthy)
Core/wiring/surface layering is clean; journal-as-source-of-truth is applied consistently (views,
handoff, accretion, plan_status are folds); Executor and Verifier seams have real multiple adapters.
`corpora/` and `scripts/{root_tree,units,churn}` are stable (not in the churn window) — comment-audit
only, no structural change.

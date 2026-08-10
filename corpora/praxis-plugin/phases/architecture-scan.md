# Phase: architecture-scan

Proactively scan a managed project's codebase for architecture-deepening opportunities and surface
them to the operator, agent-legible rather than visual. Migrated from corpora
`processes/architecture-scan.md`. The scan is judgment (deep-module reasoning: depth, seam, leverage,
locality — the `architecture-health` domain), but its *scoping* step is a fact praxis scripts, so the
judgment spends itself on the modules the hot spots point at, not on tallying commits.

**Entry condition:** operator command only, `architecture-scan [target]`. Never automatic — there is
no mechanical trigger, the same standalone posture the retrospective takes, applied here to the
target project's actual code.

**Stance:** convergent (assess and recommend, not generate). Load `architecture-health`
(`unit-of-work: scan-architecture`).

**Invocations:** the judgment engine composed for `scan-architecture`; and the `Explore` agent to
walk the scoped code. Candidates are described in deep-module vocabulary informally — corpora has no
domain for those terms yet.

## Deterministic facts — run first (praxis script)

- **`churn.py dirs --repo <target>`** (or `files`) — recent-churn hot spots from git alone, the
  concrete form of `scan-scope-by-recent-churn`. When the operator named a target, scope to it
  directly and churn is optional; otherwise the churn ranking is what pulls attention first. Widen
  the window (`--since` / `--max-count`) if changes are too scattered to show a hot spot. This
  replaces the prose "walk `git log` for a good stretch" with a fact.

## The judgment (engine's)

1. **Scope** — the named target, else the churn hot spots.
2. **Explore** — walk the scoped code (`Explore` agent). Note friction: interfaces nearly as complex
   as their implementation, concepts requiring bouncing between many small modules, seams leaking
   coupling, code hard to test through its current interface. Apply the deletion test to anything
   suspected shallow.
3. **Screen ADR conflicts** — a candidate contradicting an existing ADR is included only if the
   friction is real and specific (`dont-relitigate-adr-without-real-friction`), and the conflict is
   marked.
4. **Write the report** — a plain-text file at `<target>/.corpora/architecture-scans/<date>-<slug>.md`,
   one section per candidate (Files / Problem / Solution / Benefits / Tradeoffs / Recommendation
   strength / ADR conflict), ending with a Top recommendation.

**Artifact:** the scan report file, relayed **verbatim** to the operator (the `Surfaced` convention —
never summarized or filtered).

**Surfaced/lacking:** offer per candidate to hand it to the planner as a fresh capability
description; do not invoke the planner automatically. A scan that surfaces nothing actionable is a
valid outcome — report that plainly rather than manufacturing a weak candidate.

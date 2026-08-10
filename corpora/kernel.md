# The Corpora Kernel

The kernel is the shared mechanism every spawn inherits. It is not code — it is a discipline made
of files plus a loop.

A **spawn** (the process layer's unit of work) draws a *stance* plus a *composition*: a generative
posture (the mode of reasoning the agent applies) and the **domain corpora** corpora composes for the
task, decided fresh from the unit-of-work each time. Spawns do not own corpora. Judgment lives in
domains; a composition is the momentary combination through which one or more domains are applied to a
task. See "Spawns: stance + composition," below.

A **domain corpus** is a list of principles about one subject matter, context type, or decision
class — not a job title. Multiple compositions may draw on the same domain, so shared judgment
lives once. Domain boundaries are *discovered from accumulated tension* (the fork signal in the
retrospective), never declared up front from how a team would be organized.

---

## The principle schema

A domain corpus is a list of **principles**. Every principle has four required fields plus optional ones:

```yaml
principle:
  id: kebab-case-identifier
  rule: # WHAT. The judgment itself, stated as guidance.
  condition: # WHEN it applies. The scope. Be specific enough that two principles
             #   with overlapping conditions don't silently contradict each other.
  reason: # WHY. The justification that generalizes. This is the most important field —
          #   it lets the principle be weighed against the present case rather than
          #   obeyed mechanically. A rule without its reason is dogma.
  provenance: # WHERE it came from. Date, task, context. For audit and trust.
  see-also: # OPTIONAL. ids of related principles (same domain or another domain).
```

Notes on fields:

- **condition** is structurally the most important. When two ratified principles in a domain have
  conditions that partition the same space and give opposing advice, the corpus is telling you the
  domain has become two — a fork candidate.
- **reason** travels with the rule always. This is what lets the spawn think rather than pattern-match:
  "the reason was X; this task is Y, so the rule doesn't bind here."
- **provenance** is cheap to record and invaluable for trusting or retiring a principle later.
- A principle does not name its domain in a field — the domain is the *file* it lives in. Moving a
  principle to a better-fitting domain is a file move, recorded in the audit `history`.

### Storage: working vs audit

Working and audit metadata are split so a spawn's working context carries only the fields it weighs
during a task. **File granularity matches load granularity:** working files are per-domain because
the working load is *selective* (only composed domains); audit metadata is one file per layer
because the audit load is *broad* (the whole layer is pulled at once).

- **Working file** (`domains/<domain>.md`) — one per domain. The active `principles:` with their
  `id / rule / condition / reason / see-also` and the `conventions:` list (below). This is the only
  part loaded when a spawn works, inline or spawned. The file ends with an empty `killed:` marker —
  a structural anchor the script's append/count helpers rely on, not storage; kill records live in
  the audit file's kill log.
- **Audit file** (`domains/audit.md`, one per domains-dir — this skill's own and each project's) —
  per-principle `provenance` keyed by `id` (each entry noting its `domain`) and the **kill log** (a
  flat `kills:` list: `id / domain / rule / kill_type / reason_killed / killed`). Loaded only at ratify and retrospective time —
  never in a spawn's working context. The audit file also carries the layer's **counters** — the
  mechanical signals that replace operator feel. **Never write or edit these by hand, including
  when creating a fresh audit file**: `scripts/corpus.py` alone creates them (`measure`) and
  updates them (`record-gate`), inside a marker-delimited block it owns. Shown here for
  reference only:

  ```yaml
  counters:
    - domain: coding-general
      since: 2026-06-20            # last retrospective
      ratified: 3                  # new principles since
      killed: 1
      gate-violations: 2           # violations flagged at ratify-gate audit passes
      working-file-tokens: 3100    # measured at the most recent gate
      baseline-tokens: 2100        # measured at the last retrospective (growth reference)
      principles-at-baseline: 12   # entry counts at the last retrospective — ground truth
      kills-at-baseline: 4         #   for `verify` (ledger must reconcile with the files)

  efficacy:                        # per-principle, incremented at each gate's audit pass
    - id: some-principle
      fired: 4                     # was relevant and the output followed it
      violated: 1                  # was relevant and the output contradicted it
      idle: 9                      # domain was loaded, principle never relevant

  co-occurrence:                   # per unordered domain pair, incremented at each gate that
                                    #   loaded both — mechanical byproduct of record-gate's inputs
    - domains: [color, motion]
      count: 3

  library-drift:                   # project layer only, when has-ui: yes
    since-last-sync: 2             # gates where a handoff's ui-drift.screens or .components
                                    #   was non-empty
  ```

  Efficacy counts must never enter a working file — a spawn that sees them will start writing
  principles that fire often instead of principles that are right. They are audit-layer signals,
  consumed only by the retrospective.

  The script (in the skill repo: `record-gate`, `measure`, `triggers`,
  `lint-deterministic-shortcut-candidates`, `deterministic-shortcut-candidates`,
  `record-deterministic-shortcut-candidate`, `set-deterministic-shortcut-status`, `retro-done`, `sync-done`) does all counting,
  measuring, validation, and threshold math. The model supplies
  judgments as arguments — fired/violated/idle classification, ratify counts — and never does the
  arithmetic or the YAML writing. Bookkeeping done by attention is bookkeeping that silently
  stops. Hand-written provenance, promotions, and per-kill detail live in the same file, outside
  the script's markers — that part of the audit file remains the model's to write.

  Completeness is enforced by **reconciliation**, not interception: `corpus.py verify` checks
  that each working file's entry counts equal its baseline plus the gates recorded since — an
  unrecorded gate (or any write that bypassed the gate) surfaces as a named discrepancy. A
  project-level SessionStart hook (`scripts/session-start.sh`) runs `verify` at every session
  start and announces the project as corpora-managed, so an omission at session end — where
  attention is weakest — is caught at the next session start, where it is strongest.

Kill records live in the audit file, not the working file. The original design carried the
`killed:` log in working files as active guidance — telling the spawn what had been tried and
rejected — but in practice the per-spawn context cost of every kill riding into every composition
outweighed the re-proposal-prevention benefit (operator decision, 2026-08-07). The gate keeps the
protection where it is actually exercised: the ratify gate consults the kill log at audit-load
time, and `ratify-import-candidate` refuses to re-ratify a killed `id` mechanically. Provenance
and promotions likewise stay in the audit file — metadata a spawn does not weigh mid-task.

This is a *storage* split, not a *corpus* excerpt: every active principle is still passed in full
with the fields a spawn reasons over. Working and audit are kept consistent by `id`: every active
`id` in a working file has a `provenance` entry in its layer's audit file, and vice versa.

---

## Spawns: stance + composition

A **spawn** is a stance (see "Generative stance," below) plus a **composition** — the domain subset
applied to the task at hand. Composing is a judgment act: given the unit-of-work and stance, corpora
states the domain subset directly, every time — never through a cached, named intermediate layer. A
spawn is never a persistent named file carrying its own persona prompt and a fixed domain list; two
fixed, universal stance frames exist — convergent and divergent (below) — and everything else about
"what this spawn is" comes from the composed domains themselves, stated fresh for the task.

A composition's domain subset is subject-separated — a spawn never mixes domains from different
subject families (coding and design never co-compose; see "The hard line," below). Stance is a
property of the spawn, not of a domain: a domain carries `posture: guardrail` (every domain in the
corpus today does — see "The hard line") and is available to any composition whose subject matches,
regardless of which stance the spawn runs under. `design-method`, for instance, is a convergent body
of correctness guardrails that loads into both convergent and divergent design spawns; a convergent
domain loading into a divergent spawn is the design working as intended, not a violation. Domains are
not "declared by" a composition the way principles used to be "declared by" a role.

**Recognizing that a task needs a *different* domain subset, not just one more domain, is itself
routing judgment.** A founding-a-library task (standing up a UI or UX library from nothing) needs a
narrower composition than ongoing design work on an established one. The same task-shape question
applies orthogonally to coding work: a task whose actual subject is dependency/version management,
not feature work, needs judgment (`dependency-management`, seeded 2026-07-22) that has no business
loading on every routine coding task just because it's also convergent, stack-agnostic prose. The
fix is composing `dependency-management` instead of `coding-general` for that task shape, not
folding task-specific judgment into `coding-general`'s always-loaded default — a domain composed
unconditionally into every coding spawn should earn that by actually applying to every task of that
shape, not by being convergent and general-sounding. Stack-shape (framework/styling/language)
already conditions which domains a coding composition includes (`coding-nextjs` only when
`framework: nextjs`, etc.); task-shape is the same kind of conditioning, checked against what the
task is actually about instead of what the project is built with.

**The composition is deterministic, not a self-selected runtime relevance call by the working
agent.** `select` fixes which domains apply before the spawn runs; the choice is inspectable after
the fact via the handoff's `domains-loaded:` field. The `unit-of-work` a composition is *for* is
decided by the process layer (a routing judgment); corpora turns that unit into a domain set, and the
domain set alone is corpora's to state.

Multiple domains compose into one spawn whenever a task's coupling warrants it — a
gesture-transition task might load `motion` + `wizards-flows` + `ranking-evaluation` together in one
divergent spawn. There is no separately-named grouping to be "forced across"; corpora states
whatever subset the task needs directly, every time (see LINEAGE.md, "Lenses retired").

### Two load modes

- **Working load** (generation): a spawn's composed domains, *working files only*. Lean and
  inspectable. This is every new isolated spawn and every inline spawn segment.
- **Audit load** (synthesis, human-gated): at ratify and retrospective time, relevant domains are
  loaded *broadly, including audit and kill metadata*. Breadth is safe here because it is not
  constrained generation and it is gated by the operator.

Composition enforces load boundaries: a coding-stance spawn loads coding domains and never design
domains. Whether two spawn segments may share a context, and whether a handoff checkpoint ends or
continues an agent, is the process layer's routing judgment, not corpora's — corpora only states the
composition each segment loads.

### Generative stance

Every spawn has a `stance:` — how it generates. There are two, and they are opposite:

- **convergent** — the value of the output comes from *matching a standard*: correctness, idiom,
  fit. Coding, UX-flow, planning, and orchestration work are convergent. For a convergent spawn,
  regression toward the training mean is frequently the *right* answer; there is no anti-mean anchor.
- **divergent** — the value comes from *differentiating from the standard*: a distinctive identity.
  Visual/UI-identity work is divergent. A divergent spawn carries an **anti-mean anchor**: before
  committing to a direction it must name at least one safe/expected default that should *not*
  apply, because a generative model otherwise drifts to the average of its training data — the
  forgettable answer. (History: LINEAGE.md.)

Stance is a property of the **spawn** (the generating agent, for this task), not of a domain.
Principles, by their nature — a weighable rule with a condition and a reason — overwhelmingly
encode *convergent* correctness; that is what crystallizes into a rule. The divergent element is a
generative *stance*, not a body of principles. So domains are mostly convergent guardrails,
consumed by spawns of either stance, and the anti-mean anchor lives on the divergent stance and
fires at the generative moment.

**The hard line:** a single domain must not bundle principles that demand *opposite* generative
stances to apply — a "resist the standard" instruction sitting beside "match the standard" rules is
incoherent, since the agent cannot hold both stances at once. In practice this means a domain
declares `posture: guardrail` (a convergent body of correctness rules, consumable by either stance)
or, hypothetically, `posture: generative` (a body that itself demands the anti-mean anchor). No
domain in this corpus is `posture: generative` today — the anti-mean anchor lives on the divergent
stance frame itself, not on any domain — so a proposal arriving with `posture: generative` is a
ratify-gate rejection on sight; it belongs on the stance frame, not a domain. This is a narrower
claim than stance-matching at the composition level: the hard line is about what a single domain is
allowed to bundle, not about which domains a given spawn may load together (that is subject
separation, above). The sharpest composition-level case is that coding judgment and
visual-aesthetic judgment never share a domain — coding-subject and design-subject domains never
co-compose. At the ratify gate, a proposal that wants a home in a domain whose principles pull the
opposite way is a signal the domain or the proposal is wrong — surface it (a fork candidate), do not
force the fit.

---

## Corpora's part in the spawn brief

The process layer states each spawn in a short fixed-field brief — `stance`, `unit-of-work`,
`domains`, `expected-output`. Corpora owns exactly one of those fields:

```yaml
stance: divergent
unit-of-work: design-ui-surface
domains: [color, visual-hierarchy, motion]   # ← corpora's field
expected-output: "Design spec for the settings-panel color treatment."
```

**`domains` is what `scripts/corpus.py select --unit-of-work <unit-of-work>` returns** for the
project's current `.corpora/config.md` — derived and inspectable (re-run `select` and compare), never
a freestanding guess. `stance` and `unit-of-work` come from the process layer's routing judgment;
corpora does not pick them.

`emit-spawn-parts` emits four parts for the process layer to compose: the stance frame, the domain
bodies (byte-for-byte), the handoff-read schema, and **`project-config`** — `.corpora/config.md`
itself. The config part makes "every composition reads `.corpora/config.md`" a delivered fact rather
than a remembered step: the project shape, the deterministic utilities and verification commands,
and the UI/UX library locations ride with the judgment into every spawn.

The composition is not itself a gate. The real gate stays exactly where it already is: the ratify
gate, for anything proposing new corpus content, never for the working composition. A genuinely novel
subject with no existing domain simply runs guardrail-light; the new-domain need surfaces through the
spawn's own proposal at the ratify gate as already designed, with no separate pre-declaration step.

---

## The ratify gate

Every cross-boundary change is **propose → ratify → promote**, never write-directly.

- A spawn proposes a principle as part of its output. It cannot write a corpus.
- The operator (or a ratifying spawn acting under standing rules) reviews and ratifies or rejects.
- **Operator-direct authorship is sanctioned**, not a bypass of this rule: the operator already
  knows a rule they hold — no spawn had to produce it as a proposal first. `corpus.py record-gate
  --ratified 1` runs standalone (no handoff required) with a hand-written provenance entry using
  the convention `"Operator-authored, <date>, based on observed <behavior>, root-caused and
  refined."` What "never write-directly" actually forbids is a *spawn* writing a corpus directly,
  skipping the gate's review — it was never a prohibition on the operator's own hand, which the
  gate exists to serve, not to route around.
- **Rejections are kept** with their reason. The kill log is the highest-signal training data.
- Structural changes (split a domain, add an explorer, change a route) go through the
  same gate.
- This gate is for **principles only** — `proposals:` entries of `kind: judgment` or `kind:
  knowledge`. A design decision (a divergent spawn's identity/aesthetic choice) is never a proposal
  and never passes through this gate at all — see the uiux plugin's design-decision-review phase.

### The genuine-fork test

Before ratifying a `judgment` proposal, ask: is there a plausible alternative choice — one a
competent spawn would actually reach for in the moment — that this principle rules out? If no
realistic version of "the wrong way" exists, the proposal isn't recording judgment; it's
decorating an outcome that was never at risk. Reject these by default, even when the rule is true
and harmless — a principle earns its permanent slot by guarding against a real wrong turn, not by
being correct. The common failure shape is generic good practice restated as project-specific
guidance: watch for a `reason` that names no specific failure mechanism and no plausible competing
choice, only a restatement of the rule itself. This is a different rejection than a `knowledge`
kill (which fires because the answer is derivable from training/docs regardless of whether a fork
exists) — the fork test asks whether a fork exists at all, prior to asking where the answer came
from.

The same test extends to domain **creation**, not only principle ratification: before a new
domain is born at the gate (see "Domain assignment," below), ask whether the proposal is actually
a different subject from every existing domain, not merely a proposal that would read a little
cleaner with its own file. Freer domain creation under the composed-subset model cuts both ways —
it removes the old incentive to force-fit content into an ill-fitting existing container, but
without this check it trades that failure for the opposite one: fragmentation into too many
narrow, single-principle domains. A new domain clears the bar only when an existing domain's
principles would have to bundle opposing generative stances, or a genuinely separate decision
class, to hold it — the same structural-kinship/fork evidence used for domain splits, applied at
creation time instead of split time.

### Domain assignment at the gate

A proposal arrives without a home. At the gate, domain assignment decides which domain it belongs to
and writes it there. If no existing domain fits, a **new domain is born here** —
`domains/<new-domain>.md` (+ audit) is created; the domain becomes available to any spawn whose
stance and subject match — there is no composition declaration to add it to. This is the one point where
domain assignment involves judgment, and it is human-gated. A proposal that spans two domains is a
signal the domain boundaries may be wrong — surface it rather than fragmenting the principle
across both.

A proposal must cite specifically how it matches an existing domain's stated subject — not just
"plausibly fits." This is a cheap, one-line justification the proposer states at write-back time,
not a new tier or gate: it exists to stop content being filed into a domain because the container
looked plausible and was already open, rather than because it is actually the right home. (History:
LINEAGE.md, the v3 transition entry.)

### Write-back format

The **data contracts** a write-back produces — what a ratified principle, a reshaped principle's
history, and a graduated convention look like on disk. The step-by-step operations that produce
them (which `corpus.py` command, in what order, and the hand-fallback where no command exists yet)
live in **`praxis-plugin/phases/ratify-write-back.md`**; this section is the schema those operations write to
and the manual fallback for a domains-dir the script can't reach.

Ratified principle — the working fields, appended to the end of the target domain's `principles:`:

```yaml
- id: principle-id
  rule: "The guidance."
  condition: "When this applies."
  reason: "Why — the justification."
```

The proposal that surfaced the principle carries its `provenance` (captured at proposal time, not
ratification). On write-back, that `provenance` is filed by `id` in the layer's audit file, with
its `domain:` noted. The working file's principle carries no `provenance` field.

When a ratified principle is meaningfully reshaped — generalized, consolidated, split, or **moved
to another domain** — an optional `history:` sub-list is added to its provenance entry. Each item
carries `date`, `type` (generalized / consolidated / split / moved), and `reason`:

```yaml
- id: some-principle
  provenance: "2026-01-01, original task."
  history:
    - date: 2026-06-20
      type: moved
      reason: "Re-homed from ui-designer corpus to the recoverability domain — it is shared with UX."
```

Retired principle — graduated to a convention: a principle ratified long enough that checking its
`condition` before every task is friction without benefit moves from `principles:` to the working
file's `conventions:` list, dropping `condition` and keeping its `id`, `rule`, and `reason`:

```yaml
- id: convention-id
  rule: "The guidance."
  reason: "Why — the justification, unchanged from the principle it graduated from."
  # no condition — unconditioned by definition, applies whenever this domain loads
```

This is not a separate authority tier: a convention doesn't read as more authoritative than a
principle, it is simply unconditioned — checked whenever the domain loads, with no per-case
condition-weighing left to do. Unlike the old fold-to-preamble mechanic, a convention keeps its
`id`: it stays addressable, killable (a convention can still move to `killed:` if it turns out
wrong), and graduatable in the other direction (see "Promotion restraint," below) — dissolving a
principle into unstructured preamble prose loses all three. A `history:` entry (`type:
graduated-to-convention`) on the principle's audit-layer `provenance` record keeps the trail
legible — a principle that reappears as a corpus proposal after graduating is a signal of
regression, not new insight.

A principle that has outgrown its narrow domain — belongs somewhere more general, or warrants a
new domain of its own — is handled by the same mechanism as any other domain reassignment: the
structural-kinship/condensation signal (see "The retrospective," below) and the gate's ordinary
domain-reassignment judgment. No parallel "laws vs. rules" split exists here — an entry exempt
from condition-checking is *more* dangerous, not more trustworthy, and a separate authority tier
would carry an ossification risk not worth taking on.

**Promotion restraint** is the judgment that gates graduation into `conventions:` (applied in
`praxis-plugin/phases/ratify-write-back.md`, "Graduate a principle to a convention"): before graduating, ask
whether the spawn would still need to reconsider this when the project context changes. Graduate
only if the judgment is stable *across the kinds of projects the domain serves* — or is so
foundational that contestability has genuinely become noise — not merely because it has repeated
inside one project family. When in doubt, leave it in `principles:` where its `condition` and
`reason` can still be checked against an unfamiliar case.

### Killed entries

Append to the **kill log in the layer's audit file** — a flat `kills:` list after the
script-maintained block. Working files carry no kill entries; their trailing `killed:` marker
stays empty (it survives as the structural anchor the script's append/count helpers rely on, and
`verify` flags any entry that reappears under it). Kills carry a stable `id` (so they are
referenceable, queryable at the gate's audit load, and traceable if the judgment recurs) and a
`kill_type`:

```yaml
- id: rejected-rule-id
  domain: the-domain
  rule: "The rejected rule."
  kill_type: # quality | container | attribution-noise
  reason_killed: "Operator's reason."
  killed: 2026-07-18
```

- **quality** — the principle was wrong, too narrow, misframed, or already covered. The kill log
  working correctly; highest signal, because it pushes against a model default.
- **container** — the principle was sound but "belonged to another role." Under domain-scoping this
  is no longer a valid reason to kill: such a proposal is *filed in the right domain*, not killed.
  The value is reserved for tagging legacy kills that need re-homing.
- **attribution-noise** — killed by context degradation (e.g. a long multi-domain session), not on
  merit. A *false* kill. The retrospective should surface `container` and `attribution-noise` kills
  for re-examination rather than treating them as settled.

A killed principle's pre-kill `provenance` entry stays in the same audit file, keyed by the same
`id` — the kill record and the provenance record are two entries sharing an `id`, not one merged
block.

Kills lived in the working files until 2026-08-07 as active anti-re-proposal guidance, with a
graduation mechanic (`kill-report`/`graduate-kill`, since retired) that demoted stale kills to
cap the reader-tax. The operator retired the whole carryover: the per-spawn context cost of every
kill riding into every composition outweighed the re-proposal-prevention benefit in practice. The
protection now lives where it is exercised — the ratify gate consults the kill log at audit-load
time, and `ratify-import-candidate` mechanically refuses a killed `id`. A pool predating the move
migrates with `corpus.py migrate` (the kill-log relocation is schema migration 001; see
`praxis-plugin/phases/pool-sync.md` for the full update sequence).

---

## What corpora reads from a handoff

A completed unit of work arrives as a **handoff** — one artifact per unit — from the process layer
that invokes corpora. At the ratify gate corpora is a *consumer*: it reads the proposal-bearing fields
the artifact carries instead of parsing prose. Corpora reads only the fields it declares in its own
handoff-schema manifest (`handoff/plugins/corpora.json`); every other field the artifact carries
belongs to the caller, and corpora leaves it untouched. The fields corpora reads, and how it handles
each:

- **`domains-loaded`** — the domain set the spawn actually composed. Reconciled at the gate against
  what `select` composes today (the co-occurrence and composition-drift signals); a mismatch is a
  real finding, not a formality.
- **`proposals`** — principle proposals, each with `id / rule / condition / reason`, a `kind`
  (`judgment` | `knowledge`, captured by the spawn from the inside — never `direction`; a divergent
  spawn's UI/UX identity choice is never a proposal, see the uiux plugin's design-decision-review phase), and
  `provenance` captured at proposal time.
- **`violations-noted`** — existing principles the work knowingly deviated from, with why.
- **`deterministic-shortcut-candidates`** — observed deterministic-operation candidates (see "Project
  utilities").
- **`ui-drift`** — the library-staleness signal (`screens` / `components`); the UI/UX plugin's sync
  machinery consumes it, not the kernel.

The artifact also carries a freeform **Artifact** section (the spawn's own deliverable) and a
**Surfaced** section (anything fitting no field above, relayed to the operator verbatim). Corpora
reads those as context at the gate; it does not define or validate the artifact's overall shape.

**Compose discipline (corpora's, not the handoff's).** Before a composed spawn finalizes its
deliverable, it re-reads that deliverable against the ratified principles in every domain the
composition included, and revises any violation — catching it here is cheaper than the ratify gate
finding it after the fact. Passing tools (lint, typecheck, tests) is not evidence this happened:
tooling is structurally blind to soft principles (comment discipline, naming, structural
conventions). This is judgment corpora asks of the spawn it composed; the mechanical checks around it
— composition-drift blocking, schema validation, the handoff's own create/relay/close lifecycle —
happen outside corpora and are not the kernel's concern.

---

## Deferred UI/UX decisions

The non-blocking UI/UX decision queue (`.corpora/deferred-decisions.md`) is a **UI/UX concern**, so it
is not part of the judgment core — it ships with the UI/UX plugin, whose `deferred_queue.py` owns the
schema and its `lint`/`list`/`resolve`. The kernel only notes it exists: an entry a spawn defers here
is marked `resolved` once the operator's review settles it (a ratified principle, or an accepted
design decision at design-decision-review), recording HOW it was settled and **kept as a trace, not
deleted** (the backward spine — a later pass sees the question was raised and its resolution).
Durable direction still lives in the UI/UX libraries and the corpus (where a spawn loads it), never in
the queue.

---

## Project utilities

Active utilities live tersely in the `utilities` section of `.corpora/config.md` because every spawn
may need them. They are project-owned deterministic tools that replace recurring, precision-sensitive,
or disproportionately token-expensive inference. Environment-owned tools are discovered from the
current runtime instead.

Candidates live separately in `.corpora/deterministic-shortcut-candidates.md` so cheap denials and recurrence
evidence survive handoff deletion without taxing every spawn's load:

````markdown
# Deterministic shortcut candidates

```yaml
candidates:
  - id: color-math
    operation-shape: "Deterministic perceptual color transformation and compositing."
    status: denied
    evidence:
      - date: 2026-07-14
        workstream: settings-redesign
        burden: "Several rounds of manual color derivation."
    disposition:
      reason: "Not enough expected reuse yet."
```
````

Surface a plausible candidate whenever denial is cheap. Before recording it, check the standard
library, installed dependencies, current runtime tools, and active project utilities. The operator
accepts, denies, or defers it. Record evidence with `corpus.py record-deterministic-shortcut-candidate`; the script
derives sighting count and first/last dates and resurfaces recurrence or a prior denial. Record the
operator's disposition with `corpus.py set-deterministic-shortcut-status`. Only an accepted utility that is
implemented and tested enters config. Denied candidates remain historical memory; retrospectives
may consolidate duplicates or obsolete entries. Candidate status is `open`, `deferred`, `denied`,
`accepted`, or `implemented`.

---

## Project corpora

In any project using this system, project-specific accumulated judgment lives under
`<project-root>/.corpora/domains/`, one working file per domain (`<domain>.md`) plus a single
`.corpora/domains/audit.md` for the project layer, same schema as any other layer. The kernel is the
mechanism (schema, ratify gate, retrospective, lifecycle) and is indifferent to how many domains
exist or which repository holds them.

A project's own `.corpora/domains/` is the whole domain set that project's spawns compose from —
`select`, `emit-spawn-parts`, and `manifest` all read only it (or an explicit `--domains-dir`
override). There is no live, automatic merge with this skill's own `domains/` or with any other
project's corpora: every corpora-managed location is symmetric — a `domains/` + `audit.md` pair,
readable and importable the same way regardless of which repository holds it, imported through the
same mechanism whether the source is this skill's own `domains/`, another project's
`.corpora/domains/`, or a formalized sibling section of the same project (`--root-name`, "Monorepo
root resolution," below).

**There is no privileged layer a principle gets "promoted" into.** Two things do live in this
skill's own `domains/` that are genuinely special to this repository, but for a different reason
than privilege: `ratify-gate`, `principle-judgment`, and `retrospective` are
corpora's *own* operating judgment — `SKILL.md` loads them directly, always, regardless of which
project is running, because they are what makes corpora corpora (`SKILL.md`, "## domains"). Every
other domain here (`coding-general`, `testing`, `css`, `color`, ...) is ordinary importable
content, symmetric with any project's own domains-dir — bootstrap suggests importing from it on day
one because it already holds broadly useful starter content, not because it occupies a structurally
privileged position.

A freshly-bootstrapped project therefore starts with an empty `.corpora/domains/` and imports what
it needs — either the default-pool bulk import bootstrap offers, or picking individual principles
and conventions from any domains-dir later (`corpus.py import-list` / `import-candidate` /
`ratify-import-candidate`, "Import," below). The same mechanism runs in the other direction too: a
project's own well-earned principle propagates elsewhere — into this skill's own `domains/`, into a
sibling project, into a formalized section of the same project — by being imported there, exactly
like any other candidate; `domains/retrospective.md`'s `complementary-principles-signal-abstraction-
candidate` is what a retrospective looks for when deciding whether a principle is actually worth
proposing for reuse elsewhere, in place of the retired seed/project layer distinction (`LINEAGE.md`
has the retirement's reasoning). A project bootstrapped under the older, live-merge model migrates
once via `praxis-plugin/phases/domain-repo-migration.md` before its first session under this model — that
process materializes its previously-live seed content into its own `.corpora/domains/` so nothing it
already relied on silently disappears.

A project that wants to track this skill's own domain content as it evolves, rather than
snapshotting it once at import time, re-runs the default-pool import periodically (or per updated
principle) — the same mechanism, not a separate sync feature. This replaces the older per-domain
fork mechanism (`corpus.py adopt`), retired 2026-07-22 for never having been exercised by a real
project and for solving a problem — merge-time conflict — that live concatenation never actually
created; see `LINEAGE.md`.

### Import

An import never writes a domain working file directly — it is a new *producer* of candidates,
structurally the same relationship `reading/discovery-agent.md`/`reading/session-harvest-agent.md`
already have to a candidates file and the ratify gate. The difference is what's being proposed: not
a freshly-mined judgment call, but an *already-ratified* principle or convention from another
corpus, re-proposed here with provenance recording where it actually came from. **Procedure:
`praxis-plugin/phases/domain-import.md`** — this section is the command reference and candidate schema it
points into, not the step-by-step sequence.

- `corpus.py import-list --source <domains-dir>` — read-only. Lists every principle and convention
  under `<domains-dir>`, flagging which ids already exist anywhere in the target project's own
  `.corpora/domains/`. Proposes nothing; for browsing before picking.
- `corpus.py import-candidate --source <domains-dir> --domain <d> --id <id> [--as-domain <d2>]
  [--as-id <id2>]` — proposes one entry as a candidate, appended to
  `.corpora/import-candidates.md` (created on first use), with an `imported-from` provenance block:

  ```yaml
  - id: [kebab-case-slug]                 # may be renamed at import time if it collides
    rule: [...]
    condition: [...]                      # omitted for a convention import
    reason: [...]
    domains: [proposed destination domain — operator's choice, not necessarily the source's]
    kind: judgment
    provenance:
      imported-from:
        source: [path to the source domains-dir]
        domain: [source domain name]
        id: [source id, if renamed on import]
        originally-ratified: [source's own provenance date, if available]
      extracted: [YYYY-MM-DD]
  ```

  `kind: judgment` by default — the entry already cleared the fork test once, in its source corpus;
  the fork test (`domains/principle-judgment.md`) is still available if the operator wants to
  re-examine it rather than rubber-stamp it.
- `corpus.py import-default-pool [--source <domains-dir>]` — the bootstrap fast path: proposes
  every principle and convention from every domain in the source (this skill's own `domains/` by
  default) whose `applies-when` already matches the project's `.corpora/config.md` shape, or is
  `universal`, skipping anything the project already has by id. One batch, still individually
  ratifiable — not a bypass of the gate, just the operator's answer defaulted to "yes to all"
  instead of asked one at a time.

Write-back from `.corpora/import-candidates.md` follows the ordinary write-back format, above — the
`imported-from` block is additional provenance, not a different write path.

### Monorepo root resolution

A monorepo may have more than one `.corpora/config.md` — an app-scoped one (`admin/.corpora/`) and a
root-level one, or several sibling apps each with their own. `scripts/corpus.py` resolves which
root governs a given file by nearest-ancestor walk from the file up toward the filesystem root,
stopping at the first `.corpora/config.md` found — the same model `tsconfig.json`/`package.json`
resolution already use. This resolves automatically; there is no manual `sibling-corpora:`
declaration to keep in sync, deliberately, so the check can't go stale the way a hand-maintained
list would.

**`--for-file <path>` is the standard way to invoke `corpus.py`** for any real task, in place of
computing and passing `--root` by hand: pass any file the task touches (a target file, or the
first one named in the task description) and every command resolves the right root itself before
doing anything else — no caller needs to work out which root governs a
task as a separate step. `--root` still exists for the cases `--for-file` can't cover: bootstrapping
a brand-new nested root (nothing to resolve to yet, since its `.corpora/config.md` doesn't exist
until that bootstrap writes it), or operating on a `--domains-dir`/`--audit` override that isn't
tied to any one file (`migrate-kill-log`, working this skill's own `domains/` directly).

`corpus.py resolve-root --file <path>` and `corpus.py check-root-boundary --files <f1,f2,...>`
remain available directly for the narrower cases `--for-file` doesn't cover on its own: inspecting
which root a file would resolve to without running a command against it, and — the one still-manual
step — checking whether a task's *several* touched files all resolve to the *same* root before
composing a single spawn. `--for-file` only resolves one path; a task spanning multiple files still
needs `check-root-boundary` to catch the case those files disagree about which root governs them,
since a spawn's composition can only ever be one root's domains (`select`/`emit-spawn-parts`
take one `--root`). This is the same shape as subject separation (`check-composition` — a spawn
never mixes coding and design domains), just on a different axis: a task spanning two corpora roots
is two units of work, one per root, sequenced by whichever the planner judges dependent — not a
single spawn straddling both.

**Dispatching deliberately into a sibling section is the opposite direction** from all of the
above: not "which root governs this file I already have," but "which root is the section I mean to
target, before I have any file in it yet." Mechanical only — no judgment domain, since deciding
*whether* to dispatch into another section is still ordinary routing/planning judgment; only
resolving a name to a path is new. `corpus.py list-roots [--search-from <dir>]` walks *downward*
(the mirror of `resolve-root --file`'s upward walk) from `--search-from` (default cwd), skipping
vendor/build directories, and lists every corpora root found as `name: path`. A root's name is its
declared `name:` under `## project-shape` in its own `.corpora/config.md` if present, else its
directory's basename — every root is nameable with no config change required.
`corpus.py resolve-root --name <name> [--search-from <dir>]` resolves one named root's path
directly (fails, listing what's available, on no match or an ambiguous one). The top-level
**`--root-name <name>`** flag is the standard way to actually invoke a command against a named
sibling root — `corpus.py --root-name admin select --unit-of-work implement-feature` — the same
convenience `--for-file` is for the upward direction; mutually exclusive with `--for-file` since
they answer different questions. A task whose planner has already decided it needs work done in
another section names that root; nothing about *finding* it should require the dispatching agent
to already know or hardcode the sibling's filesystem path.

### One flat domain pool

This skill's own `domains/` is one flat pool — no separate "role pack" layer selected by a project-config
field. A stack-agnostic domain (`coding-general`, `planning`, `spawn-integrity`, ...)
and a stack-specific one (`coding-react`, `css`, `color`, ...) live side by side; each states its own
load condition as `applies-when` frontmatter against `.corpora/config.md`'s existing project-shape
fields (`language`, `framework`, `styling`, `has-ui`) — `coding-nextjs` loads when `framework:
nextjs`, `css` loads when `styling` is not `none`, and so on; `scripts/corpus.py select` evaluates
these mechanically rather than a reader checking prose (see "Spawns: stance + composition," and
`scripts/corpus.py`'s `select`/`manifest` commands). Retired 2026-07-22: an earlier `role-pack:`
field bundled a stack's domains behind one coarse flag, gating them all-or-nothing; since every
domain already carried its own precise condition, the field added an indirection without adding
information, and it couldn't express a project needing some but not all of a stack's domains. A
project with no UI simply never composes divergent visual-identity domains into a spawn — nothing
gates that on a config field at all, since nothing routes work into them.

That original reasoning was specific to who was consuming the condition: true while the only
consumer was a reader checking prose before a spawn, since a coarse `role-pack:` flag genuinely
added nothing over precise per-domain prose read the same way either form. It stopped being the
whole story once a process layer needs to select domains without reading prose at all (2026-07-29,
"Promote load conditions to frontmatter") — at that point the condition has to exist in a
machine-evaluable form regardless, and `applies-when` frontmatter is that form. This isn't a
reversal of the `role-pack:` retirement — a coarse all-or-nothing flag would still be strictly worse
information than per-domain `applies-when` predicates — it's the same conclusion holding for a new
reason once the requirement changed. See `LINEAGE.md` for both entries.

---

## The retrospective

Run at two cadences. Same faculty, different direction.

**Forward (per-task):** compose the right domains for the task's stance and unit-of-work. Guard
against contamination — is the working context holding domains from another mode?

**Backward (periodic):** surfaces signals as proposals for the operator — contamination, domain
tension, convergence, composition drift, complementary-principle abstraction candidates, structural
kinship, anti-overfitting, and efficacy interpretation. See `praxis-plugin/phases/retrospective.md` for the trigger
and procedure, and `domains/retrospective.md` for the judgment behind each signal — what counts,
what doesn't, and why. Two adjacent signals (a misplaced principle, and a ratified principle whose
gate-time discipline may have lapsed) are judged by `principle-judgment` instead, since they're
about one principle's own fitness rather than a pattern read across a domain's history.

Each domain working file carries `last-retrospective: <date>` at the top to make convergence measurable.

---

## Domain lifecycle

```
spawn (stance + composition)
  → accumulate (work + retrospective surface principles; operator ratifies into domains)
  → [retrospective may propose SPLIT if a domain develops tension, FORK if the split tracks a
     project-local seam]
  → converge / lock (domains stabilize, corrections rare)
  → [retrospective proposes pairing with an EXPLORER]
```

Growth is differentiation under accumulated tension — never promotion up a ladder, never an org
chart imposed in advance.

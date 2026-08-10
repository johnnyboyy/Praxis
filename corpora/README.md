# corpora

### A system for accumulating learned judgment across agent sessions and projects

Instead of an agent re-deriving the same correction every session, or a project's conventions living
only in one person's head, judgment gets written down once, weighed against new cases, and kept or
killed based on whether it actually holds up.

## Why this exists (I wrote this)

AI agents, really Claude Code in particular, is a new kind of tool. I felt I needed to learn how to
use it as much as it needed work to be geat. This is a colleciton (probably not exhaustive) of all
those lessons I've learned along the way. Including the ones Claude Code taught me about my own
rules and principles from my time as a software engineer.

- **Reason and condition over hard instructions.** This grew from having hard instrstructions to
  force my own rules onto Claude Code. I had very good reasons for it, but I couldn't be sure they
  were *the best rules ever*. It would struggle to follow them anyways; or over apply them. Until
  one day I asked it why it was doing what it was doing. I dont't remember the answer. The point was
  I broke down each rule with it's reason, and it said the reason was doing much more work than the
  rule on it's own. Not only that, it was able to find a meta-principle that all my rules were
  pointing towards: The Reader Tax (Explicit by Default). It taught me something new and interesting
  about my own thinking. I wanted it to do that more, and that's when this project started.
- **Some Agents hate to read.** (Codex). I could not get Codex to cooperate with the system. The
  whole *full corpus on spawn* thing was meant to be a guard against pointing to a file and hoping
  that the agent would not just skim it or skip it altogether. If it was in the spawn prompt, it
  was at least guaranteed to be in the context. But even then it seemed to be skimming or ignoring
  the reading. I wasn't able to get it to use the rules the way Claude Code does.
- **Convergent vs. divergent stance.** I noticed that doing design work followed by implementation
  in the same context window was incredibly painful. It's married to the design it creates, and the
  "stances" as I've taken to calling them (Claude's name) do NOT mix well. Convergent is correctness.
  You want your code to be correct. Divergent is creative. You do not want your code to be creative.
- **Overstuffed context.** You can notice it when Claude Code starts answering in long, drawn out
  responses. I assume this is it's way of trying to keep attention on the current ask, and the sheer
  size of the context before it means it needs a lot more bulk just to stay on track. This also means
  that principles loaded will get less notice, and not be followed. So there's a principle that watches
  for these symptoms, suggest the agent find a good place to stop work, and ask for a fresh spawn to
  continue where it left off.
- **Making a script is a good option.** Codified in the `deterministic-shortcut-candidates.md` mechanism. Anything
  you can move out of Inference into something Deterministic is a good thing. For one, you're saving
  tokens. But also, you're saving time and getting better results. This came from asking Claude Code
  to give me three colors from one - a warmer and cooler variant. It was spinning like crazy on that
  task and the colors is made were awful. When probed, it said it had to "guess a warmer color, then
  check if it actually was," and essentially loop that until it thought it had something. A quick
  color utility script later and I had 9 full color scheme options for a 10th of the cost. And they
  didn't suck!
- **You can eat other skills!** You can mine other skills for new principles and domains! Other people
  have good ideas too, believe it or not.
- **It can review it's own plan.** Typically, I ask it to make a high-level plan, and then do a pass
  for any gaps or improvements. It's never come back without something. That's codified in a planning
  principle.
- **Propose → ratify.** Claude does not always propse good things. Sometimes, it even does
  bad or ugly things. The Operator (you) is the standing guard against a bad corpus.
- **Rejections are kept, with their reason.** This might get cut or eventually moved fully to the
  auditing section. I've been told it's both useful and not useful, and I haven't had enough data
  to really tell. There's a new system in place to track how long they sit and if they matter in a
  task. After so many sessions, they move out to the audit anyways. If that's the consistent pattern,
  then that can become the default.

If you don't want to take the system as a whole, I hope you can at least take something from these
lessons. I've always wanted to meaningfully contribute something to the field of software. I hope
this can go at least a small way towards that.

## The system (Everything below is Claude Code)

Judgment lives in **domains** — corpora scoped to one subject matter or decision class. A
**spawn** (the process layer's unit of work) is a *stance* (convergent or divergent — `kernel.md`,
"Generative stance") plus whatever domain subset corpora composes fresh for that unit of work,
stated directly in a spawn brief every time. The shared mechanism — schema, ratify gate,
retrospective — is the **kernel**.
This repo's own `domains/` carries general principles earned from real work; a project imports what
it needs into its own `.corpora/domains/`, which is then the whole domain set that project's spawns
compose from — no live merge with this repo. Every domains-dir is symmetric, this repo's included:
there is no privileged "seed" tier a principle gets promoted into. (A couple of domains here are
special for a different reason — `ratify-gate` and `principle-judgment` are corpora's own operating
judgment, loaded directly regardless of project, not a privileged pool.) A principle ratified in a project
propagates elsewhere — into this repo, into another project, into a formalized sibling section of
the same project — by being imported there, the same mechanism as any other candidate, when a
retrospective finds it's jointly necessary alongside another principle for a test neither states
alone. A principle can also graduate into a domain's own `conventions:` list once it's stabilized
into unconditioned guidance that no longer needs per-task condition-checking. Rejected principles
are kept with their reason and a `kill_type`.

Domains own corpora, so shared judgment lives once and is available to any spawn whose stance and
subject match (a divergent UI-composed spawn and a convergent UX-composed spawn both load
`recoverability`, for example, without either one "owning" it). Domain boundaries are discovered
from accumulated tension — the fork signal in the retrospective.

### Architecture

**One flat domain pool; corpora is the judgment layer the process layer invokes:**

- **Corpora** (`SKILL.md`, loads `ratify-gate` and `principle-judgment` as its own operating
  judgment) is invoked by a separate process/orchestration layer (praxis) that owns routing,
  spawning, and deciding units of work. Corpora composes the domain set for a unit of work and runs
  the ratify gate; it does not take on a spawn's stance itself and does not route or spawn. The
  **planner** composes `planning` + `interviewing` like any other spawn, decided fresh by the
  process layer's routing judgment. Every working spawn composes from `coding-general` at minimum.
- **Domains** — stack-agnostic (`coding-general`, `spawn-integrity`, ...) and stack-specific
  (`coding-react`, `css`, `color`, ...) domains live together in one flat `domains/`. Each
  stack-specific domain states its own load condition as `applies-when` frontmatter against
  `.corpora/config.md`'s shape fields (`language`, `framework`, `styling`, `has-ui`);
  `scripts/corpus.py select --unit-of-work <u>` evaluates every domain's condition mechanically and
  returns the composed subset.

The process layer states a stance and unit-of-work in the spawn brief for every task, and invokes
corpora to fill the domain subset. `coder`, `ux-design`, `ui-design`, and `planner` name recurring
task shapes in prose (see `LINEAGE.md` for history). One composed spawn per recurring task shape
runs at a time per project; a domain splits into scoped instances when the retrospective surfaces a
fork signal — conditions that partition the space and give opposing advice.

**Domains (where judgment lives):** every domains-dir is the same shape — a `domains/` + `audit.md`
pair — whether it's this skill's own flat `domains/` (general principles, plus the domains corpora
itself depends on: `ratify-gate`, `principle-judgment`) or a project's own
`.corpora/domains/<domain>.md`. Nothing is a privileged "seed" source; this skill's own pool is just
a convenient default a project's bootstrap suggests importing from on day one.

A project's own `.corpora/domains/` is the whole domain set its spawns compose from — no automatic
inclusion of anything else. A project may have domains with no counterpart in this repo at all
(project-specific subjects, e.g. `spatial-metaphor`), imported principles from another project's
corpora, or principles it wrote itself.

**Two load modes** (file granularity matches load granularity):

- **Working load** — a spawn's composed domains, *working files only* (`domains/<domain>.md`).
  Selective and inspectable; this is every new isolated spawn and inline segment.
- **Audit load** — domains are read broadly *including* `domains/audit.md` (provenance, kills) at
  ratify and retrospective time.

**Spawn contexts.** Each spawn receives its stance frame plus every composed domain. Whether to run
inline, resume the agent owning the workstream, or start an isolated agent is the process layer's
routing decision, not corpora's; handoffs are checkpoints, and operator testing and revisions
return to the owning agent. See `LINEAGE.md`, "Role isolation."

### Files

- `SKILL.md` — the shared corpora entrypoint for Claude Code (`/corpora`) and Codex
  (`$corpora`): what corpora owns and what it doesn't, its judgment ("what you do"/"what you
  don't do"), and the config-file schema. Points to the routing plugin's `operation` phase for the
  procedure itself.
- the routing plugin's `operation` phase — the session and per-spawn procedure the process layer drives
  when it invokes corpora, in phases: session entry, routing, spawn composition, execution, relay,
  the ratify gate, post-gate maintenance, and the retrospective.
- `kernel.md` — the schema, stance+composition model, ratify gate, write-back format, two load
  modes, and domain lifecycle. Reference document.
- `praxis-plugin/phases/retrospective.md` — the periodic, backward-looking counterpart to per-task routing: trigger,
  composition, and procedure for reading a domain's accumulated corpus and gate history.
- `praxis-plugin/phases/domain-import.md` — the procedure for pulling already-ratified content from another
  domains-dir into a project's own `.corpora/domains/` (bootstrap's default-pool pull, a later
  individual pick, or a live-merge-model migration) through the ordinary ratify gate. Mechanical;
  `kernel.md`, "Project corpora → Import," holds the command syntax and candidate schema this
  points into.
- `domains/` — every domain this repo carries, flat: stack-agnostic (`coding-general.md`,
  `orchestrator-routing.md`, `ratify-gate.md`, `principle-judgment.md`, `retrospective.md`,
  `testing.md`, `planning.md`, `interviewing.md`, `spawn-integrity.md`) and stack-specific
  (`coding-ts.md`, `coding-react.md`, `coding-nextjs.md`, `css.md`, and the design domains
  `color.md`/`motion.md`/`recoverability.md`/ etc.) alike, each stating its own
  `subject`/`posture`/`applies-when`/`units-of-work` frontmatter. Plus `audit.md`
  (provenance/kill detail for the layer, loaded only at ratify/retrospective time).
- `praxis-plugin/phases/runtime-verification.md` and the `testing` phase — the processes that apply
  `testing.md`'s judgment: driving a real surface before a runtime-observable change can be
  reported complete (required, not optional, at every coder checkpoint), and — in the consolidated
  `testing` phase, which folds in the former test-writing / test-coverage-audit / integration-test
  procedures — when and what to write or audit for test coverage.
- the `engine-bootstrap` phase — one-time project setup, process/procedure only. Phase 1 detects
  project shape and writes `.corpora/config.md` (via `corpus.py init`). For `has-ui: yes` projects it
  routes into the design plugin's `library-init` phase — the one phase that consolidates the former UI
  library, screenshot-cache, and UX library inits — which proposes the starter design principles.
- the design plugin's `library-sync` phase — the ongoing counterpart to `library-init`: brings each
  library or the screenshot cache back in line with the project's actual state after drift
  accumulates. Triggered from the routing plugin's `operation` phase's ratify gate.
- `reading/` — the reading pipeline, self-contained and independently scheduled, not part of the
  process layer's own per-spawn loop: `discovery-agent.md` (finds sources), `reading-agent.md`
  (extracts candidates from queued sources), `session-harvest-agent.md` (mines past session
  transcripts for judgment exercised but never proposed). All three feed `reading/candidates.md`,
  which the routing plugin's `operation` phase's ratify gate checks like any other proposal source. The
  quality-filter and mining judgment behind the first and third live in
  `domains/principle-judgment.md`, not in the agent files themselves.
- `LINEAGE.md` — intellectual history: why conventions became law, key kills, design decisions.
- `reader-tax-and-the-model.md` — a living, multi-model assessment of whether Explicit by Default
  helps the model itself, not only the human reviewer.

### Installation

Clone this repository once, then symlink the same working copy into either or both skill directories:

```bash
ln -s /absolute/path/to/corpora ~/.claude/skills/corpora
ln -s /absolute/path/to/corpora ~/.codex/skills/corpora
```

Claude Code invokes it as `/corpora`. Codex invokes it as `$corpora` and may also activate it
implicitly. A managed project's `AGENTS.md` can opt into automatic Codex activation with the
one-line instruction offered by the skill.

**Diverging from the shared skill.** A project's own `.corpora/domains/` never automatically tracks
this repo's `domains/` — it only holds what was explicitly imported (`kernel.md`, "Project
corpora"). A project that wants to track the skill's evolving default pool re-runs that import
periodically; one that wants a frozen snapshot simply doesn't. Symlinking vs. copying this repo
into `~/.claude/skills/corpora` only affects whether the *mechanism itself* (kernel, process files)
updates — not domain content, which every project already controls per-import.

### Using in a project

1. Invoke corpora on an unbootstrapped project. When `.corpora/config.md` is absent, bootstrap runs:
   Phase 1 writes stable project shape, commands, and registered utilities; UI projects then route
   divergent- and convergent-composed bootstrap workstreams for their libraries.
2. On subsequent invocations, the process layer routes work inline, to an existing workstream agent,
   or to a new isolated spawn, invoking corpora for each spawn's composition. A plan starts a new
   coder-composed workstream; testing feedback and revisions return to its owning agent.
3. Handoffs surface proposals, violations, deterministic shortcut candidates, and other routing
   material. The operator ratifies corpus principles at the ratify gate, and separately reviews
   design decisions (accept / revise / reject) at design decision review.
4. `.corpora/domains/<domain>.md` holds project-specific principles. A domain file is created on
   first ratification into it, and every ratified proposal is assigned a domain at the gate.

**Project files** (all under `.corpora/` in the target project):

- `config.md` — stable project shape, registered deterministic utilities, library paths, and
  verification commands
- `ui-library.md` — design system documentation (generated by bootstrap, updated by designers)
- `ux-library.md` — experience patterns and flow documentation for UI projects
- `deferred-decisions.md` — non-blocking UI/UX questions waiting for a coherent designer workstream
- `deterministic-shortcut-candidates.md` — persistent accepted, denied, and deferred utility observations
- `handoffs/` — unratified spawn checkpoints and their pending gate material
- `domains/<domain>.md` — per-domain accumulated judgment (working fields only)
- `domains/audit.md` — provenance and per-kill detail for the project layer

See `kernel.md` for the full principle schema and write-back format.

### Validation

Run the dependency-free regression suite with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

### Cross-project learning

There is no separate promotion process or privileged destination — a principle propagates
elsewhere the same way any candidate does, through `corpus.py import-candidate` /
`ratify-import-candidate` (`kernel.md`, "Import"), whether the destination is this repo, another
project, or a formalized sibling section of the same project (`--root-name`).

The retrospective is the natural trigger for *noticing* a candidate worth proposing, but the bar
isn't one principle's condition merely reading stack-agnostic — that's weak evidence, since a
condition can read general and simply not have hit its edge case yet.
`complementary-principles-signal-abstraction-candidate` (`domains/retrospective.md`) is the actual
test: two or more principles — same domain or different, same project or an already-imported one —
that are jointly necessary for a test neither states alone. The shared abstraction they jointly
imply is what gets proposed as a candidate, then ratified through the ordinary gate like anything
else.

### New stacks and domain splitting

**New stack:** the kernel applies unchanged — every new project inherits the process layer, the
planner, and `coding-general` for free. Add stack-specific domains (with their own load
conditions against `language`/`framework`/`styling`) once a body of stack-specific conventions has
accumulated and is worth shipping across projects of that stack. Until then, project-earned
specifics live in `.corpora/domains/coding-general.md` (and project-specific domains). Do not
pre-build stack-specific domains speculatively.

**Domain splitting:** new judgment lands in the domain it's about (a new domain is born at the
ratify gate when nothing fits, after clearing the genuine-fork test — see `kernel.md`, "The
genuine-fork test"). A domain splits into scoped instances when it develops a genuine fork signal —
conditions that partition the space and give opposing advice. Reach for this when accumulated
tension reveals the seam.

## License

MIT — see `LICENSE`.

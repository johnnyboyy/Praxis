# Praxis plugins — the Contributor contract

A praxis plugin provides one or more **Contributors**. A Contributor injects context
into a unit of work (per phase) and/or reacts at named workflow steps. Praxis
discovers Contributors from the root's `.praxis/config.json`, loads them fail-soft, and
composes their contributions during a run.

## The Contributor contract

A Contributor is any object with:

- `source: str` — non-empty identifier for the plugin (namespaces its config and
  tags its contributions).
- `contribute(situation) -> list[Contribution]` — **required.** Called once per
  phase with `situation.phase` set to the **stance** (`divergent`, `convergent`, or
  `none`) — always a stance, never a phase name. Return the context to inject; return
  `[]` to inject nothing. `contribute` may also branch on `situation.phase_name` — the
  **named** phase channel — when a named workflow is driving the run; it is `None`
  outside a workflow run (i.e. `phase_name is None` means "no named phase; behave as in
  single-dispatch").
- `hooks(self) -> dict[str, StepHook]` — **optional.** Maps step names to callbacks.
  Absent is fine; when present it must be callable.
- `surface(situation) -> list[str] | None` — **optional.** Returns the edit-lease
  globs this contributor claims for the unit (the paths the gate lets edits touch).
  Absent is fine; when present it must be callable.
- `phases(self) -> list[Phase]` — **optional.** Contributes phases to the phase
  library (merged by `registry.resolve_phases`, seed-wins). When present it must be
  callable.
- `workflows(self) -> list[Workflow]` — **optional.** Contributes workflows to the
  workflow library (merged by `registry.resolve_workflows`, seed-wins). When present
  it must be callable.
- `domains_dir` — **optional attribute** (not callable). Absolute path to a `domains/`
  directory of `*.md` judgment files that **corpora** discovers and composes; a plugin
  that carries no judgment omits it.

```python
@dataclass
class Contribution:
    source: str          # who is speaking
    title: str
    body: str
    priority: int = 0    # lower sorts first when composed
    meta: dict | None = None

StepHook = Callable[[HookContext], None]
```

`Situation` carries the framing of the unit (`task_kind`, `intent`, `subject`,
`phase`, `phase_name`, `root`, `targets`, `workflow`, `label`). `phase` is always a
**stance**; `phase_name` is the **named phase** (or `None` outside a workflow run).

### Steps praxis fires

Praxis fires three named steps through `hooks()`:

- `verify` — after a unit is verified as passing (once per verified pass). Context
  carries `unit`, `receipt`, and the `verdict`.
- `unit-close` — **once per unit**, as that unit finishes (whatever its outcome), on
  every dispatch path (single-dispatch, DAG, orchestrate/cascade, and workflow-driven).
  Context carries the `unit` and its **final `receipt`** (for a workflow-driven unit, an
  aggregate whose `receipt["evidence"]` merges every phase's evidence). This is the
  general per-unit seam any contributor can ride — e.g. a **uiux** staleness/drift
  recorder that bumps counters and marks surfaces stale off the unit's receipt; or a
  **corpora** per-unit harvest / a **metrics** recorder that folds each unit's
  `receipt["cost"]` and `tool_calls` into a running tally.
- `close` — once at the end of a run (batch/end-of-run event). Empty context (no unit,
  no receipt). Use it for run-level rollups, not per-unit work.

Each hook receives a `HookContext`:

```python
@dataclass
class HookContext:
    root: Path
    step: str
    unit: object | None = None
    receipt: dict | None = None
    verdict: dict | None = None

    def add_note(self, source, body, **extra) -> dict   # append to the unit journal
    def notes(self, unit=None) -> list[dict]            # read notes back
```

## Registration

Declare Contributors in the root's `.praxis/config.json` under the `contributors`
namespace — a `name: "module:factory"` entry each. `factory(root)` returns a
Contributor. Loading is fail-soft: a spec that fails to import/instantiate, or whose
result does not conform, is **skipped** (no exception, no aborting the others). With
no `contributors` namespace, nothing loads.

The spec is split on the **last** `:` into module path and factory name, so dotted
module paths work (`my_pkg.plugin:make`).

### Worked example

`.praxis/config.json`:

```json
{
  "contributors": {
    "house": "house_style:make"
  }
}
```

`house_style.py` (importable on `sys.path`):

```python
from contributors import Contribution

class HouseStyle:
    source = "house"

    def contribute(self, situation):
        if situation.subject != "coding":
            return []
        return [Contribution(source=self.source, title="house style",
                             body="prefer small pure functions", priority=0)]

    def hooks(self):
        return {"close": lambda ctx: ctx.add_note(self.source, "run closed")}

def make(root):
    return HouseStyle()
```

## A plugin's own config

A plugin owns the `<source>` namespace of `.praxis/config.json`. Read and write it with
the namespaced store — values are stored raw, so lists and nested objects work, not just
strings:

```python
import config
settings = config.read(root, "house")               # {} when absent
config.write(root, "house", {"strict": True, "exclude": ["vendor", "build"]})
```

## Validation

`validate_contributor(obj) -> list[str]` returns a list of human-readable problems
(`[]` means it conforms). It is structural — it never calls `contribute`. It flags a
missing/blank `source`, a non-callable `contribute`, and any of `hooks` / `surface` /
`phases` / `workflows` that is present but not callable. `contributors_for(root)` runs it on every loaded object and
skips any with problems.

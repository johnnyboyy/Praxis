# Praxis plugins — the Contributor contract

A praxis plugin provides one or more **Contributors**. A Contributor injects context
into a unit of work (per phase) and/or reacts at named workflow steps. Praxis
discovers Contributors from the root's `.praxis/config.md`, loads them fail-soft, and
composes their contributions during a run.

## The Contributor contract

A Contributor is any object with:

- `source: str` — non-empty identifier for the plugin (namespaces its config and
  tags its contributions).
- `contribute(situation) -> list[Contribution]` — **required.** Called once per
  phase with `situation.phase` set (`divergent`, `convergent`, or `none`). Return the
  context to inject; return `[]` to inject nothing.
- `hooks(self) -> dict[str, StepHook]` — **optional.** Maps step names to callbacks.
  Absent is fine; when present it must be callable.

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
`phase`, `project_shape`, `root`, `targets`, `workflow`, `label`).

### Steps praxis fires

Praxis fires two named steps through `hooks()`:

- `verify` — after a unit is verified as passing (once per verified pass).
- `close` — once at the end of a run.

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

Declare Contributors in the root's `.praxis/config.md` under a `## contributors`
section — one `name: module:factory` line each. `factory(root)` returns a
Contributor. Loading is fail-soft: a spec that fails to import/instantiate, or whose
result does not conform, is **skipped** (no exception, no aborting the others). With
no `## contributors` section, nothing loads.

The spec is split on the **last** `:` into module path and factory name, so dotted
module paths work (`my_pkg.plugin:make`).

### Worked example

`.praxis/config.md`:

```
## contributors
house: house_style:make
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

A plugin owns the `## <source>` section of `.praxis/config.md`. Read and write it with
the namespaced store:

```python
import config
settings = config.read(root, "house")          # {} when absent
config.write(root, "house", {"strict": "true"})
```

## Validation

`validate_contributor(obj) -> list[str]` returns a list of human-readable problems
(`[]` means it conforms). It is structural — it never calls `contribute`. It flags a
missing/blank `source`, a non-callable `contribute`, and a `hooks` attribute that is
present but not callable. `contributors_for(root)` runs it on every loaded object and
skips any with problems.

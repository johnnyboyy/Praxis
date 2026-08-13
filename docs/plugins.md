# Praxis plugins — the Contributor contract

A praxis plugin provides one or more **Contributors**: objects that inject context into a unit
(per phase) and/or react at named workflow steps. Praxis discovers them from the root's
`.praxis/config.json`, loads them fail-soft, and composes their contributions during a run.

## The Contributor contract (duck-typed)

- `source: str` — **required.** Non-empty id; namespaces the plugin's config, tags its contributions.
- `contribute(situation) -> list[Contribution]` — **required.** Called once per phase. Return the
  context to inject, or `[]`.
- `hooks() -> dict[str, StepHook]` — optional. Step name → callback.
- `surface(situation) -> list[str] | None` — optional. Edit-lease globs the unit may touch.
- `phases() -> list[Phase]` / `workflows() -> list[Workflow]` — optional. Merged into the seed
  library (seed wins). A `Workflow` may carry a `verifiers` factory (`(root) -> {gate-name:
  Verifier}`) — the gate's form travels with the workflow that needs it (see `plugins/rebuild/`).
- `domains_dir` — optional attribute. Path to a `domains/*.md` directory corpora composes.

```python
@dataclass
class Contribution:
    source: str; title: str; body: str
    priority: int = 0        # lower sorts first
    meta: dict | None = None

StepHook = Callable[[HookContext], None]
```

`Situation` carries the unit's framing (`task_kind`, `intent`, `subject`, `phase_name`, `root`,
`targets`, `workflow`, `label`). `phase_name` is the named phase driving the current step, or
`None` outside a workflow walk — it is the only per-phase channel `contribute` should branch on.

## Steps praxis fires (via `hooks()`)

- `unit-close` — once per unit as it closes (`close_unit` / `record_receipt`, whatever the
  outcome). Context: `unit`, final `receipt`. The general per-unit seam.

(`fire` dispatches any step name, but `unit-close` is the only step core fires today.)

`HookContext(root, step, unit=None, receipt=None, verdict=None)` also exposes
`add_note(source, body, **extra)` and `notes(unit=None)`.

## Registration

Declare Contributors under the `contributors` namespace of `.praxis/config.json` — a
`name: "module:factory"` each (split on the last `:`, so dotted paths work). `factory(root)`
returns the Contributor. Fail-soft: a spec that fails to import/instantiate or doesn't conform is
skipped.

```json
{ "contributors": { "house": "house_style:make" } }
```

```python
from contributors import Contribution

class HouseStyle:
    source = "house"
    def contribute(self, situation):
        return [] if situation.subject != "coding" else [
            Contribution(source=self.source, title="house style",
                         body="prefer small pure functions")]

def make(root):
    return HouseStyle()
```

A plugin owns the `<source>` namespace of `.praxis/config.json` (`config.read`/`config.write`,
values stored raw). `validate_contributor(obj) -> list[str]` structurally checks conformance
(`[]` = conforms); `contributors_for(root)` runs it on every loaded object.

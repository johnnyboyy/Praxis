# Self-hosting the house — a runbook for driving from a fresh session

Goal: use this system to frame, route, and improve *its own* development.

## ✅ SETUP IS DONE — start driving

The repo self-hosts cleanly now (2026-08-06): project state lives in dot-dirs — `.praxis/config.md`
(root marker, engine-plugins → corpora/praxis-plugin/engine/plugins, debug on) and
`.corpora/config.md` (project shape; `domains-dir: corpora/domains` points the pool at the shipped
source pool) — so the `praxis/` and `corpora/` SOURCE trees no longer double as markers, and the
old `.selfhost/` side-slot + pristine-core gotcha below are historical. The task queue is
`.corpora/queue.md`.

To drive from a fresh session in `~/jdev/skills`: enter through the front door — `begin_work`
(praxis-front-door MCP), or the CLI engine room (`praxis/scripts/route.py --ask` for a raw ask,
`frame.py`/`route.py` for a targeted frame); `corpora/scripts/corpus.py --root . queue-status`
shows the backlog.

---

## Step 0 — the one judgment call: the root shape

`root_tree` governs a task by the **nearest ancestor directory carrying `praxis/config.md`**. So the
question is *where that marker goes*, and it decides how the house sees its own work. Two shapes:

- **Single root at the repo top (recommended to start).** One marker at `skills/praxis/config.md`;
  the whole house is one root. Any file — `corpora/…`, `praxis/…`, `plugins/…` — resolves to it, so
  `frame`/`route` work on any change immediately. Simple; nothing forced.
  - **The gotcha to respect:** `skills/praxis/` is *also* the praxis-CORE code dir. Do **not**
    `plugin_import` a plugin's praxis face into it (that would dump imported phases/scripts alongside
    the pristine core and pollute the repo). For composition when framing the house, register only the
    *engine* slot in a **side location** and point `frame --engine-plugins` at it (see Step 2) — the
    front door (root facts, size signals, assumptions) already works with no engine at all.

- **Per-concern roots (a richer, later exercise).** Give `corpora/`, `praxis/`, and each plugin their
  own marker, so a change spanning two concerns surfaces as `decompose` and needs an **interop root** —
  which would dogfood that unbuilt piece for real. Costs: nested `praxis/praxis/config.md` dirs read
  oddly, and *every* cross-concern edit becomes a multi-root handoff (noise for routine work). Do this
  deliberately once the interop root exists, not as the first step.

**Recommendation:** single root now; revisit per-concern roots when building the interop root.

## Step 1 — make the repo a root

```bash
python3 praxis/scripts/praxis_init.py init --root . --name skills-house --debug
# → writes praxis/config.md (the marker). --debug archives closed handoffs instead of deleting them,
#   which you want while dogfooding your own development.
```

Confirm it's discoverable and read the house's own structure as fact:

```bash
python3 praxis/scripts/root_tree.py tree --from .        # should list this root
python3 praxis/scripts/root_tree.py span --files corpora/scripts/corpus.py,praxis/scripts/frame.py
```

## Step 2 — (optional) register the engine so composition works when framing the house

The front door runs without an engine, but to have `frame` compose corpora domains for a house task,
register corpora's engine manifest in a side slot that does NOT touch the pristine core `praxis/`:

```bash
mkdir -p .selfhost/engine/plugins
# copy corpora's engine manifest, freezing its cli.entry to the absolute corpus.py path:
python3 - <<'PY'
import json, pathlib
src = pathlib.Path("corpora/praxis-plugin/engine/plugins/corpora.json")
d = json.loads(src.read_text())
entry = (src.parent / d["cli"]["entry"]).resolve()      # → skills/corpora/scripts/corpus.py
d["cli"]["entry"] = str(entry)
pathlib.Path(".selfhost/engine/plugins/corpora.json").write_text(json.dumps(d, indent=2) + "\n")
print("registered engine at .selfhost/engine/plugins/corpora.json")
PY
```

(Framing the house also wants a `corpora/config.md` project-shape for `select` to read — the house's
own engine bootstrap. `has-ui: no` is enough to start. Producing that is the *engine's* bootstrap, the
symmetric counterpart to `praxis_init`; hand-write it for now or add a `corpus.py init` later.)

## Step 3 — drive a real change through the front door

Pick the next roadmap item (e.g. **framing Stage 2**, the raw-ask entry) and frame it *as a house
task*:

```bash
python3 praxis/scripts/route.py --from . \
  --target praxis/scripts/frame.py --unit-of-work implement-feature \
  --engine-plugins .selfhost/engine/plugins        # omit to see the no-engine degrade
```

Read what it reports: governing root, `size_floor`, `size_signals`, the `assumptions` to confirm, and
the execution-shape signals. That readout *is* the system framing its own improvement — the point of
the whole exercise. From there, act at the size the frame earned.

## What's already prepared

- `praxis_init.py` — writes the root marker (this file's Step 1). Tested.
- `frame.py` / `route.py` — root facts + composition + Stage-1 sizing signals + assumption-relay.
- `plugin_import.py`, `plugin_scaffold.py`, `relocate-domain` — the authoring toolkit, ready to run on
  the house's own plugins/domains once it's framing itself.

## Open, in rough order (from the memory horizon)

~~framing **Stage 2** (raw-ask entry)~~ [done, t-01] → ~~spawn-prompt → praxis (capability sort)~~
[done, t-02: `emit-spawn-parts` hook + praxis `spawn_prompt.py`] → **interop root** + per-concern
roots + bidirectional handoff → **backward spine** (+ framing Stage 3, the persisted frame artifact)
→ finer generic-vs-design split of the `routing` domain.

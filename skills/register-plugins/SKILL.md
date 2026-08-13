---
description: Opt-in, re-runnable multi-select that registers/unregisters praxis plugins (corpora + the judgment plugins) into this root's .praxis/config.json — pick what to enable, toggle anytime.
disable-model-invocation: true
---

Toggle which praxis plugins are active for a root. Opt-in, re-runnable, non-destructive.

## Steps

1. **Root** = this repo's root (where `.praxis/config.json` lives). If it is not a managed root
   yet, run `:init` first.

2. **List** available + current in one call:

   ```
   python3 praxis/scripts/plugin_registry.py --root <ROOT> --list
   ```

   `available` = discovered plugins (`name`, `spec`, `dir`, `description`, `layer`).
   `registered` = the root's current `{name: spec}` map.

3. **Ask** with `AskUserQuestion` (`multiSelect: true`), one option per `available` plugin:
   `label` = `name`, `description` = its one-liner. **Pre-check every plugin already in
   `registered`.** In the `corpora` option's description, note it is the **composer**: the judgment
   plugins (general, coding-stack, uiux, writing) are inert without it.

4. **Set** exactly what the user selected (registers newly-checked, drops unchecked):

   ```
   python3 praxis/scripts/plugin_registry.py --root <ROOT> --set <name1,name2,...>
   ```

   Use `--set ""` to clear all.

5. **Report** the helper's `added` / `removed`, the final active set, and that `plugins_path` was
   written. If corpora was selected, also report `corpora_sources` — the domains dirs written into
   corpora's config scope (corpora discovers from that list, not from praxis). Remind the user this
   is re-runnable.

## Background (only if something is ambiguous)

- **Helper.** `praxis/scripts/plugin_registry.py` — pure functions `discover`, `current`, `apply`.

- **Discovery.** A plugin is found by its module-level `PRAXIS_PLUGIN = True` marker (static, not by
  filename) across four layers, LOW→HIGH precedence, higher layer wins a name collision:
  **bundled** (`praxis/plugins`) → **global** (Claude Code plugins dir, default `~/.claude/plugins`)
  → **project** (`<ROOT>/.praxis/plugins`) → **explicit** (dirs in the root's `plugins_search_paths`).
  The global layer is why a praxis plugin bundled in a globally-installed Claude Code plugin shows up
  in every project with no per-root setup.

- **Plugins root.** Discovery defaults to the bundled `praxis/plugins` (derived from the helper's
  location) and unions the layers above. Pass `--plugins-root` only to override the bundled dir.

- **What `--set` writes.** `contributors` = exactly the selected set; top-level `plugins_path` = the
  union of the selected plugins' dirs, so praxis imports the `module:make` modules with no external
  `PYTHONPATH` (praxis-core reads `plugins_path` onto `sys.path` before loading contributors). Every
  other section of `.praxis/config.json` is left untouched.

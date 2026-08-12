---
description: Opt-in, re-runnable multi-select that registers/unregisters praxis plugins (corpora + the judgment plugins) into this root's .praxis/config.json — pick what to enable, toggle anytime.
disable-model-invocation: true
---

Run this to choose which praxis plugins are active for a root. It is a **toggle**: opt-in,
re-runnable, and non-destructive — nothing is enabled unless the user selects it, re-running shows
the current state, and every other section of `.praxis/config.json` is left untouched.

The helper is `praxis/scripts/plugin_registry.py` (pure functions: `discover`, `current`, `apply`).
Drive it like this:

1. **Resolve roots.** The target praxis root is this repo's root (where `.praxis/config.json` lives;
   run `:init` first if it is not yet a managed root). The plugins root defaults to
   `/Users/johnzdanis/jdev/skills/praxis-plugins` — use that unless the user names another.

2. **Read available + current.** Run the helper to get both at once:

   ```
   python3 praxis/scripts/plugin_registry.py --root <ROOT> --plugins-root <PLUGINS_ROOT> --list
   ```

   `available` is the discovered plugins (`name`, `spec`, `dir`, `description`); `registered` is the
   root's current `{name: spec}` map.

3. **Present an opt-in multi-select.** Ask the user with `AskUserQuestion` (`multiSelect: true`), one
   option per available plugin — `label` = the plugin `name`, `description` = its one-liner.
   **Pre-select the plugins already in `registered`** so the prompt shows current state and the user
   adds/removes in a single pass. Nothing beyond what is already registered is checked by default.
   In the `corpora` option's description, make clear it is the **composer**: the judgment plugins
   (general, coding-stack, uiux, writing, monorepo) are inert without it, so enabling them without
   corpora composes nothing.

4. **Apply the selection.** Register EXACTLY what the user selected (this registers newly-checked
   plugins and drops unchecked ones) by running the helper with the comma-separated names:

   ```
   python3 praxis/scripts/plugin_registry.py --root <ROOT> --plugins-root <PLUGINS_ROOT> --set <name1,name2,...>
   ```

   (Pass `--set ""` to clear all.) The helper writes `contributors` to exactly the selected set and
   sets top-level `plugins_path` to the union of the selected plugins' dirs, so praxis can import the
   `module:make` modules with no external `PYTHONPATH` (praxis-core reads `plugins_path` onto
   `sys.path` before loading contributors).

5. **Report.** Tell the user which plugins were newly **registered** and which were **unregistered**
   (from the helper's `added` / `removed` summary), the final active set, and that `plugins_path` was
   written so the modules import. Remind them this skill is re-runnable to change the selection later.

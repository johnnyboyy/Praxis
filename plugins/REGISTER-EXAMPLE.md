# Registering corpora + the judgment plugins

A consuming praxis root enables all three by listing them under the
`contributors` namespace in its `.praxis/config.json`. Each value is a
`module:make` factory string; praxis calls `factory(root)` to instantiate the
contributor (`corpora.plugin:make` for the composer, `*_plugin:make` for each
bare judgment plugin).

```json
{
  "contributors": {
    "corpora":  "corpora.plugin:make",
    "uiux":     "uiux_plugin:make",
    "general":  "general_plugin:make"
  },
  "corpora": {
    "project_shape": { "language": "python", "framework": "react", "has-ui": true }
  }
}
```

- `corpora` is the only composer — it discovers `uiux` and `general` via
  `contributors_for(root)`, reads their `domains_dir`, stamps `owner`, and
  injects. The two judgment plugins ship domains and compose nothing.
- The `corpora.project_shape` section is optional but gates domains that declare
  `applies-when` (e.g. the uiux domains require `has-ui: true`); omit a key and
  those domains are pruned. An absent section == `{}` == only always-on domains.

**Imports:** you don't set `PYTHONPATH` by hand. The plugins are bundled under
`praxis/plugins/<name>/`, and `:register-plugins` writes a top-level `plugins_path`
(the union of the selected plugins' dirs) that praxis-core prepends to `sys.path`
before loading contributors — so the `module:make` specs above import as written.
To register plugins that live outside the bundled tree, list their dirs under the
top-level `plugins_search_paths` key (the highest-precedence discovery layer).

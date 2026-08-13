# Registering corpora + a process plugin

A consuming praxis root enables plugins by listing them under the
`contributors` namespace in its `.praxis/config.json`. Each value is a
`module:make` factory string; praxis calls `factory(root)` to instantiate the
contributor (`corpora.plugin:make` for the composer, `*_plugin:make` for each
bundled process plugin).

```json
{
  "contributors": {
    "corpora": "corpora.plugin:make",
    "uiux":    "uiux_plugin:make"
  },
  "corpora": {
    "project_shape": { "language": "python", "framework": "react", "has-ui": true },
    "sources": [
      { "owner": "uiux", "dir": "/path/to/domains/uiux" }
    ]
  }
}
```

- Every plugin bundled with praxis (`plugins/<name>/`) is process-only now —
  none exposes a `domains_dir`. Judgment lives in the peer **domains bucket**
  (`~/jdev/skills/domains`); pull it into a root via `corpora:import` (writes
  ratified domains into `.praxis/domains`) or by listing a collection dir
  directly under `corpora.sources`, as above. `corpora` discovers from that
  `sources` list plus the project-local pool — it no longer asks praxis for
  plugins carrying `domains_dir`.
- The `corpora.project_shape` section is optional but gates domains that declare
  `applies-when` (e.g. the uiux domains require `has-ui: true`); omit a key and
  those domains are pruned. An absent section == `{}` == only always-on domains.

**Imports:** you don't set `PYTHONPATH` by hand. The plugins are bundled under
`praxis/plugins/<name>/`, and `:register-plugins` writes a top-level `plugins_path`
(the union of the selected plugins' dirs) that praxis-core prepends to `sys.path`
before loading contributors — so the `module:make` specs above import as written.
To register plugins that live outside the bundled tree, list their dirs under the
top-level `plugins_search_paths` key (the highest-precedence discovery layer).

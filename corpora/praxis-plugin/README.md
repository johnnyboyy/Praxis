# corpora/praxis-plugin — corpora's contribution to praxis

Everything corpora needs to register as an engine into praxis's plugin slots. Praxis-core names
nothing here; this contribution depends on praxis-core (the correct direction), never the reverse.

```
engine/plugins/corpora.json   capability→verb map + `cli` (where corpus.py is)
handoff/plugins/corpora.json  the handoff fields corpora expects at its ratify gate
scripts/                      corpora-specific orchestration over corpora's own CLI verbs:
  _engine_link.py               links these scripts to praxis-core's generic resolver + loads the manifest
  domain_import.py              browse → file → ratify import sequence
  ratify_writeback.py           principle write-back (scripted vs. manual map)
  domain_migrate.py             the gated domain-repo migration sequence
phases/                       corpora's phases (retrospective, domain-import, debugging, testing, …)
tests/                        the moved sequence-script tests, the corpora-mimicking stub, and
                              test_integration.py (proves corpora-registered-into-praxis composes)
```

**How the binding works.** `engine/plugins/corpora.json` carries a `cli` block whose `entry`
(`../../../scripts/corpus.py`) is resolved relative to the manifest file — so when this contribution
is imported into a project's praxis engine slot, the corpus.py location travels with it. Praxis reads
that to learn where to invoke; the scripts here reach praxis-core's generic `engine.resolve` via
`_engine_link` and name only capabilities, never verbs directly.

Run: `python3 -m unittest discover -s tests`

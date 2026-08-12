# writing — a process-only praxis plugin

Ships the writing **PROCESS** face and nothing else: two phases and a workflow
for authoring real prose products (fiction, nonfiction, copy, legal,
documentation), plus per-stance drafting/revision guidance from `contribute`.

## Process-only — no judgment

This plugin has **no `domains_dir`**, on purpose. It carries no hand-authored
judgment, so corpora finds nothing to inject from it. A baked-in "good fiction"
or "good legal prose" rule is just the baseline craft an agent already applies,
and corpora only earns its keep with judgment that *beats* baseline. Genre/style
judgment is therefore **born later at the ratify gate**, homed in the project
doing the work — not pre-authored here.

The genre axis (`fiction` / `nonfiction` / `copy` / `legal` / `documentation`)
is not a field on `Situation`; it rides in each `Contribution`'s `body` and
`meta`, read as a hint from `situation.label`.

## What it registers

- **Phases** — `writing-draft` (divergent, spawn) and `writing-revision`
  (convergent, spawn). No deterministic `run` — there is no mechanical writing
  craft to compute.
- **Workflow** — `writing`: `writing-draft -> writing-revision -> close`
  (revision loops back to draft on `fail`). `close` is the seed phase from
  `workflow.CLOSE`, merged in by the registry.
- **contribute(situation)** — keyed on `subject == "prose"`; returns draft
  guidance for the divergent stance (or `phase_name == "writing-draft"`) and
  revision guidance for the convergent stance (or `writing-revision`); returns
  `[]` for any non-prose subject.

## Registration

In the consuming praxis root's `.praxis/config.json`, under `contributors`:

```json
{
  "contributors": {
    "writing": "writing_plugin:make"
  }
}
```

## Tests

```
cd praxis-plugins/writing && python3 -m pytest -q
```

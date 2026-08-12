# monorepo — coordination judgment plugin

A praxis judgment plugin for the **coordination root** — a root whose children
include other praxis roots. It carries the `monorepo-coordination` domain for the
corpora composer and injects a little process framing for units running at that
border.

## Faces

- **Judgment** (`domains/monorepo-coordination.md`): the coordination judgment,
  seeded from the motors-and-controls migration. Corpora discovers it via
  `domains_dir` and stamps it `owner = monorepo`.
- **Process** (`contribute`): for a cross-root / `subject == "process"` unit (or the
  `coordination` phase), injects orchestration framing — frame at the border,
  decompose one unit per child root, hand each through the child's own front door,
  carry cross-root dependencies through interop. It injects *judgment only*; it does
  **not** resolve or traverse the root tree — that is core `root_tree`'s job
  (`find_roots` / `nearest_root` / `span` / `interop_root`).

## Registration

In the consuming root's `.praxis/config.json`:

```json
{
  "contributors": {
    "corpora": "corpora.injector:make",
    "monorepo": "monorepo_plugin:make"
  }
}
```

## Test

```
cd monorepo && python3 -m pytest -q
```

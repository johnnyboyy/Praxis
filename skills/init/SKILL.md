---
description: Mark this repo as a praxis root — write an empty .praxis/config.json so the gate and drive tools start managing it.
disable-model-invocation: true
---

Call the praxis `init` tool. It ensures an empty `.praxis/config.json` at the git root (or the
current folder outside a repo), which marks the repo a managed praxis root. In a git repo it also
ensures `.gitignore` ignores the rebuild-triple scratch dir (`.rebuild/`), so extract→synthesize
working files are never committed.

`.praxis/config.json` is a namespaced config store: plugins persist their own settings under their
own section, and any praxis-core needs live in the unnamed top-level scope. A fresh root starts
clean (`{}`) — nothing is detected or written beyond the marker itself.

Report that the repo is now a managed praxis root — the gate and drive tools (conduct / plan /
register_plan) are active for it.

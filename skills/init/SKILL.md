---
description: Mark this repo as a praxis root — detect the project shape and write .praxis/config.md so the gate and drive tools start managing it.
disable-model-invocation: true
---

Detect the project shape by inspecting the repo, then call the praxis `init` tool with what you found.

Detection:
- `language` / `framework` — `package.json` → node (read its deps for the framework: react, next, vue, …); `pyproject.toml` / `requirements.txt` / `setup.py` → python (read for the framework: django, flask, fastapi, …). Default `none` when unknown.
- `has_ui` — `yes` if a UI framework is present (react, vue, svelte, next, …), else `no`.
- `styling` — the CSS/styling system in use (tailwind, css-modules, styled-components, …), else `none`.
- `package_manager` — from the lockfile: `package-lock.json` → npm, `yarn.lock` → yarn, `pnpm-lock.yaml` → pnpm, `poetry.lock` → poetry, `uv.lock` → uv, else `none`.

Then call the praxis `init` tool with the detected `language`, `framework`, `has_ui`, `styling`, `package_manager`.

Report that the repo is now a managed praxis root — the gate and drive tools (conduct / plan / register_plan) are active for it.

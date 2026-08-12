#!/usr/bin/env python3
"""plugin_registry — pure, testable helpers behind the `:register-plugins` onboarding flow.

Registration is opt-in and re-runnable: a consuming praxis root enables plugins by listing them
under the `contributors` namespace of its `.praxis/config.json` (each value a `module:make` factory
spec praxis calls as `factory(root)`), and the modules are made importable by the top-level
`plugins_path` list (see `contributors._prepend_plugins_path`). This module is the mechanism the
skill drives:

  discover(plugins_root) -> the plugins available to register (name, source, spec, dir, description)
  current(root)          -> the root's currently-registered {name: spec} contributors map
  apply(root, names, discovered)
                         -> register EXACTLY the selected set (drop the rest) and write the
                            union of their dirs to top-level `plugins_path`; return an add/remove
                            summary. Non-destructive to every other config section.

Dependency-free on purpose (json + pathlib + ast, all stdlib): the file format mirrors
`config.py` so a root written here reads back identically through praxis-core.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

CONFIG_REL = (".praxis", "config.json")
CONTRIBUTORS_SCOPE = "contributors"
PLUGINS_PATH_KEY = "plugins_path"
DEFAULT_PLUGINS_ROOT = "/Users/johnzdanis/jdev/skills/praxis-plugins"


# ── discovery ────────────────────────────────────────────────────────────────

def discover(plugins_root: str | Path) -> list[dict]:
    """Scan `plugins_root` for registerable plugins.

    Returns one entry per plugin, sorted by name:
      {name, source, spec ("module:make"), dir, description}

    Includes the corpora composer (`corpora.injector:make`, dir = the corpora package parent so
    `corpora.injector` imports) and every `*_plugin.py` bare/full judgment plugin. `description`
    is the first sentence of the plugin module's docstring, falling back to the sibling README's
    H1, then to a generic stub. Never imports the plugins — everything is read statically.
    """
    root = Path(plugins_root)
    entries: list[dict] = []
    seen_dirs: set[str] = set()

    corpora_pkg = root / "corpora" / "corpora" / "injector.py"
    if corpora_pkg.exists():
        corpora_dir = str((root / "corpora").resolve())
        entries.append({
            "name": "corpora",
            "source": "corpora",
            "spec": "corpora.injector:make",
            "dir": corpora_dir,
            "description": (
                _first_sentence(_module_docstring(corpora_pkg))
                or _readme_h1(root / "corpora")
                or "The composer — discovers and injects the judgment plugins."
            ),
        })
        seen_dirs.add(corpora_dir)

    for plugin_file in sorted(root.glob("*/*_plugin.py")):
        module_name = plugin_file.stem  # e.g. general_plugin
        source = _plugin_source(plugin_file) or module_name.removesuffix("_plugin")
        plugin_dir = str(plugin_file.parent.resolve())
        description = (
            _first_sentence(_module_docstring(plugin_file))
            or _readme_h1(plugin_file.parent)
            or f"The {source} plugin."
        )
        entries.append({
            "name": source,
            "source": source,
            "spec": f"{module_name}:make",
            "dir": plugin_dir,
            "description": description,
        })
        seen_dirs.add(plugin_dir)

    entries.sort(key=lambda e: e["name"])
    return entries


def _module_docstring(py_file: Path) -> str:
    try:
        tree = ast.parse(py_file.read_text())
    except (OSError, SyntaxError):
        return ""
    return ast.get_docstring(tree) or ""


def _plugin_source(py_file: Path) -> str | None:
    """Read the `source = "..."` class attribute statically (no import)."""
    try:
        tree = ast.parse(py_file.read_text())
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                    if "source" in targets and isinstance(stmt.value, ast.Constant):
                        val = stmt.value.value
                        if isinstance(val, str) and val.strip():
                            return val
    return None


def _first_sentence(text: str) -> str:
    collapsed = " ".join((text or "").split())
    if not collapsed:
        return ""
    dot = collapsed.find(". ")
    if dot != -1:
        return collapsed[: dot + 1]
    return collapsed if collapsed.endswith(".") else collapsed


def _readme_h1(plugin_dir: Path) -> str:
    readme = plugin_dir / "README.md"
    try:
        for line in readme.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return ""


# ── config read/write (mirrors config.py's `.praxis/config.json` format) ─────

def _config_path(root: str | Path) -> Path:
    return Path(root).joinpath(*CONFIG_REL)


def _load(root: str | Path) -> dict:
    try:
        data = json.loads(_config_path(root).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _dump(root: str | Path, scopes: dict) -> None:
    p = _config_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(scopes, indent=2, sort_keys=True) + "\n")


# ── current / apply ──────────────────────────────────────────────────────────

def current(root: str | Path) -> dict:
    """The root's currently-registered `{name: spec}` contributors map."""
    scope = _load(root).get(CONTRIBUTORS_SCOPE, {})
    return dict(scope) if isinstance(scope, dict) else {}


def apply(root: str | Path, selected_names, discovered: list[dict]) -> dict:
    """Register EXACTLY `selected_names` (drop everything else) and write `plugins_path`.

    Writes `contributors` = `{name: spec}` for the selected, known plugins, and sets top-level
    `plugins_path` to the sorted union of the selected plugins' dirs so the modules import
    (Part 1). Every other config section is preserved untouched. Returns a summary:
      {added, removed, contributors, plugins_path}
    """
    by_name = {e["name"]: e for e in discovered}
    selected = [n for n in dict.fromkeys(selected_names) if n in by_name]

    new_contributors = {name: by_name[name]["spec"] for name in selected}
    plugins_path = sorted({by_name[name]["dir"] for name in selected})

    before = current(root)
    added = sorted(set(new_contributors) - set(before))
    removed = sorted(set(before) - set(new_contributors))

    scopes = _load(root)
    scopes[CONTRIBUTORS_SCOPE] = new_contributors
    unnamed = dict(scopes.get("", {})) if isinstance(scopes.get(""), dict) else {}
    if plugins_path:
        unnamed[PLUGINS_PATH_KEY] = plugins_path
    else:
        unnamed.pop(PLUGINS_PATH_KEY, None)
    scopes[""] = unnamed
    _dump(root, scopes)

    return {
        "added": added,
        "removed": removed,
        "contributors": new_contributors,
        "plugins_path": plugins_path,
    }


# ── CLI (scripting / testing convenience; the interactive UX lives in the skill) ─

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Register/unregister praxis plugins for a root.")
    ap.add_argument("--root", required=True, help="the target praxis root")
    ap.add_argument("--plugins-root", default=DEFAULT_PLUGINS_ROOT,
                    help="dir holding the available plugins")
    ap.add_argument("--list", action="store_true",
                    help="print discovered plugins + which are registered, as JSON")
    ap.add_argument("--set", metavar="a,b,c",
                    help="register EXACTLY these plugin names (comma-separated); '' clears all")
    args = ap.parse_args(argv)

    discovered = discover(args.plugins_root)

    if args.set is not None:
        names = [n.strip() for n in args.set.split(",") if n.strip()]
        summary = apply(args.root, names, discovered)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    registered = current(args.root)
    out = {
        "available": discovered,
        "registered": registered,
    }
    if args.list:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    for e in discovered:
        mark = "x" if e["name"] in registered else " "
        print(f"[{mark}] {e['name']:14} {e['spec']:26} {e['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

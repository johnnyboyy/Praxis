#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

CONFIG_REL = (".praxis", "config.json")
CONTRIBUTORS_SCOPE = "contributors"
PLUGINS_PATH_KEY = "plugins_path"

PLUGINS_SEARCH_PATHS_KEY = "plugins_search_paths"

MARKER = "PRAXIS_PLUGIN"

DEFAULT_PLUGINS_ROOT = str(Path(__file__).resolve().parent.parent / "plugins")

DEFAULT_GLOBAL_ROOT = "~/.claude"

INSTALLED_PLUGINS_REL = ("plugins", "installed_plugins.json")

GLOBAL_SKILLS_REL = ("skills",)

PROJECT_PLUGINS_REL = (".praxis", "plugins")

_UNSET = object()

def discover(
    root: str | Path | None = None,
    *,
    plugins_root: str | Path | None = None,
    global_root: str | Path | None = _UNSET,
) -> list[dict]:
    layers: list[tuple[str, list[dict]]] = []

    bundled_dir = Path(plugins_root) if plugins_root is not None else Path(DEFAULT_PLUGINS_ROOT)
    layers.append(("bundled", _scan_tree(bundled_dir)))

    if global_root is _UNSET:
        global_root = DEFAULT_GLOBAL_ROOT
    if global_root is not None:
        layers.append(("global", _scan_global(Path(global_root).expanduser())))

    if root is not None:
        layers.append(("project", _scan_tree(Path(root).joinpath(*PROJECT_PLUGINS_REL))))
        explicit: list[dict] = []
        for d in _config_search_paths(root):
            explicit.extend(_scan_tree(Path(d)))
        layers.append(("explicit", explicit))

    merged: dict[str, dict] = {}
    for layer_name, entries in layers:
        for entry in entries:
            tagged = dict(entry, origin=layer_name, layer=layer_name)
            merged[tagged["name"]] = tagged

    return sorted(merged.values(), key=lambda e: e["name"])

def _scan_tree(search_dir: Path) -> list[dict]:
    try:
        if not search_dir.is_dir():
            return []
        candidates = sorted(search_dir.rglob("*.py"))
    except OSError:
        return []

    entries: list[dict] = []
    for py_file in candidates:
        if "__pycache__" in py_file.parts:
            continue
        if not _has_marker(py_file):
            continue
        entry = _entry_for(py_file)
        if entry is not None:
            entries.append(entry)
    return entries

def _scan_global(global_root: Path) -> list[dict]:
    entries: list[dict] = []
    for path in _global_install_paths(global_root):
        entries.extend(_scan_tree(path))
    return entries

def _global_install_paths(global_root: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        if p not in seen:
            seen.add(p)
            paths.append(p)

    manifest = global_root.joinpath(*INSTALLED_PLUGINS_REL)
    try:
        data = json.loads(manifest.read_text())
    except (OSError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict) and isinstance(data.get("plugins"), dict):
        for installs in data["plugins"].values():
            if not isinstance(installs, list):
                continue
            for install in installs:
                if isinstance(install, dict):
                    ip = install.get("installPath")
                    if isinstance(ip, str) and ip:
                        _add(Path(ip))

    skills = global_root.joinpath(*GLOBAL_SKILLS_REL)
    try:
        children = sorted(skills.iterdir())
    except OSError:
        children = []
    for child in children:
        try:
            _add(child.resolve())
        except OSError:
            continue

    return paths

def _entry_for(py_file: Path) -> dict | None:
    module, plugin_dir = _module_and_dir(py_file)
    source = _plugin_source(py_file) or _fallback_source(module)
    if not source:
        return None
    description = (
        _first_sentence(_module_docstring(py_file))
        or _readme_h1(py_file.parent)
        or _readme_h1(Path(plugin_dir))
        or f"The {source} plugin."
    )
    return {
        "name": source,
        "source": source,
        "spec": f"{module}:make",
        "dir": plugin_dir,
        "description": description,
    }

def _module_and_dir(py_file: Path) -> tuple[str, str]:
    parts = [py_file.stem]
    d = py_file.parent
    while (d / "__init__.py").exists():
        parts.insert(0, d.name)
        d = d.parent
    return ".".join(parts), str(d.resolve())

def _fallback_source(module: str) -> str:
    head = module.split(".")[0]
    return head.removesuffix("_plugin") if head else ""

def _config_search_paths(root: str | Path) -> list[str]:
    paths = _load(root).get("", {})
    vals = paths.get(PLUGINS_SEARCH_PATHS_KEY) if isinstance(paths, dict) else None
    if not isinstance(vals, list):
        return []
    return [v for v in vals if isinstance(v, str) and v]

def _module_docstring(py_file: Path) -> str:
    try:
        tree = ast.parse(py_file.read_text())
    except (OSError, SyntaxError):
        return ""
    return ast.get_docstring(tree) or ""

def _has_marker(py_file: Path) -> bool:
    try:
        tree = ast.parse(py_file.read_text())
    except (OSError, SyntaxError):
        return False

    marked = False
    has_make = False
    has_module_source = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if MARKER in names:
                marked = True
            if "source" in names:
                has_module_source = True
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == MARKER:
                marked = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "make":
            has_make = True

    if not marked:
        return False
    return has_make or has_module_source or _plugin_source(py_file) is not None

def _plugin_source(py_file: Path) -> str | None:
    try:
        tree = ast.parse(py_file.read_text())
    except (OSError, SyntaxError):
        return None

    for scope in (tree, *[n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]):
        for stmt in getattr(scope, "body", []):
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

def current(root: str | Path) -> dict:
    scope = _load(root).get(CONTRIBUTORS_SCOPE, {})
    return dict(scope) if isinstance(scope, dict) else {}

def apply(root: str | Path, selected_names, discovered: list[dict]) -> dict:
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

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Register/unregister praxis plugins for a root.")
    ap.add_argument("--root", required=True, help="the target praxis root")
    ap.add_argument("--plugins-root", default=None,
                    help="override the bundled plugins dir (default: praxis' own)")
    ap.add_argument("--global-root", default=None,
                    help="override the Claude Code config dir (default ~/.claude) enumerated as "
                         "the global layer via installed_plugins.json + skills/ symlinks")
    ap.add_argument("--list", action="store_true",
                    help="print discovered plugins + which are registered, as JSON")
    ap.add_argument("--set", metavar="a,b,c",
                    help="register EXACTLY these plugin names (comma-separated); '' clears all")
    args = ap.parse_args(argv)

    discover_kw: dict = {}
    if args.plugins_root is not None:
        discover_kw["plugins_root"] = args.plugins_root
    if args.global_root is not None:
        discover_kw["global_root"] = args.global_root
    discovered = discover(args.root, **discover_kw)

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

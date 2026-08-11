#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

CONFIG_NAME = "config.md"


def path(root: str | Path) -> Path:
    return Path(root) / ".praxis" / CONFIG_NAME


def read(root: str | Path, namespace: str | None = None) -> dict:
    try:
        text = path(root).read_text()
    except OSError:
        return {}
    return _parse(text).get(_scope(namespace), {})


def write(root: str | Path, namespace: str | None, updates: dict) -> None:
    p = path(root)
    try:
        text = p.read_text()
    except OSError:
        text = ""
    scopes = _parse(text)
    scope = _scope(namespace)
    merged = dict(scopes.get(scope, {}))
    merged.update({str(k): str(v) for k, v in updates.items()})
    scopes[scope] = merged
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_render(scopes))


def _scope(namespace: str | None) -> str:
    return "" if namespace is None else namespace


def _parse(text: str) -> "dict[str, dict]":
    scopes: dict[str, dict] = {"": {}}
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            current = stripped[3:].strip()
            scopes.setdefault(current, {})
            continue
        if stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key:
            scopes[current][key] = value.strip()
    return scopes


def _render(scopes: "dict[str, dict]") -> str:
    lines: list[str] = []
    for key, value in scopes.get("", {}).items():
        lines.append(f"{key}: {value}")
    for name, section in scopes.items():
        if name == "" or not section:
            continue
        if lines:
            lines.append("")
        lines.append(f"## {name}")
        for key, value in section.items():
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"

#!/usr/bin/env python3
"""engine — praxis's generic judgment-engine binding: a plugin loader + capability resolver.

Part of praxis-core. Praxis never imports an engine, never learns its schema, and never hardcodes
where an engine lives or what its verbs are called. Instead an engine *registers* by dropping a
capabilities manifest into praxis's engine plugin slot (`engine/plugins/`). The manifest is data:

  - it maps each praxis *capability name* (e.g. `compose`) to that engine's own CLI verb + the argv
    shape praxis must build, and
  - it declares WHERE the engine's CLI is (`cli`: a command + an entry path resolved relative to the
    manifest file), so praxis learns the invocation location from the registered manifest rather than
    knowing it a priori.

A sequence script or phase names a capability; `resolve` looks it up in the registered manifest,
builds the argv, and invokes the engine's CLI. Praxis ships with an EMPTY slot — no engine — and
degrades (reports "no engine registered") rather than crashing. Move an engine in (import its
manifest into the slot) and the same generic code drives it. A second engine is a second manifest;
nothing in praxis enumerates or names any particular engine.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Praxis's engine plugin slot. Ships EMPTY: an engine registers by importing its manifest here.
DEFAULT_ENGINE_PLUGINS = Path(__file__).resolve().parents[1] / "engine" / "plugins"

_ENGINE_PLUGINS_RE = re.compile(r"^\s*engine-plugins:\s*(.+?)\s*$", re.MULTILINE)


def slot_for_root(root: Path) -> Path:
    """The engine plugin slot a governing root exposes — so a task need not pass `--engine-plugins` by
    hand once its root is known.

    Resolution, in order:
      1. the root's config marker (`praxis/config.md`) may declare `engine-plugins: <path>` — the
         explicit pointer a project uses when its engine contribution sits outside the convention slot
         (resolved relative to the root when not absolute);
      2. otherwise the convention `<root>/praxis/engine/plugins`, where `plugin_import` lands an
         imported engine manifest.

    praxis names no engine either way: it reads a path from its own marker or falls back to its own
    slot, and whatever manifest is there (if any) is discovered generically.
    """
    import root_tree as rt
    root = Path(root)
    pdir = rt.praxis_dir(root)
    cfg = pdir / "config.md"
    if cfg.is_file():
        m = _ENGINE_PLUGINS_RE.search(cfg.read_text(encoding="utf-8", errors="replace"))
        if m:
            p = Path(m.group(1).strip())
            return p if p.is_absolute() else (root / p)
    return pdir / "engine" / "plugins"


class EngineResult:
    """The outcome of one engine call. `ok` is the guard a sequence script branches on."""

    def __init__(self, returncode: int, stdout: str, stderr: str, ran: bool):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.ran = ran  # False when no engine is registered / the CLI was absent (praxis degrades)

    @property
    def ok(self) -> bool:
        return self.ran and self.returncode == 0

    def note(self) -> str:
        if not self.ran:
            return "engine unavailable"
        if self.returncode == 0:
            return "ok"
        return f"engine returned {self.returncode}: {self.stderr.strip()[:200]}"


class CapabilityError(KeyError):
    """A capability was not declared by the manifest, or a required param was not supplied.

    Raised before the engine is ever touched — an unresolvable capability is praxis's own bug (a
    script asking for something the manifest does not declare), not an engine failure to degrade past.
    """


def _resolve_cli(cli: dict | None, manifest_dir: Path) -> list[str] | None:
    """Turn a manifest's `cli` declaration into a runnable command prefix, or None if undeclared.

    `cli` is `{"command": <str|list>, "entry": <path>}`. The entry path is resolved relative to the
    manifest file's own directory when not absolute, so a registered manifest points at its engine's
    CLI wherever that engine's contribution sits — praxis never encodes the location itself.
    """
    if not cli:
        return None
    command = cli.get("command", "python3")
    cmd = list(command) if isinstance(command, (list, tuple)) else [command]
    entry = Path(cli["entry"])
    if not entry.is_absolute():
        entry = (Path(manifest_dir) / entry).resolve()
    return cmd + [str(entry)]


def load_manifest(manifest_path: Path) -> dict:
    """Load one engine capabilities manifest, indexed by capability name and with its CLI resolved.

    Returns {"plugin", "capabilities": {name: entry}, "cli": [cmd..., entry] | None}. Every verb and
    the invocation location come from here — never from a hardcoded string in praxis.
    """
    p = Path(manifest_path)
    data = json.loads(p.read_text())
    caps = {c["capability"]: c for c in data.get("capabilities", [])}
    return {"plugin": data.get("plugin", "?"), "capabilities": caps,
            "cli": _resolve_cli(data.get("cli"), p.parent)}


def discover_manifest(plugins_dir: Path = DEFAULT_ENGINE_PLUGINS) -> Path | None:
    """The engine manifest registered in the slot, or None if the slot is empty (no engine)."""
    d = Path(plugins_dir)
    if not d.is_dir():
        return None
    found = sorted(d.glob("*.json"))
    return found[0] if found else None


def load_registered(plugins_dir: Path = DEFAULT_ENGINE_PLUGINS) -> dict | None:
    """Load whichever engine has registered in the slot, or None. This is how praxis-core gets 'the
    engine': it discovers it, it does not name it. Empty slot → None → callers degrade."""
    mp = discover_manifest(plugins_dir)
    return load_manifest(mp) if mp else None


def build_argv(manifest: dict, capability: str, params: dict) -> list[str]:
    """Compose the engine argv for a capability from declared params. Pure data → argv; no I/O.

    Global args precede the verb; positionals emit their value alone; booleans emit just the flag when
    truthy; everything else is a `--flag value` pair. Order follows the manifest's declared order. A
    missing required param raises CapabilityError.
    """
    cap = manifest["capabilities"].get(capability)
    if cap is None:
        raise CapabilityError(
            f"capability '{capability}' not declared by engine plugin '{manifest.get('plugin','?')}'")
    globals_: list[str] = []
    rest: list[str] = []
    for a in cap.get("args", []):
        name = a["param"]
        present = name in params and params[name] not in (None, "", False)
        if a.get("required") and not present:
            raise CapabilityError(f"capability '{capability}' requires param '{name}'")
        if not present:
            continue
        val = params[name]
        if a.get("boolean"):
            piece = [a["flag"]]
        elif a.get("positional"):
            piece = [str(val)]
        else:
            piece = [a["flag"], str(val)]
        (globals_ if a.get("global") else rest).extend(piece)
    return globals_ + [cap["verb"]] + rest


def invoke(cli: list[str] | None, args: list[str], timeout: int = 60) -> EngineResult:
    """Run one engine command. `cli` is the resolved command prefix (from the manifest, or a test
    override). Never raises for an absent or failing engine — returns a result the caller guards on,
    so praxis reports facts (which step failed) instead of crashing on the engine."""
    if not cli:
        return EngineResult(127, "", "no engine registered", ran=False)
    entry = Path(cli[-1])
    if not entry.is_file():
        return EngineResult(127, "", f"engine CLI not found at {entry}", ran=False)
    try:
        p = subprocess.run([*cli, *args], capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as e:
        return EngineResult(1, "", f"engine invocation failed: {e}", ran=True)
    return EngineResult(p.returncode, p.stdout, p.stderr, ran=True)


def resolve(manifest: dict | None, capability: str, params: dict, *, cli: list[str] | None = None,
            timeout: int = 60) -> EngineResult:
    """Resolve a capability NAME to its argv via the registered manifest, then run it.

    This is how every caller reaches the engine: by capability, never by verb string. `manifest` is a
    loaded manifest (or None → no engine registered → degrade). `cli` overrides the manifest's own CLI
    (tests point it at a stub). Param errors raise (praxis's own bug); engine unavailability/failure
    degrades through `invoke`'s EngineResult.
    """
    if manifest is None:
        return EngineResult(127, "", "no engine registered", ran=False)
    argv = build_argv(manifest, capability, params)
    return invoke(cli if cli is not None else manifest.get("cli"), argv, timeout=timeout)


def call_json(manifest: dict | None, capability: str, params: dict, *, key: str | None = None,
              timeout: int = 30, none_note: str = "engine unavailable") -> tuple[object | None, str]:
    """Resolve a capability, parse its stdout as JSON, and return (payload, note) — the
    resolve→check-ok→json.loads→extract shape every capability caller repeats. `none_note` is the
    degrade message for an unregistered engine (`manifest is None`), which every call site states for
    itself since the wording differs by what the capability was for. `key`, when given, extracts and
    returns just that field of the payload (raising the same not-understood note if it's missing);
    omit it to get the whole payload back. Returns (None, note) on any of the three failure classes —
    not ran, nonzero exit, or unparseable/incomplete output — never raises for an engine failure."""
    if manifest is None:
        return None, none_note
    res = resolve(manifest, capability, params, timeout=timeout)
    if not res.ok:
        return None, res.note()
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        return None, f"engine output not understood: {e}"
    if key is not None:
        try:
            payload = payload[key]
        except KeyError as e:
            return None, f"engine output not understood: {e}"
    return payload, "ok"


def echo(result: EngineResult, label: str) -> None:
    """Relay an engine step's output to the caller, verbatim, tagged with which step it was."""
    tag = "ok" if result.ok else ("skipped (engine unavailable)" if not result.ran else "FAILED")
    sys.stdout.write(f"[{label}] {tag}\n")
    if result.stdout.strip():
        sys.stdout.write(result.stdout if result.stdout.endswith("\n") else result.stdout + "\n")
    if not result.ok and result.stderr.strip():
        sys.stdout.write(result.stderr.rstrip() + "\n")

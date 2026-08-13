#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

import rebuild_spec

def _copy_into(src: Path, dest_root: Path) -> Path | None:
    raw = Path(src)
    resolved = raw if raw.is_absolute() else (Path.cwd() / raw)
    if not resolved.is_file():
        return None
    target = dest_root / (raw if not raw.is_absolute() else Path(raw.name))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, target)
    return target

def seed_synth_worktree(spec, dest, extra=None) -> Path:
    spec = rebuild_spec.validate_spec(spec)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    seeded: list[str] = []
    for spec_test in spec["tests"]["spec"]:
        t = _copy_into(spec_test, dest)
        if t is not None:
            seeded.append(str(t))
    for item in (extra or []):
        t = _copy_into(item, dest)
        if t is not None:
            seeded.append(str(t))

    praxis = dest / ".praxis"
    praxis.mkdir(exist_ok=True)
    marker = praxis / "config.json"
    if not marker.exists():
        marker.write_text('{"": {"name": "synth-worktree"}}\n')

    return dest

def _pythonpath_entries(env: dict) -> list[Path]:
    raw = env.get("PYTHONPATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p.strip()]

def _within(path: Path, root: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(root))
        return True
    except ValueError:
        return False

def _resolve_import(name: str, entries: list[Path]) -> Path | None:
    for e in entries:
        pkg = e / name / "__init__.py"
        mod = e / (name + ".py")
        if pkg.is_file():
            return pkg
        if mod.is_file():
            return mod
    return None

def dep_hygiene_ok(worktree, original_root, env=None, package=None):
    env = dict(os.environ if env is None else env)
    worktree = Path(worktree)
    original_root = Path(original_root)
    entries = _pythonpath_entries(env)
    problems: list[str] = []

    if not any(_within(worktree, e) or _within(e, worktree) for e in entries):
        problems.append(
            f"worktree {worktree} is not on PYTHONPATH — the synth's code would "
            f"not be importable; tests bind to whatever else is on the path")

    for e in entries:
        if _within(e, original_root) or _within(original_root, e):
            problems.append(
                f"original root {original_root} is reachable via PYTHONPATH entry "
                f"{e} — the synth's tests could import the ORIGINAL implementation")

    if package:
        where = _resolve_import(package, entries)
        if where is not None and not _within(where, worktree):
            problems.append(
                f"package {package!r} resolves to {where}, OUTSIDE the worktree "
                f"(an installed/original copy) — coverage-diff would bind to it")

    return (not problems), problems

_READ_SHELL_VERBS = {"cat", "sed", "head", "tail", "less", "more", "grep", "find"}

def _bash_read_paths(command: str) -> list[str]:
    paths: list[str] = []

    normalized = command
    for sep in ("&&", "||", ";", "|"):
        normalized = normalized.replace(sep, "\n")
    for segment in normalized.split("\n"):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        if not tokens:
            continue
        verb = os.path.basename(tokens[0])
        if verb not in _READ_SHELL_VERBS:
            continue
        for tok in tokens[1:]:

            if tok.startswith("-"):
                continue
            if tok in {"(", ")", "{", "}"}:
                continue

            paths.append(tok)
    return paths

def read_tool_log(log_path, agent_id=None) -> list[str]:
    path = Path(log_path)
    try:
        raw = path.read_text()
    except (OSError, ValueError):
        return []

    reads: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        line_agent, tool_name, payload = parts[0], parts[1], parts[2]
        if agent_id is not None and line_agent != agent_id:
            continue
        if tool_name == "Bash":
            reads.extend(_bash_read_paths(payload))
        elif tool_name in ("Read", "Grep", "Glob"):
            if payload:
                reads.append(payload)
    return reads

def default_tripwire_log(root) -> Path:
    return Path(root) / ".praxis" / "tripwire.log"

def synth_tool_log(root, agent_id) -> list[str]:
    return read_tool_log(default_tripwire_log(root), agent_id)

def scan_tripwire(tool_log, worktree) -> list:
    worktree_real = Path(os.path.realpath(Path(worktree)))
    violations: list = []
    for entry in (tool_log or []):
        raw = Path(entry)
        base = raw if raw.is_absolute() else (worktree_real / raw)
        resolved = Path(os.path.realpath(base))
        if not _within(resolved, worktree_real):
            violations.append({
                "read": str(entry),
                "resolved": str(resolved),
                "reason": "read resolves outside the synth worktree "
                          "(reached for the original — a copy attempt)",
            })
    return violations

def _tool_log_from(receipt, composed) -> list:
    composed = composed or {}
    for key in ("synth_tool_log", "tool_log"):
        if key in composed and composed[key] is not None:
            return list(composed[key])
    ev = (receipt.evidence if receipt else None) or {}
    for key in ("synth_tool_log", "tool_log"):
        if ev.get(key) is not None:
            return list(ev[key])
    return []

def tripwire_verifier():
    from run import CallableVerifier, Verdict

    def _handler(unit, receipt, composed):
        ev = (receipt.evidence if receipt else None) or {}
        synth = ev.get("produces")
        if not synth:
            return Verdict(verified=False,
                           defects=["no synth worktree path for the copy tripwire"],
                           evidence={"check": "tripwire", "reason": "no-worktree"})
        violations = scan_tripwire(_tool_log_from(receipt, composed), synth)
        if violations:
            reads = [v["read"] for v in violations]
            return Verdict(verified=False,
                           defects=[f"copy tripwire: reads outside worktree {reads}"],
                           evidence={"check": "tripwire", "violations": violations})
        return Verdict(verified=True, evidence={"check": "tripwire", "violations": []})

    return CallableVerifier(_handler)

def synthesize_exit_gate(coverage_diff):
    from run import CallableVerifier

    wire = tripwire_verifier()

    def _handler(unit, receipt, composed):
        v = wire.verify(unit, receipt, composed)
        if not v.verified:
            return v
        return coverage_diff.verify(unit, receipt, composed)

    return CallableVerifier(_handler)

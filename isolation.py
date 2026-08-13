#!/usr/bin/env python3
"""isolation — rebuild isolation + copy-detection for the rebuild seam.

The rebuild triple's one invariant is that `synthesize` REBUILDS the interface
rather than COPYING the original. Behavioral gates cannot tell a rebuild from a
faithful copy — both go green. Only isolation can, and isolation here is
**best-effort**, not a capability boundary:

  * `seed_synth_worktree` builds a scratch tree containing ONLY the spec's
    sanctioned artifacts (spec tests + explicitly-passed shared config), never
    the original source — attractor-reduction, so a synth agent that stays in
    its lane never encounters the original.
  * `dep_hygiene_ok` checks that the synth's tests bind to the SYNTH's code with
    the original OFF the import path (the silent killer: a test importing the
    original's installed package passes coverage-diff against the wrong code).
  * `scan_tripwire` is a DETECTOR, not a preventer: given the synth agent's
    filesystem-read log, it flags every path that resolves OUTSIDE the worktree.
    A non-empty result means the agent reached for the original — a copy attempt.

HONEST FRAMING (do not overstate): this is "isolated + copy-detected," NOT
"provably cannot see the original." A `claude -p` subagent can Read any absolute
path; cwd isolation is attractor-reduction + a tripwire, not a sandbox. Real OS
capability sandboxing (container / mount namespace / read-only bind mount) is on
the BACKLOG, not this lap.
"""
from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

import rebuild_spec


# --- 1. seed the synth worktree, spec-only -----------------------------------

def _copy_into(src: Path, dest_root: Path) -> Path | None:
    """Copy a single sanctioned file into `dest_root`.

    A relative source keeps its relative shape under the worktree; an absolute
    source lands at its basename. Missing/non-file sources are skipped (returns
    None) — seeding only ever copies files that actually exist and are named.
    """
    raw = Path(src)
    resolved = raw if raw.is_absolute() else (Path.cwd() / raw)
    if not resolved.is_file():
        return None
    target = dest_root / (raw if not raw.is_absolute() else Path(raw.name))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, target)
    return target


def seed_synth_worktree(spec, dest, extra=None) -> Path:
    """Build a fresh scratch tree at `dest` holding ONLY the spec's artifacts.

    Contents: the spec's `tests.spec` files (the tests synthesize is allowed to
    see) plus any explicitly-passed `extra` shared build/test config. The
    original source is NEVER copied, and `tests.held_out` is withheld (it proves
    generalization at the preservation gate, so synth must not see it). We do NOT
    use `git worktree add` — that brings the whole tree, including the original.

    The seeded tree gets its OWN `.praxis/config.json` marker so the edit-lease
    gate (`root_tree.resolve_root`) resolves it as its own root, NOT the parent
    unit's root+surface lease (the worktree↔lease collision fix from the barrier).

    Fail-closed on a malformed spec. Returns the worktree Path.
    """
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

    # Its own praxis marker → its own root for the edit-lease gate.
    praxis = dest / ".praxis"
    praxis.mkdir(exist_ok=True)
    marker = praxis / "config.json"
    if not marker.exists():
        marker.write_text('{"": {"name": "synth-worktree"}}\n')

    return dest


# --- 2. dependency hygiene (the silent killer) -----------------------------

def _pythonpath_entries(env: dict) -> list[Path]:
    raw = env.get("PYTHONPATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p.strip()]


def _within(path: Path, root: Path) -> bool:
    """True iff `path` (realpath) is `root` or lives under it."""
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(root))
        return True
    except ValueError:
        return False


def _resolve_import(name: str, entries: list[Path]) -> Path | None:
    """Where `import <name>` would resolve given ordered path `entries`.

    First entry that carries `<name>/__init__.py` or `<name>.py` wins — mirrors
    Python's own first-match-on-sys.path resolution. None = not importable here.
    """
    for e in entries:
        pkg = e / name / "__init__.py"
        mod = e / (name + ".py")
        if pkg.is_file():
            return pkg
        if mod.is_file():
            return mod
    return None


def dep_hygiene_ok(worktree, original_root, env=None, package=None):
    """Verify the synth's tests would bind to the SYNTH's code, original OFF path.

    Inspects the run env (defaults to `os.environ`) that would execute the
    worktree's tests and returns `(ok, problems)`:
      * the worktree MUST be on PYTHONPATH (else the synth's code isn't importable
        and coverage-diff binds to whatever else is on the path);
      * NO PYTHONPATH entry may be, contain, or live under `original_root` (a
        leak: tests would import the original impl and pass against the wrong code);
      * if `package` is named, `import <package>` must resolve INSIDE the worktree,
        not from an installed/original copy elsewhere on the path.
    `problems` names each leak; `ok` is `not problems`.
    """
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


# --- 3a. read the PreToolUse hook log into a tripwire tool_log ---------------

# Shell verbs whose FILE arguments are reads we care about. `tripwire_log.sh`
# logs the raw Bash command; we recover the file paths it touched, best-effort.
_READ_SHELL_VERBS = {"cat", "sed", "head", "tail", "less", "more", "grep", "find"}


def _bash_read_paths(command: str) -> list[str]:
    """Best-effort: extract file arguments from a read-shaped shell command.

    Recognizes `cat`/`sed`/`head`/`tail`/`less`/`more`/`grep`/`find <path>`.
    Splits on `;`, `&&`, `||`, and `|` so each segment is judged on its own verb,
    then takes non-flag, non-option tokens as candidate paths. Deliberately
    conservative — an unparseable command yields nothing rather than guessing."""
    paths: list[str] = []
    # Normalize the pipeline/sequence separators to a single delimiter.
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
            # Skip flags/options and shell operators.
            if tok.startswith("-"):
                continue
            if tok in {"(", ")", "{", "}"}:
                continue
            # `find <path> -name ...` — stop at the first predicate flag; the
            # loop above already skips flags, so plain path tokens survive.
            paths.append(tok)
    return paths


def read_tool_log(log_path, agent_id=None) -> list[str]:
    """Parse the `tripwire_log.sh` hook log into the read-path list the tripwire
    consumes.

    The log is tab-separated `<agent_id>\\t<tool_name>\\t<path-or-command>` lines.
    When `agent_id` is given, only that subagent's lines are considered (so a
    single dispatched synth subagent's reads are isolated from the parent and
    from other subagents). Returns file paths, in log order:
      * `Read`/`Grep`/`Glob` → the recorded path directly;
      * `Bash` → the file arguments extracted from read-shaped commands
        (`cat`/`sed`/`head`/`tail`/`less`/`grep`/`find`), best-effort.

    Fail-soft: a missing/unreadable log or malformed line yields no paths for
    that line rather than raising. The result feeds `scan_tripwire(log, worktree)`
    unchanged."""
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
    """The default hook log location the orchestrator reads after dispatch:
    `<root>/.praxis/tripwire.log` — the same path `tripwire_log.sh` writes when
    `$PRAXIS_TRIPWIRE_LOG` is unset."""
    return Path(root) / ".praxis" / "tripwire.log"


def synth_tool_log(root, agent_id) -> list[str]:
    """End-to-end convenience: after the orchestrator dispatches the synthesize
    subagent and gets its `agent_id`, this replays that subagent's reads from the
    default tripwire log so they can be passed as `record_phase(..., tool_log=...)`.
    Equivalent to `read_tool_log(default_tripwire_log(root), agent_id)`."""
    return read_tool_log(default_tripwire_log(root), agent_id)


# --- 3. copy-detection tripwire (a detector, not a preventer) ---------------

def scan_tripwire(tool_log, worktree) -> list:
    """Flag every path in the synth's read-log that resolves OUTSIDE `worktree`.

    `tool_log` is the list of filesystem paths the synth agent READ (its tool-call
    log). Robust to relative, absolute, and symlink paths: each is resolved to a
    realpath (relative paths against the worktree, symlinks followed to their
    target) before the containment check, so a symlink inside the worktree that
    points at the original still trips. A non-empty result = the agent reached for
    the original = a copy attempt; the caller fails the unit.

    Returns a list of `{"read", "resolved", "reason"}` violations, in log order.
    """
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


# --- 4. the tripwire gate + composed synthesize-exit gate -------------------

def _tool_log_from(receipt, composed) -> list:
    """Locate the synth agent's read-log. Input SOURCE for now (B wires it to a
    real dispatched subagent's log): accept it from composed, then the receipt's
    evidence, then None. Absent ⇒ empty log ⇒ no violations (preservation-gate path unaffected)."""
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
    """A synthesize-exit verifier that FAILS the unit on any out-of-worktree read.

    Reads the synth worktree from `receipt.evidence['produces']` (same source
    coverage-diff uses) and the read-log via `_tool_log_from`. Fail-closed: a
    tripped wire is a copy and blocks the unit even when the behavioral gates
    would go green. Absent a log, there is nothing to detect and it passes."""
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
    """Compose the synthesize-exit gate: the copy TRIPWIRE first (a tripped wire
    is a copy — fail regardless of behavior), then the `coverage_diff`
    preservation gate. Keeps the walk's single `coverage-diff` gate at that edge
    (routing unchanged) while making a silent copy un-passable."""
    from run import CallableVerifier

    wire = tripwire_verifier()

    def _handler(unit, receipt, composed):
        v = wire.verify(unit, receipt, composed)
        if not v.verified:
            return v
        return coverage_diff.verify(unit, receipt, composed)

    return CallableVerifier(_handler)

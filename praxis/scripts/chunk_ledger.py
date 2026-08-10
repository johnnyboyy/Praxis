#!/usr/bin/env python3
# praxis-core script — unit-of-work accounting (the chunk ledger). Praxis reads and writes the ledger
# at praxis/chunks/<workstream>.md ITSELF (native filesystem work); the ONLY engine invocation left
# here is `compose` (the domains-composed for a unit-of-work), resolved against whatever engine has
# registered in the plugin slot.
"""chunk_ledger — the deterministic close sequence for a workstream's chunk ledger, praxis-native.

The ledger is unit-of-work accounting, a praxis fact, so praxis serializes it
(`parse_chunks`/`render_chunks`) rather than delegating the write to any engine. The one thing praxis
still asks the engine for is the *composition* — the `compose` capability returns the domain set for
the unit-of-work, the ground truth `domains-composed` is reconciled against.

What praxis enforces here (deterministic, tested):
  - the handoff file exists before anything is attempted (a praxis precondition — the handoff is a
    praxis primitive, so praxis checks its presence directly);
  - `chunk-done` runs first and writes the ledger natively, reconciling the handoff against the
    composition: (a) the handoff's `workstream:` must match, and (b) its `domains-loaded:` must equal
    the composed domain set, failing with a detailed diff otherwise;
  - the handoff is closed (via `handoff.py close`, praxis-native delete/archive) ONLY if chunk-done
    succeeded — the ordering is a hard gate: never retire the handoff a failed chunk-done still needs.

Commands:
  close   --root R --workstream W --unit-of-work U --stance S --handoff FILE [--next U2]
            native chunk-done then (only on success) native handoff close, in that order.
  preview --root R --workstream W --unit-of-work U   chunk-start: print a composition, write nothing.
  summary --root R --workstream W                    close-workstream: read-only ledger summary.
  next    --root R --workstream W                    session loop: the last chunk's recorded next
                                                     pointer, or a non-zero exit when there is none.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
import handoff as ho  # noqa: E402  reuse the handoff primitive: frontmatter parse + native close


DEFERRED_STANCE_ENUM = {"convergent", "divergent"}
VERIFICATION_ENUM = {"clean", "defects-found", "not-run"}


def today() -> str:
    return datetime.date.today().isoformat()


# ── ledger paths + serialization (praxis-owned state under praxis/chunks/) ──────────────────────

def chunks_dir_for(root: str | Path) -> Path:
    import root_tree as rt
    return rt.praxis_dir(root) / "chunks"


def chunks_path(root: str | Path, workstream: str) -> Path:
    return chunks_dir_for(root) / f"{workstream}.md"


def _parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [x.strip() for x in inner.split(",")] if inner else []
    return [value] if value else []


def parse_chunks(path: str | Path) -> tuple[str, list[dict]]:
    """Deliberately flat parser. Returns (workstream, entries)."""
    workstream = ""
    entries: list[dict] = []
    item = None
    in_chunks = False
    for raw in open(path):
        line = raw.rstrip()
        stripped = line.strip()
        if in_chunks and stripped == "```":
            break
        if not in_chunks and stripped.startswith("workstream:"):
            workstream = stripped.split(":", 1)[1].strip()
            continue
        if stripped in ("chunks:", "chunks: []"):
            in_chunks = True
            continue
        if not in_chunks or not stripped or stripped.startswith(("#", "```")):
            continue
        if re.match(r"^\s*-\s+unit-of-work:\s*", line):
            item = {}
            entries.append(item)
            stripped = re.sub(r"^-\s+", "", stripped)
        if item is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            item[key.strip()] = value.strip()
    for item in entries:
        if "domains-composed" in item:
            item["domains-composed"] = _parse_inline_list(item["domains-composed"])
    return workstream, entries


def render_chunks(workstream: str, entries: list[dict]) -> str:
    lines = ["# Chunks", "", f"workstream: {workstream}", "", "```yaml", "chunks:", ""]
    for e in entries:
        lines.append(f"  - unit-of-work: {e['unit-of-work']}")
        lines.append(f"    domains-composed: [{', '.join(e['domains-composed'])}]")
        lines.append(f"    stance: {e['stance']}")
        lines.append(f"    handoff: {e['handoff']}")
        lines.append(f"    completed: {e['completed']}")
        if e.get("next"):
            lines.append(f"    next: {e['next']}")
        if e.get("tier"):
            lines.append(f"    tier: {e['tier']}")
        if e.get("verification"):
            lines.append(f"    verification: {e['verification']}")
        lines.append("")
    lines.append("```")
    return "\n".join(lines) + "\n"


def handoff_field(path: str | Path, name: str) -> str:
    """Read one frontmatter scalar from a handoff. Reuses the handoff primitive's own frontmatter
    splitter (`handoff.split_frontmatter`)."""
    fm, _ = ho.split_frontmatter(Path(path).read_text())
    m = re.search(rf"^{re.escape(name)}:[ \t]*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip() if m else ""


# ── the one engine touch: compose ─────────────────────────────────────────────────────────────

def compose(manifest: dict | None, root: str, unit_of_work: str) -> tuple[list[str] | None, str]:
    """Invoke the registered engine's `compose` capability for the domain set of a unit-of-work. The
    sole engine call remaining in the chunk ledger. Returns (domains, note); domains is None when no
    engine is registered, it is unavailable, or its output isn't understood (praxis reports, does not
    crash)."""
    return engine.call_json(manifest, "compose",
                            {"root": str(root), "unit_of_work": unit_of_work, "json": True},
                            key="domains", timeout=30)


# ── chunk-done: native append + the two reconciliation checks ───────────────────────────────────

def chunk_done(manifest: dict | None, root: str, workstream: str, unit_of_work: str, stance: str,
               handoff: str, nxt: str | None, tier: str | None = None,
               verification: str | None = None) -> tuple[bool, str]:
    """Append a ledger entry after reconciling the handoff against the composition. Native — praxis
    writes praxis/chunks/<workstream>.md itself. `tier` and `verification` are OPTIONAL telemetry:
    which model tier did the work, and what the conductor's verify pass (session.md loop step 3)
    found. Absent → not written, so older ledgers and tier-less closes keep today's exact shape.
    Returns (ok, message)."""
    # (a) the handoff must belong to this workstream.
    handoff_workstream = handoff_field(handoff, "workstream")
    if handoff_workstream and handoff_workstream != workstream:
        return False, (f"handoff's workstream '{handoff_workstream}' does not match --workstream "
                       f"'{workstream}' — a chunk can only be closed by the handoff it actually produced")

    # domains-composed is ground truth from compose(), never self-reported by the handoff.
    domains_composed, note = compose(manifest, root, unit_of_work)
    if domains_composed is None:
        return False, (f"composition unavailable — cannot record domains-composed for unit-of-work "
                       f"'{unit_of_work}' ({note}); nothing written")

    # (b) reconcile the spawn's own report of what it loaded against the composition.
    domains_loaded_raw = handoff_field(handoff, "domains-loaded")
    if domains_loaded_raw:
        domains_loaded = sorted(_parse_inline_list(domains_loaded_raw))
        expected = sorted(domains_composed)
        if domains_loaded != expected:
            only_composed = sorted(set(expected) - set(domains_loaded))
            only_loaded = sorted(set(domains_loaded) - set(expected))
            return False, (
                "handoff's domains-loaded does not match the composed domains-composed for "
                f"unit-of-work '{unit_of_work}' — refusing to close the chunk.\n"
                f"  composition only: {only_composed or '(none)'}\n"
                f"  handoff only: {only_loaded or '(none)'}\n"
                "Either the composing process diverged from the composition (fix it to use the "
                "composed set, per the spawn-brief step), or the spawn didn't load what its "
                "composition specified (fix the spawn). Do not paper over this by editing the ledger."
            )

    path = chunks_path(root, workstream)
    if path.exists():
        _, entries = parse_chunks(path)
    else:
        entries = []
    entries.append({
        "unit-of-work": unit_of_work,
        "domains-composed": domains_composed,
        "stance": stance,
        "handoff": handoff,
        "completed": today(),
        "next": nxt,
        "tier": tier,
        "verification": verification,
    })
    chunks_dir_for(root).mkdir(parents=True, exist_ok=True)
    path.write_text(render_chunks(workstream, entries))
    return True, f"chunk closed: {workstream}/{unit_of_work} -> {path}"


# ── the close sequence: native chunk-done, then native handoff close, in that load-bearing order ──

def close(manifest: dict | None, root: str, workstream: str, unit_of_work: str, stance: str,
          handoff: str, nxt: str | None, tier: str | None = None,
          verification: str | None = None) -> int:
    """Run the close sequence with the load-bearing ordering gate. Returns a process exit code.

    chunk-done writes the ledger and must run BEFORE the handoff is closed (deleted/archived), because
    a closed handoff is gone from disk and chunk-done reconciles against it. Both steps are native
    praxis filesystem work now; only the composition inside chunk-done touches the engine.

    `tier` and `verification` are optional telemetry pass-through, see `chunk_done`.
    """
    if verification is not None and verification not in VERIFICATION_ENUM:
        sys.stdout.write(f"[precondition] FAILED — --verification must be one of "
                         f"{sorted(VERIFICATION_ENUM)}, got: {verification!r}\n")
        return 1

    handoff_path = Path(handoff)
    if not handoff_path.is_file():
        # Praxis precondition, before anything else: the handoff is a praxis primitive, so praxis owns
        # this check in its own voice rather than letting a downstream step discover the absence.
        sys.stdout.write(f"[precondition] FAILED — handoff file does not exist: {handoff}\n")
        sys.stdout.write("  chunk-done reconciles against a handoff that must still be on disk; nothing run.\n")
        return 1

    ok, msg = chunk_done(manifest, root, workstream, unit_of_work, stance, str(handoff_path), nxt,
                         tier, verification)
    sys.stdout.write(f"[chunk-done] {'ok' if ok else 'FAILED'}\n{msg}\n")
    if not ok:
        # The gate: never close the handoff a failed chunk-done still needs.
        sys.stdout.write("[handoff-close] not run — chunk-done did not succeed; handoff left in place "
                         "so the close can be retried in the correct order.\n")
        return 1

    import root_tree as rt
    handoffs_dir = rt.praxis_dir(root) / "handoffs"
    rc, hmsg = ho.close(str(handoff_path), handoffs_dir, ho.project_debug(root))
    sys.stdout.write(f"[handoff-close] {'ok' if rc == 0 else 'FAILED'}\n{hmsg}\n")
    return rc


def cmd_close(args) -> int:
    manifest = engine.load_registered(Path(args.engine_plugins))
    return close(manifest, args.root, args.workstream, args.unit_of_work, args.stance,
                 args.handoff, args.next or None, args.tier or None, args.verification or None)


def cmd_preview(args) -> int:
    """chunk-start: the deterministic composition for a unit-of-work, printed, nothing written."""
    manifest = engine.load_registered(Path(args.engine_plugins))
    domains, note = compose(manifest, args.root, args.unit_of_work)
    if domains is None:
        sys.stdout.write(f"[chunk-start] composition unavailable: {note}\n")
        return 1
    print(f"workstream={args.workstream} unit-of-work={args.unit_of_work} "
          f"domains-composed=[{', '.join(domains)}]")
    return 0


def cmd_summary(args) -> int:
    """close-workstream: read-only ledger summary. Native — praxis reads its own ledger."""
    path = chunks_path(args.root, args.workstream)
    if not path.exists():
        sys.stdout.write(f"no chunk ledger for workstream '{args.workstream}' at {path}\n")
        return 1
    workstream, entries = parse_chunks(path)
    print(f"workstream: {workstream}")
    print(f"chunks: {len(entries)}")
    for e in entries:
        extras = []
        if e.get("tier"):
            extras.append(f"tier: {e['tier']}")
        if e.get("verification"):
            extras.append(f"verification: {e['verification']}")
        suffix = f" [{', '.join(extras)}]" if extras else ""
        print(f"  - {e['unit-of-work']} ({e['stance']}, completed {e['completed']}): "
              f"{', '.join(e['domains-composed'])}{suffix}")
    return 0


def next_unit(root: str, workstream: str) -> tuple[str | None, str]:
    """The session loop's deterministic next-pointer: the `next:` recorded on the ledger's last
    entry. Native ledger read, no engine touch. Returns (unit_of_work | None, note) — None means the
    ledger names no next unit, and the note says why (absent ledger / empty ledger / at rest), so the
    loop conductor falls back to its task source instead of guessing."""
    path = chunks_path(root, workstream)
    if not path.exists():
        return None, (f"no chunk ledger for workstream '{workstream}' at {path} — nothing recorded "
                      "yet; the task source, not the ledger, names the first unit")
    _, entries = parse_chunks(path)
    if not entries:
        return None, "ledger exists but records no chunks — the task source names the first unit"
    last = entries[-1]
    nxt = last.get("next") or ""
    if not nxt:
        return None, (f"last chunk '{last['unit-of-work']}' recorded no next — the workstream is at "
                      "rest; consult the task source or close the workstream")
    return nxt, "ok"


def cmd_next(args) -> int:
    nxt, note = next_unit(args.root, args.workstream)
    if nxt is None:
        sys.stdout.write(f"[next] none — {note}\n")
        return 1
    print(nxt)
    return 0


def verify(manifest: dict | None, root: str) -> tuple[int, list[str]]:
    """verify-chunks: recompute `compose` for every recorded chunk and flag drift from its stored
    `domains-composed` — the composition a later config/domain change may have silently invalidated.
    Native ledger read; the only engine touch is the same `compose` hook chunk-done recorded from.
    Returns (rc, problems); rc is 1 when any chunk drifted, 0 when the ledger reconciles (or is absent)."""
    cdir = chunks_dir_for(root)
    problems: list[str] = []
    if not cdir.is_dir():
        return 0, problems
    for path in sorted(cdir.glob("*.md")):
        workstream, entries = parse_chunks(path)
        for e in entries:
            expected, note = compose(manifest, root, e["unit-of-work"])
            if expected is None:
                problems.append(f"{workstream}/{e['unit-of-work']}: composition unavailable ({note})")
                continue
            recorded = sorted(e.get("domains-composed", []))
            if sorted(expected) != recorded:
                problems.append(f"{workstream}/{e['unit-of-work']}: recorded domains-composed "
                                f"{recorded} no longer matches current compose() {sorted(expected)}")
    return (1 if problems else 0), problems


def cmd_verify(args) -> int:
    manifest = engine.load_registered(Path(args.engine_plugins))
    rc, problems = verify(manifest, args.root)
    if problems:
        print("CHUNK COMPOSITION DRIFT:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("chunk composition reconciled: every recorded domains-composed matches current compose()")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="chunk_ledger", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine-plugins", default=str(engine.DEFAULT_ENGINE_PLUGINS),
                    help="engine plugin slot, used ONLY to resolve `compose` (ships empty; degrades)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("close", help="native chunk-done then native handoff close, in that order")
    c.add_argument("--root", required=True, help="governing root (holds praxis/chunks and praxis/handoffs)")
    c.add_argument("--workstream", required=True)
    c.add_argument("--unit-of-work", required=True)
    c.add_argument("--stance", required=True, choices=sorted(DEFERRED_STANCE_ENUM))
    c.add_argument("--handoff", required=True)
    c.add_argument("--next", default="")
    c.add_argument("--tier", default="", help="OPTIONAL: which model tier did the work "
                   "(free-form, e.g. sonnet, opus, inline)")
    c.add_argument("--verification", default="", choices=[""] + sorted(VERIFICATION_ENUM),
                   help="OPTIONAL: the conductor's verify-pass outcome (session.md loop step 3)")
    c.set_defaults(func=cmd_close)

    p = sub.add_parser("preview", help="chunk-start: print composition, write nothing")
    p.add_argument("--root", required=True)
    p.add_argument("--workstream", required=True)
    p.add_argument("--unit-of-work", required=True)
    p.set_defaults(func=cmd_preview)

    s = sub.add_parser("summary", help="close-workstream: read-only ledger summary")
    s.add_argument("--root", required=True)
    s.add_argument("--workstream", required=True)
    s.set_defaults(func=cmd_summary)

    v = sub.add_parser("verify", help="verify-chunks: recompute compose() for every recorded chunk, flag drift")
    v.add_argument("--root", required=True)
    v.set_defaults(func=cmd_verify)

    n = sub.add_parser("next", help="session loop: print the last chunk's next pointer (exit 1 when none)")
    n.add_argument("--root", required=True)
    n.add_argument("--workstream", required=True)
    n.set_defaults(func=cmd_next)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

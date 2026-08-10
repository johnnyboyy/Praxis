#!/usr/bin/env python3
"""unit_close — the one-shot close ceremony for a unit of work.

Adopted from an agent-loop-optimization review ("code mode": chain deterministic sequential steps
in one invocation instead of N round trips). The conductor's unit close is three always-in-this-
order deterministic steps — today run as three separate calls with error gaps between them:

  1. handoff.py validate <handoff> --plugins-dir <slot>    — schema check
  2. chunk_ledger.py close --root R --workstream W --unit-of-work U --stance S --handoff H [--next N]
                                                             — chunk-done + handoff-close gates
  3. frame.close_frame_marker(root)                         — close the frame marker (the same
                                                               logic close_work runs), delete the
                                                               payload file

Each step gates the next; the ordering is the ledger's own gate (chunk-done must record the chunk
before the handoff it reconciled against is closed), not reimplemented here. On a failure this
stops immediately — later steps are NOT run — and reports which step failed and what remains.

Every step is called as a library function (handoff.py / chunk_ledger.py / frame.py), never
subprocessed: `chunk_ledger.close` was already the clean callable seam for step 2 (it takes the
same params `chunk_ledger.py close` does and returns a process-style exit code), so no refactor of
that module was needed.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
import handoff as ho  # noqa: E402
import chunk_ledger as cl  # noqa: E402
import frame as fr  # noqa: E402


def _validate_handoff(handoff_path: str, plugins_dir: str) -> tuple[bool, str]:
    """Step 1: the schema check `handoff.py validate` runs, called as a library — never a
    subprocess. Returns (ok, message)."""
    path = Path(handoff_path)
    if not path.is_file():
        return False, f"no such file: {handoff_path}"
    schema = ho.compose(ho.load_manifests(ho.DEFAULT_BASE, plugins_dir))
    missing = ho.validate(path.read_text(), schema)
    if missing:
        lines = [f"INVALID handoff: {len(missing)} required field(s)/section(s) missing"]
        lines += [f"  - {m}" for m in missing]
        return False, "\n".join(lines)
    return True, (f"valid handoff (checked base + {len(schema['plugins']) - 1} plugin(s): "
                  f"{', '.join(schema['plugins'])})")


def run(root: str, workstream: str, unit_of_work: str, stance: str, handoff_path: str,
       nxt: str | None, engine_plugins: str | None, plugins_dir: str, tier: str | None = None,
       verification: str | None = None) -> dict:
    """Chain validate -> chunk-close -> marker-close, stopping at the first failure. `tier` and
    `verification` are OPTIONAL telemetry, passed through untouched to the chunk-close step (see
    chunk_ledger.close). Returns a step-by-step report:
    `{ok, failed_at, steps: [{step, ok, message}, ...], marker?}`."""
    steps: list[dict] = []

    ok, msg = _validate_handoff(handoff_path, plugins_dir)
    steps.append({"step": "validate", "ok": ok, "message": msg})
    if not ok:
        return {"ok": False, "failed_at": "validate", "steps": steps}

    slot = Path(engine_plugins) if engine_plugins else engine.DEFAULT_ENGINE_PLUGINS
    manifest = engine.load_registered(slot)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cl.close(manifest, root, workstream, unit_of_work, stance, handoff_path, nxt,
                      tier, verification)
    steps.append({"step": "chunk-close", "ok": rc == 0, "message": buf.getvalue().strip()})
    if rc != 0:
        return {"ok": False, "failed_at": "chunk-close", "steps": steps}

    marker = fr.close_frame_marker(Path(root))
    steps.append({"step": "marker-close", "ok": True, "message": json.dumps(marker)})
    return {"ok": True, "failed_at": None, "steps": steps, "marker": marker}


def print_report(result: dict) -> None:
    for s in result["steps"]:
        print(f"[{s['step']}] {'ok' if s['ok'] else 'FAILED'}")
        if s["message"]:
            print(s["message"])
    if result["ok"]:
        print("\nunit closed: validate -> chunk-close -> marker-close, all steps ok")
    else:
        remaining = {"validate": ["chunk-close", "marker-close"],
                    "chunk-close": ["marker-close"]}.get(result["failed_at"], [])
        print(f"\nunit close STOPPED at [{result['failed_at']}] — not run: "
              f"{', '.join(remaining) if remaining else '(nothing further)'}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="unit_close", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="governing root (holds praxis/chunks and praxis/handoffs)")
    ap.add_argument("--workstream", required=True)
    ap.add_argument("--unit-of-work", required=True)
    ap.add_argument("--stance", required=True, choices=sorted(cl.DEFERRED_STANCE_ENUM))
    ap.add_argument("--handoff", required=True)
    ap.add_argument("--next", default="")
    ap.add_argument("--tier", default="", help="OPTIONAL: which model tier did the work, "
                    "passed through to the chunk-close step")
    ap.add_argument("--verification", default="", choices=[""] + sorted(cl.VERIFICATION_ENUM),
                    help="OPTIONAL: the conductor's verify-pass outcome, passed through to the "
                         "chunk-close step")
    ap.add_argument("--engine-plugins", default=None,
                    help="engine plugin slot for the ledger's compose step (default: praxis's own "
                         "empty slot, engine.DEFAULT_ENGINE_PLUGINS)")
    ap.add_argument("--plugins-dir", default=str(ho.DEFAULT_PLUGINS),
                    help="handoff schema plugins dir, same default as handoff.py's own CLI")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = run(args.root, args.workstream, args.unit_of_work, args.stance, args.handoff,
                args.next or None, args.engine_plugins, args.plugins_dir,
                args.tier or None, args.verification or None)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

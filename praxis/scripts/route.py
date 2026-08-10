#!/usr/bin/env python3
"""route — the deterministic fact-sheet a GO-2 routing judgment consumes. Facts only, no decision.

Part of praxis-core (the routing spine). `frame` already produces the facts *prior* to routing — the
governing root, the span→decompose verdict, and the composition. Routing (the "I am the orchestrator"
decision) needs a little more before a human/engine can pick the unit-of-work, the stance, and the
execution shape (inline / resume / isolate). `route` bundles that: it runs `frame` for the
root+span+composition facts and adds the deterministic *execution-shape signals* on top —

  - **span → isolate**: a task whose files span multiple roots is `decompose` (frame's verdict); it
    is N units of work, one isolated per root, never routed as one. This is a hard fact, not a call.
  - **resume vs new**: if a workstream id is named, a ledger lookup says whether prior chunks for it
    already exist (a *resume* candidate) or not (*new*). The ledger is a praxis-owned file
    (`<root>/praxis/chunks/<workstream>.md`), so this is a native filesystem check — no engine call.
  - **composition availability**: whether the engine actually returned a domain set for the unit.

route is also the CLI raw-ask entry (framing Stage 2): a task can enter with nothing settled but a
sentence (`--ask "<the ask>"`, no targets). The raw-ask → targets/unit-of-work mapping is JUDGMENT;
route is the deterministic frame *around* it — with no targets guessed there is no root to compose
against, so it reports exactly what is still unresolved (which file(s), which unit-of-work) as the
assumptions to settle, rather than requiring them up front or crashing. Pass `--target`/`--files`/
`--unit-of-work` as they are guessed and the readout fills in. (The MCP `begin_work` tool is the
other, richer front door; this CLI path survives so praxis still degrades to deterministic facts with
no engine or tool available.)

Everything here is fact. The *decision* — which unit-of-work, which stance, inline/resume/isolate —
is `phases/routing.md`, the judgment on top. Like `frame`, `route` degrades rather than crashes when
the engine or ledger is absent: it reports what it could not learn (`ledger: unknown`) and still
carries every root fact, because praxis does not depend on the engine to route.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frame as fr  # noqa: E402
import root_tree as rt  # noqa: E402
import chunk_ledger as cl  # noqa: E402  the praxis-owned ledger this reads natively
import frame_store as fs  # noqa: E402  the persisted-frame trace (framing Stage 3)
import units  # noqa: E402  the lease declarations (edit surface + output) per unit of work


def workstream_ledger_state(root_path: str | None, workstream: str | None) -> tuple[str, str]:
    """Native resume-vs-new signal. Returns (state, note) where state is one of:
    'exists' (a ledger file for this workstream is present → resume candidate),
    'absent' (a governing root is known but has no such ledger → new),
    'unknown' (no workstream named, or no single governing root → cannot tell, defaults to new).

    The ledger is a praxis-owned file (`chunk_ledger.chunks_path`), so this is a pure filesystem
    check — no engine call.
    """
    if not workstream:
        return "unknown", "no workstream named — treated as new work"
    if not root_path:
        return "unknown", "no single governing root — cannot locate a ledger"
    if cl.chunks_path(root_path, workstream).is_file():
        return "exists", "a chunk ledger for this workstream exists — resume candidate"
    return "absent", "no ledger for this workstream — new work"


def build_route(base: Path, target: str | None, files: list[str], unit_of_work: str | None,
                workstream: str | None, manifest: dict | None, *, ask: str | None = None) -> dict:
    frame = fr.build_frame(base, target, files, unit_of_work, manifest)

    spans = frame["spans_multiple_roots"]
    # A single governing root owns the ledger; a spanning/no-root task has no one ledger to resume.
    root_path = frame["roots"][0]["path"] if (frame.get("roots") and not spans) else None
    ledger_state, ledger_note = workstream_ledger_state(root_path, workstream)
    resume_candidate = ledger_state == "exists"
    composition_available = frame.get("composition") is not None
    lease = units.lease_for(Path(root_path), unit_of_work) if root_path else None

    # Execution-shape signals are facts; the shape *choice* is the judgment in routing.md.
    signals: list[str] = []
    if spans:
        signals.append("spans multiple roots → isolate: one unit of work per root, never routed as one")
    if resume_candidate:
        signals.append(f"workstream '{workstream}' has a ledger → resume candidate")
    elif workstream and ledger_state == "absent":
        signals.append(f"workstream '{workstream}' named but no ledger → new")
    if not unit_of_work:
        signals.append("unit-of-work not decided — the core routing judgment; composition follows it")
    if unit_of_work and not composition_available and not spans:
        signals.append(f"composition unavailable ({frame.get('composition_note')})")
    if lease and lease.get("edit_surface"):
        signals.append(f"lease: unit '{unit_of_work}' may write only "
                       f"{', '.join(lease['edit_surface'])} (plus praxis bookkeeping)")

    return {
        "base": str(base),
        "ask": ask,
        "targets_known": frame["size_signals"]["target_count"] > 0,
        "unit_of_work": unit_of_work,
        "frame": frame,
        "lease": lease,
        "execution_shape": {
            "verdict": frame["verdict"],
            "spans_multiple_roots": spans,
            "isolate_per_root": spans,
            "workstream": workstream,
            "ledger": ledger_state,
            "ledger_note": ledger_note,
            "resume_candidate": resume_candidate,
            "composition_available": composition_available,
        },
        "signals": signals,
    }


def print_route(r: dict) -> None:
    raw_ask = not r["targets_known"]
    if r.get("ask") is not None or raw_ask:
        # The raw-ask front-door header: printed whenever an ask was given or nothing points at a file
        # yet (the clean-degrade case). A targeted route with no --ask keeps its plain readout below.
        print(f"front door · ask: {r['ask'] or '(none given)'}\n")
    if raw_ask:
        # Nothing points at a file yet — report the unresolved frame rather than a misleading
        # "no root governs this target".
        print("no target(s) resolved from the ask yet — this is a raw ask.")
        print("  resolve it to file(s) and a unit-of-work (judgment) before it can be sized to execute.")
        fr.print_sizing(r["frame"])
        if r["signals"]:
            print("\nsignals (facts for the routing judgment):")
            for s in r["signals"]:
                print(f"  • {s}")
        return
    es = r["execution_shape"]
    print(f"route · unit-of-work: {r['unit_of_work'] or '(undecided)'}\n")
    f = r["frame"]
    if es["spans_multiple_roots"]:
        print(f"shape: ISOLATE (decompose) — {f.get('note','')}")
    else:
        if not f["roots"]:
            print("shape: no root governs this target (see frame)")
        else:
            rr = f["roots"][0]
            comp = f["composition"]
            comp_s = f"{len(comp)} domains" if comp is not None else f"— ({f.get('composition_note')})"
            print(f"root: {rr['name']} [{rr['marker']}]   composition: {comp_s}")
            if comp is not None and f.get("composition_note") not in (None, "ok"):
                print(f"  ⚠ {f['composition_note']}")
    print(f"workstream: {es['workstream'] or '(none)'}   ledger: {es['ledger']}   "
          f"resume-candidate: {es['resume_candidate']}")
    fr.print_sizing(r["frame"])          # the framing front-door readout: size floor + assumptions
    if r["signals"]:
        print("\nsignals (facts for the routing judgment):")
        for s in r["signals"]:
            print(f"  • {s}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="route", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ask", help="the natural-language ask (raw-ask entry; no targets required)")
    ap.add_argument("--target", help="a candidate path the task touches")
    ap.add_argument("--files", default="", help="comma-separated candidate files")
    ap.add_argument("--unit-of-work", default="", help="the task's unit-of-work (decided in routing)")
    ap.add_argument("--workstream", default="", help="an existing workstream id to test for resume")
    ap.add_argument("--from", dest="frm", default=".", help="search base for root discovery (default cwd)")
    ap.add_argument("--engine-plugins", default=None,
                    help="the engine plugin slot to resolve a registered engine from. Omit to "
                         "auto-resolve the task's own governing-root slot (config-declared or the "
                         "<root>/praxis/engine/plugins convention).")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--persist", action="store_true",
                    help="persist this frame to praxis/frames/<workstream>.md (Stage 3 backward "
                         "trace); requires --workstream")
    args = ap.parse_args(argv)

    # No targets is the raw-ask entry (Stage 2): degrade to the unresolved-frame readout rather than
    # erroring — the ask is judgment resolved to targets/unit-of-work, and the frame reports what is
    # still missing.
    base = Path(args.frm).resolve()
    files = rt.split_files(args.files)
    manifest = fr.manifest_for(base, args.target, files, args.engine_plugins)
    route = build_route(base, args.target, files, args.unit_of_work or None,
                        args.workstream or None, manifest, ask=args.ask)
    if args.json:
        print(json.dumps(route, indent=2))
    else:
        print_route(route)
    if args.persist:
        if not args.workstream:
            ap.error("--persist requires --workstream (the frame trace is keyed by workstream)")
        # A spanning task has no single governing root to hold the trace; persist per governing root.
        f = route["frame"]
        root = f["roots"][0]["path"] if (f.get("roots") and not f["spans_multiple_roots"]) else None
        if root is None:
            print("frame not persisted: no single governing root (spanning or unrooted task)")
        else:
            path = fs.append_frame(root, args.workstream, f, route["execution_shape"]["verdict"])
            print(f"frame persisted: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

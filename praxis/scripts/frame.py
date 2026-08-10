#!/usr/bin/env python3
"""frame — the deterministic fact bundle for a task, gathered before any judgment acts.

Part of praxis-core. Given a task's candidate target (a path and/or a set of files) and its
unit-of-work, emit the facts the `framing` phase sizes and routes on:

  - which root governs the task, and whether it spans several roots (→ decompose: one unit of work per
    root, handed to each; a single agent never straddles two roots)
  - the composition (domain set) for the unit-of-work

Determinism + decoupling:
  - Root facts are pure filesystem (via root_tree) — they cannot be wrong.
  - Composition is the ENGINE's job, not praxis's. Praxis *invokes* it and relays the fact; it never
    re-derives a composition and never learns the engine's schema (what a "domain" or "applies-when"
    is). Which engine — if any — is registered comes from the engine plugin slot: `engine_compose`
    resolves the `compose` capability against whatever manifest is registered there. With an EMPTY
    slot praxis has no engine and simply reports the root facts with composition unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import root_tree as rt  # noqa: E402
import engine  # noqa: E402

FRAME_MARKER_NAME = ".last-frame-at"

# The two canonical field lists the schema-of-record block (below) refers to instead of repeating
# them in prose — a field-adder edits the constant, and the parity tests (test_hooks.py /
# test_frame.py) fail loudly if the marker write, the stamp projection, or the jq line drift out of
# sync with it.
#   MARKER_FIELDS            — what begin_work (server.py) writes into the JSON marker's
#                               `marker_data`, beyond the `timestamp` every marker carries.
#   STAMP_PROJECTION_FIELDS  — what the stamp hook's jq line must project onto the session stamp:
#                               the gate-consumed subset of MARKER_FIELDS, plus `root` (which the
#                               marker itself doesn't carry — it's implied by the marker's own
#                               location — but the stamp needs explicitly, since a stamp is read
#                               independent of any particular root's marker file).
MARKER_FIELDS = ("unit_of_work", "workstream", "composition", "size_floor", "execution",
                 "delivery", "payload", "surface", "output")
STAMP_PROJECTION_FIELDS = ("root", "unit_of_work", "workstream", "delivery", "payload",
                           "surface", "output")

# ── Frame-marker schema of record (`<root>/{.praxis,praxis}/.last-frame-at`) ─────────────────────
# The marker is the freshness/lease signal the gate reads before allowing an edit. It is written in
# TWO forms; a field-adder touches this block, `touch_frame_marker` (open side), `close_frame_marker`
# (close side, below — written by close_work and unit_close.py), and the stamp hook's projection.
#
# Forms:
#   • bare float — `str(time.time())`, written by the frame.py CLI (touch_if_framed). No unit-of-work;
#     the gate's backward-compat branch accepts it on freshness alone.
#   • JSON object — always carries `timestamp`. begin_work (server.py) enriches it with
#     MARKER_FIELDS (above); close_work replaces it with `{timestamp, closed: true,
#     prior_unit_of_work}`.
#
# Consumers (all resolve the root then read this file):
#   • ~/.claude/hooks/praxis-frame-gate.sh — PreToolUse edit gate. Reads `closed`, `unit_of_work`,
#     `surface` (lease check), and timestamp/mtime freshness.
#   • ~/.claude/hooks/praxis-frame-stamp.sh — PostToolUse on begin_work/close_work. Projects the
#     JSON marker to the session stamp via jq, to exactly STAMP_PROJECTION_FIELDS (above) — a NEW
#     marker field the gate must see MUST be added to that jq list too, or it never reaches the
#     stamp the gate reads. `test_hook_glob_parity`-style parity tests in test_hooks.py enforce the
#     jq line matches the constant, and test_front_door_server.py enforces the marker's written keys
#     match MARKER_FIELDS, so drift in either direction fails a test instead of silently breaking
#     the gate.
#   • server.py work_status — reads the whole marker, normalizing the bare-float form to
#     `{timestamp}`.
#
# Freshness: the gate's window is 1800s (MAX_AGE_SECONDS); the stamp hook additionally ignores any
# begin_work marker older than 60s (the "this begin_work just wrote it" recency check).
#
# Close means closed: `close_frame_marker` also clears every session's stamp for this root (all of
# `$TMPDIR/praxis-front-door/*/<hash>` and `*/<hash>.read`, via `clear_session_stamps`), not just
# the closing session's — the gate checks the stamp FIRST and never re-reads the marker while a
# fresh stamp allows, so a closed marker with a surviving stamp from a DIFFERENT session left the
# gate open regardless. The stamp hook's own close_work branch (removing just its session's stamp)
# remains as belt-and-suspenders for the common single-session case; `clear_session_stamps` is what
# makes close authoritative across every session.
#
# `build_frame` is facts-only and never writes here — the WRITE side of framing is touch_if_framed
# (CLI) and begin_work's own JSON write, so read paths (route, compose_spawn) never disturb a marker
# another session wrote.


def touch_frame_marker(root: Path, marker_data: dict | None = None) -> None:
    """Record that a real frame (single root, unit-of-work known) was just computed for `root` —
    the freshness signal a PreToolUse hook checks before allowing an Edit/Write, so "frame before
    acting" is enforced mechanically instead of relying on remembering to run this script.

    With `marker_data` (a caller that knows the frame's content, e.g. the front-door MCP server),
    the marker is JSON carrying that content plus a `timestamp`; bare callers keep the plain
    `str(time.time())` format, which marker readers must continue to accept."""
    marker = rt.praxis_dir(root) / FRAME_MARKER_NAME
    marker.parent.mkdir(parents=True, exist_ok=True)
    if marker_data is None:
        marker.write_text(str(time.time()))
    else:
        marker.write_text(json.dumps({"timestamp": time.time(), **marker_data}))


FRAME_PAYLOAD_NAME = ".frame-payload.md"


def stamp_hash_for_root(root: Path) -> str:
    """The session-stamp hash for `root`: sha1 hex of the exact root-path string. Identical to the
    bash hooks' `printf '%s' "$ROOT_PATH" | shasum` (praxis-hooks-lib.sh's `praxis_stamp_path`) and
    to what server.py's `work_status` derives — one derivation, three consumers (this function, the
    bash transcription documented there, and work_status below, which calls this instead of
    re-deriving it). All three key off the same root-path *string* with no normalization (no
    trailing-slash stripping), so a caller passing an inconsistently-slashed root will disagree with
    itself across consumers — not this function's problem to solve, since every caller resolves the
    root the same way (`root_tree`) before it ever reaches a hash."""
    return hashlib.sha1(str(root).encode()).hexdigest()


def clear_session_stamps(root: Path) -> int:
    """Delete every session's stamp — and its `.read` companion — for `root`, across ALL sessions:
    `$TMPDIR/praxis-front-door/*/<hash>` and `*/<hash>.read`. The close-side fix for the gap where
    closing a unit left OTHER sessions' stamps (and even the closing session's, on the CLI close
    path, which never ran the stamp hook at all) still satisfying the gate's stamp check, which is
    consulted before the marker and short-circuits past a `closed: true` marker entirely. Honors
    `TMPDIR` with the same `/tmp` fallback the stamp hook and work_status use. Fail-soft: an OSError
    unlinking one stamp (permissions, a race with another process) is skipped, not raised, so it
    can't abort clearing the rest. Returns the count actually removed."""
    stamp_hash = stamp_hash_for_root(root)
    base = Path(os.environ.get("TMPDIR", "/tmp")) / "praxis-front-door"
    if not base.is_dir():
        return 0
    removed = 0
    for pattern in (f"*/{stamp_hash}", f"*/{stamp_hash}.read"):
        for stamp in base.glob(pattern):
            try:
                stamp.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def close_frame_marker(root: Path) -> dict:
    """The close-side counterpart of `touch_frame_marker`: end this root's frame. Overwrites the
    marker with `{timestamp, closed: true, prior_unit_of_work}` — tolerating a bare-float prior
    marker (the plain frame.py CLI path, which carries no unit-of-work) — and deletes the payload
    file so a stale read can't satisfy the next unit's Read-stamp gate. Also clears every session's
    stamp for this root (`clear_session_stamps`) so the gate's stamp check — which runs BEFORE it
    ever looks at the marker — can't keep an edit open on a unit that just closed. Shared by
    close_work (the front-door MCP server) and unit_close.py's CLI-side close ceremony, so both get
    identical close-side marker AND stamp behavior. Always reports `closed: True`: closing a root
    with no marker on disk yet is a no-op success, not an error."""
    marker = rt.praxis_dir(root) / FRAME_MARKER_NAME
    prior = None
    if marker.is_file():
        try:
            parsed = json.loads(marker.read_text())
        except (json.JSONDecodeError, OSError):
            parsed = None
        # A bare-timestamp marker (the plain frame.py CLI path) parses as a float — valid, but
        # carries no unit-of-work.
        prior = parsed if isinstance(parsed, dict) else None
        marker.write_text(json.dumps({"timestamp": time.time(), "closed": True,
                                      "prior_unit_of_work": (prior or {}).get("unit_of_work")}))
    (rt.praxis_dir(root) / FRAME_PAYLOAD_NAME).unlink(missing_ok=True)
    stamps_cleared = clear_session_stamps(root)
    return {"closed": True, "prior_unit_of_work": (prior or {}).get("unit_of_work"),
            "stamps_cleared": stamps_cleared}


def touch_if_framed(frame: dict) -> None:
    """The write side of framing: stamp the bare freshness marker when a real single-root frame
    with a decided unit-of-work was produced. Kept out of `build_frame` (facts only) so read-path
    callers never touch the marker; the CLI framing paths (frame.main, frame_store.cmd_write) call
    this explicitly."""
    if frame["roots"] and not frame["spans_multiple_roots"] and frame["unit_of_work"]:
        touch_frame_marker(Path(frame["roots"][0]["path"]))


def engine_compose(root: Path, unit_of_work: str, manifest: dict | None) -> tuple[list[str] | None, str]:
    """Invoke the registered engine's `compose` capability: the domain set for a unit-of-work.

    `compose` is just a declared capability — its argv is built from whatever engine registered in the
    slot (`engine.call_json`), so frame never names a verb or knows an engine's flags.

    Returns (domains, note). domains is None when no engine is registered, it is unavailable, or it
    errored — praxis still reports the root facts, since it does not depend on the engine.
    """
    payload, note = engine.call_json(
        manifest, "compose", {"root": str(root), "unit_of_work": unit_of_work, "json": True},
        timeout=30, none_note="no engine registered — composition unavailable")
    if payload is None:
        return None, note
    try:
        domains = payload["domains"]
    except KeyError as e:
        return None, f"engine output not understood: {e}"
    warnings = payload.get("warnings") or []
    return domains, "; ".join(warnings) if warnings else "ok"


def manifest_for(base: Path, target: str | None, files: list[str],
                 override: str | None) -> dict | None:
    """The registered engine manifest for a task: `override` (an explicit `--engine-plugins` slot)
    when given, else the task's own governing-root slot (`auto_engine_slot`). None when no slot
    resolves or nothing is registered there — every CLI entry point resolves its engine this way."""
    slot = Path(override) if override is not None else auto_engine_slot(base, target, files)
    return engine.load_registered(slot) if slot else None


def _size_signals(targets: list, governing: dict, unrouted: list, unit_of_work: str | None,
                  composition: list | None) -> dict:
    """The deterministic inputs the framing phase SIZES on — facts that bound how big a task is, never
    the size decision itself (trivial/bounded/vague stays the phase's judgment)."""
    return {
        "target_count": len(targets),
        "roots_spanned": len(governing),
        "unit_of_work_known": bool(unit_of_work),
        "composition_size": (len(composition) if composition is not None else None),
        "unrouted_count": len(unrouted),
    }


def _size_floor(spans: bool, governing: dict, unrouted: list, unit_of_work: str | None) -> str:
    """The DETERMINISTIC part of the size verdict — as far as facts alone can settle it:
      - `decompose`      — spans multiple roots (hard fact; never one task).
      - `underspecified` — missing an input the trivial/execute path requires: no unit-of-work decided,
                           targets that match no root, or no governing root at all. The phase must
                           resolve these (infer the uow, pick the root, disambiguate) before it can
                           size to 'execute directly'.
      - `by-judgment`    — every deterministic input is present (one root, uow known, targets routed);
                           whether it's trivial/bounded/vague is the phase's proportional judgment.
    """
    if spans:
        return "decompose"
    if not governing or unrouted or not unit_of_work:
        return "underspecified"
    return "by-judgment"


def _assumptions(frame: dict, targets: list, unit_of_work: str | None) -> list:
    """The confirmable statements the frame is acting on, for relay BEFORE acting — deterministic
    restatements of the facts (which root, which uow, what's in scope), one per line the operator can
    redirect. This is the assumption-relay floor `framing.md` requires, as data rather than prose."""
    a: list[str] = []
    if frame["spans_multiple_roots"]:
        names = ", ".join(r["name"] for r in frame["roots"])
        a.append(f"spans {len(frame['roots'])} roots ({names}) → decomposing into {len(frame['roots'])} "
                 f"units, one per root; no single agent straddles them")
    elif frame["roots"]:
        r = frame["roots"][0]
        a.append(f"governing root: {r['name']} ({r['path']})")
    else:
        a.append("no root governs the target(s) — acting outside any governed root")
    if targets:
        a.append(f"in scope: {', '.join(str(t) for t in targets)} — say so if a different file or set "
                 f"was meant")
    if unit_of_work:
        a.append(f"unit-of-work: {unit_of_work}")
    else:
        a.append("unit-of-work: undecided — will be inferred from the ask before sizing to execute")
    if frame.get("unrouted_targets"):
        a.append(f"outside any root: {', '.join(frame['unrouted_targets'])}")
    return a


def resolve_targets(base: Path, target: str | None, files: list[str]) -> list[Path]:
    """The candidate paths a task touches, made absolute against `base`. Shared by frame-building and
    engine-slot auto-resolution so both see exactly the same target set."""
    targets: list[Path] = []
    if target:
        p = Path(target)
        targets.append(p if p.is_absolute() else base / p)
    for f in files:
        p = Path(f)
        targets.append(p if p.is_absolute() else base / p)
    return targets


def auto_engine_slot(base: Path, target: str | None, files: list[str]) -> Path | None:
    """The engine slot to use when `--engine-plugins` wasn't passed: the task's own governing root's
    slot (`engine.slot_for_root`). Resolves the target(s) to their governing root; returns None when
    they span roots or match none — there is no single project slot to auto-resolve, so the caller
    degrades to no engine (exactly as a spanning task composes nothing)."""
    roots = rt.find_roots(base, rt.DEFAULT_MARKERS)
    governing = {rt.nearest_root(t, roots) for t in resolve_targets(base, target, files)}
    governing.discard(None)
    if len(governing) != 1:
        return None
    return engine.slot_for_root(next(iter(governing)))


def build_frame(base: Path, target: str | None, files: list[str], unit_of_work: str | None,
                manifest: dict | None) -> dict:
    markers = rt.DEFAULT_MARKERS
    roots = rt.find_roots(base, markers)

    # Resolve the target(s) to their governing root(s).
    targets: list[Path] = resolve_targets(base, target, files)

    governing: dict[str, dict] = {}
    unrouted: list[str] = []
    for t in targets:
        r = rt.nearest_root(t, roots)
        if r is None:
            unrouted.append(str(t))
        else:
            governing.setdefault(str(r), {
                "name": rt.root_name(r, markers), "marker": rt.which_marker(r, markers),
                "path": str(r), "targets": [],
            })["targets"].append(str(t))

    spans = len(governing) > 1
    frame: dict = {
        "base": str(base),
        "unit_of_work": unit_of_work,
        "roots": list(governing.values()),
        "spans_multiple_roots": spans,
        "unrouted_targets": unrouted,
    }

    if spans:
        info = rt.interop_root(targets, roots)
        frame["verdict"] = "decompose"
        frame["composition"] = None
        if info["entry"] is not None:
            entry = info["entry"]
            frame["interop_root"] = {"name": rt.root_name(entry, markers), "path": str(entry)}
            frame["define_interop_at"] = None
            frame["note"] = (f"spans {len(governing)} roots: enter at interop root "
                             f"'{rt.root_name(entry, markers)}', which defines each in-scope piece and "
                             f"passes it off to the child root for execution in its own context.")
        else:
            frame["interop_root"] = None
            frame["define_interop_at"] = info["define_at"]
            frame["note"] = (f"spans {len(governing)} roots with NO common-ancestor root to enter at — "
                             f"define an interop root at {info['define_at']} before this can proceed.")
        frame["size_signals"] = _size_signals(targets, governing, unrouted, unit_of_work, None)
        frame["size_floor"] = _size_floor(True, governing, unrouted, unit_of_work)
        frame["assumptions"] = _assumptions(frame, targets, unit_of_work)
        return frame

    frame["verdict"] = "single-root" if governing else "no-root"
    # Composition is a fact only once the unit-of-work is decided (a routing judgment upstream).
    if governing and unit_of_work:
        root = Path(next(iter(governing)))
        domains, note = engine_compose(root, unit_of_work, manifest)
        frame["composition"] = domains
        frame["composition_note"] = note
    else:
        frame["composition"] = None
        frame["composition_note"] = "unit-of-work not given — decide it (routing judgment) then re-run"
    frame["size_signals"] = _size_signals(targets, governing, unrouted, unit_of_work, frame["composition"])
    frame["size_floor"] = _size_floor(False, governing, unrouted, unit_of_work)
    frame["assumptions"] = _assumptions(frame, targets, unit_of_work)
    return frame


def print_sizing(f: dict) -> None:
    print(f"\nsize floor: {f['size_floor']} (deterministic; trivial/bounded/vague is the phase's call)")
    s = f["size_signals"]
    comp = "n/a" if s["composition_size"] is None else s["composition_size"]
    print(f"  signals: targets={s['target_count']} roots={s['roots_spanned']} "
          f"uow-known={s['unit_of_work_known']} composition={comp} unrouted={s['unrouted_count']}")
    print("assumptions (relay before acting; redirect any before it's realized):")
    for a in f["assumptions"]:
        print(f"  • {a}")


def print_frame(f: dict) -> None:
    print(f"frame · unit-of-work: {f['unit_of_work'] or '(undecided)'}\n")
    if f["spans_multiple_roots"]:
        print(f"⚠ {f['note']}\n")
        if f.get("interop_root"):
            print(f"enter at: {f['interop_root']['name']}  {f['interop_root']['path']}")
        elif f.get("define_interop_at"):
            print(f"define an interop root at: {f['define_interop_at']}")
        print("pieces:")
        for r in f["roots"]:
            print(f"  • {r['name']} [{r['marker']}]")
            for t in r["targets"]:
                print(f"      {t}")
        print_sizing(f)
        return
    if not f["roots"]:
        print("no root governs this target.")
        if f["unrouted_targets"]:
            for t in f["unrouted_targets"]:
                print(f"  {t}")
        print_sizing(f)
        return
    r = f["roots"][0]
    print(f"root: {r['name']} [{r['marker']}]  {r['path']}")
    comp = f["composition"]
    if comp is None:
        print(f"composition: — ({f['composition_note']})")
    else:
        print(f"composition ({len(comp)} domains): {', '.join(comp)}")
        if f["composition_note"] != "ok":
            print(f"  ⚠ {f['composition_note']}")
    print_sizing(f)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="frame", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", help="a candidate path the task touches")
    ap.add_argument("--files", default="", help="comma-separated candidate files")
    ap.add_argument("--unit-of-work", default="", help="the task's unit-of-work (decided upstream)")
    ap.add_argument("--from", dest="frm", default=".", help="search base for root discovery (default cwd)")
    ap.add_argument("--engine-plugins", default=None,
                    help="the engine plugin slot to resolve a registered engine from. Omit to "
                         "auto-resolve the task's own governing-root slot (config-declared or the "
                         "<root>/praxis/engine/plugins convention).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.target and not args.files:
        ap.error("give --target and/or --files")
    base = Path(args.frm).resolve()
    files = rt.split_files(args.files)
    manifest = manifest_for(base, args.target, files, args.engine_plugins)
    frame = build_frame(base, args.target, files, args.unit_of_work or None, manifest)
    touch_if_framed(frame)
    if args.json:
        print(json.dumps(frame, indent=2))
    else:
        print_frame(frame)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

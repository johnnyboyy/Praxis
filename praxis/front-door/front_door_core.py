#!/usr/bin/env python3
"""front_door_core — the praxis front door as transport-free functions.

This is the brain the two transports share:
  - server.py    wraps these as FastMCP tools (Claude Code / any MCP client)
  - cli.py       wraps these as an argparse CLI emitting JSON (Pi's native extension, or any
                 caller that does not want the `mcp` package)

Each public function (`begin_work`, `compose_spawn`, `close_work`, `work_status`) returns a plain
dict — the transports serialize. It imports praxis scripts as library code and calls corpora's
`compose` / `spawn-parts` capabilities (via `engine.py`, from the governing root's registered
manifest) to build each frame. With no engine registered every function degrades to root facts,
exactly as `frame.py` does.

See server.py's module docstring for the delivery/lease/gate rationale; it applies verbatim here.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

# The sibling scripts dir is put on sys.path by whichever transport imports this module
# (server.py / cli.py); both set PRAXIS_SCRIPTS or add the path before importing.
import engine  # noqa: E402
import root_tree  # noqa: E402
import frame as fr  # noqa: E402
import frame_store as fs  # noqa: E402
import route as rt  # noqa: E402
import units as un  # noqa: E402
import runtime_policy as rp  # noqa: E402
import workflow as wf  # noqa: E402

# P2 bridge (docs/CONDUCTOR-PLAN.md): begin_work/close_work also write unit.framed/unit.closed
# events to the conductor journal, so conductor/journal.open_unit has state to read. Additive next
# to the existing marker — the marker keeps authorizing the Pi-extension gate (not yet ported to
# the journal) and the legacy fallback in praxis-frame-gate.sh; the journal is what the
# journal-first gate check (praxis/scripts/gate.py) consults.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "conductor"))
import journal  # noqa: E402

TRACE_NAME = "trace.jsonl"


def _trace_entries(root: Path) -> list[dict]:
    path = root_tree.praxis_dir(root) / TRACE_NAME
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return out


def _trace_summary(entries: list[dict]) -> dict:
    """Which phases (and whole workflows) tend to deliver vs stall — the A/B surface the trace
    exists for. Counts outcome events (the spawn path carries result/stall); frame/close events are
    timeline only."""
    def bucket() -> dict:
        return {"runs": 0, "result": 0, "stall": 0}
    by_phase: dict[str, dict] = {}
    by_workflow: dict[str, dict] = {}
    stalls: list[dict] = []
    for e in entries:
        outcome = e.get("outcome")
        if outcome not in ("result", "stall"):
            continue
        phase = e.get("unit_of_work") or "(none)"
        bp = by_phase.setdefault(phase, bucket())
        bp["runs"] += 1
        bp[outcome] += 1
        flow = e.get("workflow")
        if flow:
            bw = by_workflow.setdefault(flow, bucket())
            bw["runs"] += 1
            bw[outcome] += 1
        if outcome == "stall":
            stalls.append({"ts": e.get("ts"), "unit_of_work": phase,
                           "workflow": flow, "status": e.get("status"),
                           "surfaced": e.get("surfaced")})
    return {"by_phase": by_phase, "by_workflow": by_workflow, "recent_stalls": stalls[-5:]}


def _config_text(root: Path) -> str | None:
    """The governing root's .praxis/config.md text, for runtime-policy overrides."""
    cfg = root_tree.praxis_dir(root) / "config.md"
    try:
        return cfg.read_text()
    except OSError:
        return None


def _workflow_info(root: Path, unit_of_work: str, workflow: str | None) -> dict | None:
    """Where this unit sits in a declared workflow (see workflow.py), or None when no workflow was
    named. Attached to the front-door result so the trace can be tagged and the caller can see
    what phase comes next."""
    if not workflow:
        return None
    return wf.info(root, workflow, unit_of_work)


def _runtime_recommendation(root: Path, unit_of_work: str, frame: dict) -> dict:
    """Praxis's HOW-it-runs recommendation for this unit (see runtime_policy). Attached to the
    front-door result so the harness can apply it and audit it."""
    return rp.recommend(unit_of_work, frame.get("size_floor"),
                        frame.get("composition"), _config_text(root))


RUNTIME_AUDIT_NAME = "runtime-audit.log"


def _runtime_audit_tail(root: Path, n: int = 5) -> list[dict]:
    """The last n applied-runtime records the harness logged for this root — the review surface."""
    path = root_tree.praxis_dir(root) / RUNTIME_AUDIT_NAME
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text().splitlines()[-n:]:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return out


def _resolve_engine(base: Path, target: str | None, files: list[str]):
    slot = fr.auto_engine_slot(base, target, files)
    return engine.load_registered(slot) if slot else None


def _single_root(frame: dict) -> Path | None:
    if frame.get("roots") and not frame["spans_multiple_roots"]:
        return Path(frame["roots"][0]["path"])
    return None


def _spawn_parts(root: Path, domains: list[str], manifest: dict | None) -> dict:
    """Resolve the engine's `spawn-parts` capability (stance frame + domain bodies + handoff
    schema) for an already-composed domain set. Degrades to a note, never raises."""
    payload, note = engine.call_json(
        manifest, "spawn-parts", {"root": str(root), "domains": ",".join(domains), "json": True},
        timeout=30, none_note="no engine registered — spawn parts unavailable")
    if payload is None:
        return {"available": False, "note": note}
    return {"available": True, **payload}


PAYLOAD_NAME = ".frame-payload.md"

# Mirrors praxis-frame-gate.sh's MAX_AGE_SECONDS: an open marker younger than this is a live
# same-session frame (re-framing it is normal); older means the prior unit expired by staleness
# without its close ceremony ever running.
FRAME_MAX_AGE_SECONDS = 1800


def _unclosed_prior(root: Path, new_unit: str) -> dict | None:
    """The prior frame's close-ceremony debt, if any."""
    marker = root_tree.praxis_dir(root) / fr.FRAME_MARKER_NAME
    if not marker.is_file():
        return None
    try:
        prior = json.loads(marker.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(prior, dict) or prior.get("closed") or not prior.get("unit_of_work"):
        return None
    age = int(time.time() - prior.get("timestamp", 0))
    if age <= FRAME_MAX_AGE_SECONDS and prior.get("unit_of_work") == new_unit:
        return None
    dirty = None
    try:
        import subprocess
        proc = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                              capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            dirty = len([l for l in proc.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    return {"unit_of_work": prior.get("unit_of_work"), "age_seconds": age,
            "git_dirty_paths": dirty}


def _write_payload(root: Path, unit_of_work: str, composition: list[str],
                   spawn_parts: dict, lease: dict | None = None) -> dict:
    """Render the engine's spawn parts to `<root>/.praxis/.frame-payload.md` and return its
    metadata. The file — not the tool result — carries the domain bodies; the payload-read stamp
    verifies the file was actually read before the gate lets inline work edit."""
    path = root_tree.praxis_dir(root) / PAYLOAD_NAME
    sections = [f"# Frame payload · unit-of-work: {unit_of_work}",
                f"composed domains: {', '.join(composition)}"]
    if lease:
        if lease.get("edit_surface"):
            sections.append(f"edit-surface: {', '.join(lease['edit_surface'])} — this unit may "
                            f"write ONLY these paths (plus praxis bookkeeping); an edit outside "
                            f"them is a different unit of work and needs its own begin_work")
        if lease.get("output"):
            sections.append(f"output: {lease['output']} — delivering this ends the unit; call "
                            f"close_work then, not when the clock runs out")
    sections.append("")
    for part in spawn_parts.get("parts", []):
        sections.append(f"<!-- slot: {part['slot']} -->")
        sections.append(part["body"])
        sections.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(sections)
    path.write_text(text)
    return {"path": str(path), "bytes": len(text.encode()),
            "problems": spawn_parts.get("problems", [])}


def _phase_inventory(root: Path) -> list[dict]:
    """The root's registered phases with their entry conditions — deterministic facts surfaced so a
    task that matches an existing process gets routed to it instead of being improvised."""
    phases_dir = root_tree.praxis_dir(root) / "phases"
    out = []
    if not phases_dir.is_dir():
        return out
    for p in sorted(phases_dir.glob("*.md")):
        entry = None
        try:
            lines = p.read_text().splitlines()
            for i, line in enumerate(lines):
                m = re.match(r"\*\*entry condition[^:*]*:\*\*\s*(.+)", line, re.IGNORECASE)
                if m:
                    para = [m.group(1).strip()]
                    for cont in lines[i + 1:]:
                        if not cont.strip():
                            break
                        para.append(cont.strip())
                    entry = " ".join(para)
                    break
        except OSError:
            pass
        out.append({"phase": p.stem, "entry": entry})
    return out


def _norm_files(files: list[str] | str | None) -> list[str]:
    if files is None:
        return []
    if isinstance(files, str):
        return [f.strip() for f in files.split(",") if f.strip()]
    return list(files)


def _validate_targets(base: Path, target: str | None,
                      files: list[str]) -> tuple[str | None, list[str], list[str], str | None]:
    """Resolve every target to an absolute path that actually exists, salvaging the common
    mixed-base mistake. Returns (target, files, warnings, error)."""
    warnings: list[str] = []
    resolved_any = False

    def resolve_one(p: str) -> str:
        nonlocal resolved_any
        cand = [Path(p)] if Path(p).is_absolute() else [base / p, Path.cwd() / p]
        for c in cand:
            if c.exists():
                resolved_any = True
                if not Path(p).is_absolute() and c == Path.cwd() / p:
                    warnings.append(f"'{p}' does not exist under search base {base} — "
                                    f"resolved against cwd as {c}")
                return str(c)
        warnings.append(f"'{p}' does not exist under {base}"
                        + ("" if Path(p).is_absolute() else f" or {Path.cwd()}"))
        return str(cand[0])

    r_target = resolve_one(target) if target else None
    r_files = [resolve_one(f) for f in files]
    if (target or files) and not resolved_any:
        return r_target, r_files, warnings, (
            "no given target/file exists on disk — check the paths (are they relative to the "
            "wrong base?) and re-call; refusing to frame nonexistent paths")
    return r_target, r_files, warnings, None


def begin_work(unit_of_work: str, target: str | None = None,
               files: list[str] | str | None = None, workstream: str | None = None,
               execution: str | None = None, search_base: str | None = None,
               workflow: str | None = None) -> dict:
    """Frame + route the unit of work, persist the frame when a workstream is named, and open the
    edit gate for this session. See server.py's tool docstring for the full contract."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    target, file_list, path_warnings, path_error = _validate_targets(
        base, target, _norm_files(files))
    if path_error:
        return {"error": path_error, "warnings": path_warnings}
    manifest = _resolve_engine(base, target, file_list)

    route = rt.build_route(base, target, file_list, unit_of_work, workstream, manifest)
    if path_warnings:
        route["signals"] = route["signals"] + [f"path: {w}" for w in path_warnings]
    frame = route["frame"]
    result: dict = {"root": None, "frame": frame,
                    "execution_shape": route["execution_shape"], "signals": route["signals"]}

    note = frame.get("composition_note")
    if note and note != "ok":
        result["warnings"] = [f"COMPOSITION: {note}"]
        if "matches no domain" in note:
            result["warnings"].append(
                "unit_of_work is not a known unit — the composition above is universal domains "
                "only, with NO task-specific judgment. Fit the task to a known unit (see the "
                "phase inventory in this result) and re-call; if NO known unit genuinely fits, "
                "that misfit is a gap in the system's vocabulary — surface it to the operator "
                "and author the unit/phase through plugin-authoring rather than proceeding "
                "under universal-only judgment.")

    root = _single_root(frame)
    if root is None:
        result["gate"] = "closed — no single governing root; decompose and frame each piece"
        return result

    result["root"] = str(root)
    result["phases"] = _phase_inventory(root)
    result["runtime"] = _runtime_recommendation(root, unit_of_work, frame)
    wf_info = _workflow_info(root, unit_of_work, workflow)
    if wf_info is not None:
        result["workflow"] = wf_info
        if wf_info.get("known") and wf_info.get("unit_in_workflow") is False:
            result.setdefault("warnings", []).append(
                f"WORKFLOW: unit '{unit_of_work}' is not a phase in workflow '{workflow}' "
                f"({', '.join(wf_info.get('phases', []))}) — tagging the trace anyway, but check "
                f"the flow or the unit.")
        elif not wf_info.get("known"):
            result.setdefault("warnings", []).append(
                f"WORKFLOW: '{workflow}' is not declared in .praxis/workflow.json "
                f"(known: {', '.join(wf_info.get('known_workflows', [])) or 'none'}).")
    if workstream:
        fs.append_frame(root, workstream, frame, route["execution_shape"]["verdict"])

    lease = un.lease_for(root, unit_of_work)
    surface = lease.get("edit_surface") if lease else None
    output = lease.get("output") if lease else None
    if lease:
        result["lease"] = {
            "edit_surface": surface, "output": output,
            "note": ("edits outside the surface are denied by the gate — they are a different "
                     "unit of work; deliver the output and call close_work to end this one")}

        def _outside(p: str) -> bool:
            try:
                rel = str(Path(p).resolve().relative_to(root))
            except ValueError:
                return False
            return not un.surface_allows(surface, rel)

        out_of_surface = [p for p in ([target] if target else []) + file_list if _outside(p)]
        if out_of_surface:
            result.setdefault("warnings", []).append(
                f"LEASE: {len(out_of_surface)} given path(s) fall outside this unit's edit "
                f"surface ({', '.join(surface or [])}): {', '.join(out_of_surface)} — fine if "
                f"they are read inputs (the gate denies any actual edit to them); only if they "
                f"are the edit targets is this the wrong unit of work, in which case re-call "
                f"with the unit whose surface covers them.")

    unclosed = _unclosed_prior(root, unit_of_work)
    if unclosed:
        dirty = unclosed.get("git_dirty_paths")
        result.setdefault("warnings", []).append(
            f"UNCLOSED PRIOR UNIT: '{unclosed['unit_of_work']}' on this root was never closed — "
            f"its frame is {unclosed['age_seconds'] // 60} minutes old with no close_work call"
            + (f", and the root has {dirty} dirty git path(s)" if dirty else "")
            + ". Its close ceremony (handoff, commit decision, close_work) is pending debt: "
              "settle or explicitly abandon it with the operator before this unit proceeds, "
              "rather than letting the new frame silently bury it.")
        result["unclosed_prior"] = unclosed

    if execution not in ("inline", "spawn"):
        execution = "spawn"
        result["execution"] = (
            "spawn (defaulted) — undeclared execution routes to a spawn: one unit of work = one "
            "spawn = one handoff, and the spawn's death is the unit's close-out. Inline is the "
            "explicit exception: re-call with execution='inline' only when the operator asked "
            "for inline work or framing sized this trivial.")

    if execution == "inline" and lease and lease.get("execution") == "spawn":
        result["execution_rejected"] = (
            f"inline unavailable: this root's units.md declares unit '{unit_of_work}' "
            f"execution: spawn — a standing root policy, not a per-call judgment. Route it as a "
            f"spawn (compose_spawn → Read payload → Agent). If the operator genuinely wants "
            f"this unit inline in this root, the policy line in "
            f"{un.units_path(root)} is theirs to change.")
        result["gate"] = "closed — no frame written; the unit has not begun"
        return result

    seat = root_tree.governing_root_above(base)
    if execution == "inline" and seat is not None and Path(seat).resolve() != root.resolve():
        result["execution_rejected"] = (
            f"inline unavailable: this session is seated in {seat} but the work is governed by "
            f"{root} — a seat root holds the judgment between roots, never works inside another "
            f"root, and inline here would run {root.name}'s unit in {seat.name}'s context. "
            f"Route it as a spawn: call compose_spawn, Read the payload, and hand it to an "
            f"Agent with search_base={root}. For genuinely operator-directed inline work in "
            f"that root, re-call begin_work with search_base={root} — declaring the seat is the "
            f"re-seating act.")
        result["gate"] = "closed — no frame written; the unit has not begun"
        return result

    composition = frame.get("composition")
    delivery = "none"
    payload_path = None
    if execution == "inline" and composition:
        parts = _spawn_parts(root, composition, manifest)
        if parts.get("available"):
            payload = _write_payload(root, unit_of_work, composition, parts, lease)
            payload_path = payload["path"]
            delivery = "file"
            result["payload"] = payload
            result["delivery"] = (
                f"file — the domain bodies for this work are at {payload['path']} "
                f"({payload['bytes']} bytes). Read that file IN FULL before editing: it is the "
                f"judgment this work runs under, and the edit gate stays closed until the read "
                f"is recorded.")
        else:
            result["delivery"] = f"facts — spawn parts unavailable ({parts.get('note')})"
    elif execution == "spawn" and composition:
        delivery = "spawn"
        result["delivery"] = (
            "facts — bodies ride in the spawn prompt: call compose_spawn, Read the payload it "
            "writes (the gate requires that read before any edit), and inject it into the Agent "
            "prompt. The spawn delivers the unit's output and dies; direct edits here without "
            "the payload read are the inline path wearing spawn's clothes.")
    else:
        result["delivery"] = "facts — no composition available to deliver"

    fr.touch_frame_marker(root, marker_data={
        "unit_of_work": unit_of_work, "workstream": workstream,
        "composition": composition, "size_floor": frame.get("size_floor"),
        "execution": execution, "delivery": delivery, "payload": payload_path,
        "surface": surface, "output": output,
    })
    unit_id = uuid.uuid4().hex[:12]
    journal.append(root, "unit.framed", unit=unit_id,
                   unit_of_work=unit_of_work, workstream=workstream,
                   composition=composition, size_floor=frame.get("size_floor"),
                   execution=execution, delivery=delivery, payload=payload_path,
                   surface=surface, output=output)
    result["unit"] = unit_id
    result["gate"] = ("open once the payload file has been read" if delivery in ("file", "spawn")
                      else "open for this unit")
    return result


def compose_spawn(unit_of_work: str, target: str | None = None,
                  files: list[str] | str | None = None,
                  search_base: str | None = None, workflow: str | None = None) -> dict:
    """Compose the domain set for a unit of work and write the assembled spawn-prompt parts to
    `<root>/.praxis/.frame-payload.md`, returning the path."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    target, file_list, path_warnings, path_error = _validate_targets(
        base, target, _norm_files(files))
    if path_error:
        return {"error": path_error, "warnings": path_warnings}
    manifest = _resolve_engine(base, target, file_list)

    frame = fr.build_frame(base, target, file_list, unit_of_work, manifest)

    root = _single_root(frame)
    if root is None:
        return {"error": "no single governing root — decompose before composing a spawn",
                "frame": frame}
    composition = frame.get("composition")
    if not composition:
        return {"error": f"no composition ({frame.get('composition_note')})", "frame": frame}
    parts = _spawn_parts(root, composition, manifest)
    if not parts.get("available"):
        return {"error": f"spawn parts unavailable ({parts.get('note')})",
                "composition": composition}
    lease = un.lease_for(root, unit_of_work)
    payload = _write_payload(root, unit_of_work, composition, parts, lease)
    result = {"root": str(root), "unit_of_work": unit_of_work,
              "composition": composition, "payload": payload,
              "runtime": _runtime_recommendation(root, unit_of_work, frame),
              "workflow": _workflow_info(root, unit_of_work, workflow),
              "note": ("Read the payload file and inject its content into the Agent prompt — the "
                       "spawn's judgment rides there. Assemble invariants-first: payload at the "
                       "top, task-specific brief at the bottom, so same-composition spawns share "
                       "a byte-identical prefix and batches hit the provider's prompt cache.")}
    if lease:
        result["lease"] = {"edit_surface": lease.get("edit_surface"),
                           "output": lease.get("output")}
    return result


def close_work(search_base: str | None = None) -> dict:
    """Close out the current unit of work for the governing root."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    root = root_tree.governing_root_above(base)
    if root is None:
        return {"error": f"no praxis root at or above {base}"}
    closed = fr.close_frame_marker(root)
    open_unit = journal.open_unit(root)
    if open_unit is not None:
        journal.append(root, "unit.closed", unit=open_unit["unit"],
                       prior_unit_of_work=closed.get("prior_unit_of_work"))
    return {"root": str(root), **closed,
            "note": "next edit in this root requires a fresh begin_work"}


def work_status(search_base: str | None = None) -> dict:
    """Read-only introspection: the governing root, the frame marker's contents and age, and which
    sessions currently hold a stamp for it."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    root = root_tree.governing_root_above(base)
    if root is None:
        return {"error": f"no praxis root at or above {base}"}
    out: dict = {"root": str(root)}
    marker = root_tree.praxis_dir(root) / fr.FRAME_MARKER_NAME
    if marker.is_file():
        text = marker.read_text().strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        out["marker"] = parsed if isinstance(parsed, dict) else \
            ({"timestamp": float(text)} if text.replace(".", "", 1).isdigit() else {})
        ts = out["marker"].get("timestamp")
        if ts:
            out["marker_age_seconds"] = int(time.time() - ts)
    else:
        out["marker"] = None
    root_hash = fr.stamp_hash_for_root(root)
    stamp_base = Path(os.environ.get("TMPDIR", "/tmp")) / "praxis-front-door"
    out["session_stamps"] = sorted(
        p.parent.name for p in stamp_base.glob(f"*/{root_hash}")) if stamp_base.is_dir() else []
    out["runtime_audit"] = _runtime_audit_tail(root)
    entries = _trace_entries(root)
    out["trace"] = {"recent": entries[-8:], "summary": _trace_summary(entries)}
    return out


def trace(search_base: str | None = None) -> dict:
    """The workflow trace for the governing root: recent entries + the deliver-vs-stall summary."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    root = root_tree.governing_root_above(base)
    if root is None:
        return {"error": f"no praxis root at or above {base}"}
    entries = _trace_entries(root)
    return {"root": str(root), "recent": entries[-15:], "summary": _trace_summary(entries),
            "workflows": wf.load(root)}


def preframe(target: str | None = None, files: list[str] | str | None = None,
             search_base: str | None = None) -> dict:
    """The engine-light front of a frame, for L1 praxis-mode auto-framing at the INPUT boundary:
    the deterministic facts available before a unit-of-work is decided — which root governs the
    ask, whether it spans roots (decompose), the size floor, and the root's phase inventory. No
    unit-of-work, so no composition; this is what praxis knows before the routing judgment, enough
    to make the model frame up front instead of getting bounced by the gate mid-edit."""
    base = Path(search_base).resolve() if search_base else Path.cwd()
    file_list = _norm_files(files)
    # With no path named, the ask's root is the base (cwd) itself — frame resolves the root of a
    # target, so give it one.
    if not target and not file_list:
        target = str(base)
    manifest = _resolve_engine(base, target, file_list)
    frame = fr.build_frame(base, target, file_list, None, manifest)
    out: dict = {"base": str(base), "roots": frame.get("roots"),
                 "spans": frame.get("spans_multiple_roots"), "verdict": frame.get("verdict"),
                 "size_floor": frame.get("size_floor")}
    root = _single_root(frame)
    if root is not None:
        out["root"] = str(root)
        out["phases"] = _phase_inventory(root)
    return out

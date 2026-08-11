#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

JOURNAL_NAME = "journal.jsonl"

_APPEND_LOCK = threading.Lock()

STATE_EVENTS: dict[str, str] = {
    "unit.proposed": "proposed",
    "unit.framed": "framed",
    "unit.dispatched": "dispatched",
    "unit.running": "running",
    "unit.receipt": "verifying",
    "unit.verified": "verified",
    "unit.done": "done",
    "unit.stalled": "stalled",
    "unit.closed": "closed",
}

IN_FLIGHT = {"framed", "dispatched", "running", "verifying", "verified"}
CONCLUDED = {"done", "closed", "stalled"}


def _praxis_dir(root: Path) -> Path:
    for m in (".praxis", "praxis"):
        if (root / m).is_dir():
            return root / m
    return root / ".praxis"


def journal_path(root: Path) -> Path:
    return _praxis_dir(root) / JOURNAL_NAME


def append(root: Path, event: str, unit: str | None = None, **payload) -> dict:
    path = journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": payload.pop("ts", None) or time.time(), "event": event}
    if unit is not None:
        record["unit"] = unit
    record.update(payload)
    with _APPEND_LOCK:
        record["seq"] = _next_seq(path)
        with path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


def _next_seq(path: Path) -> int:
    if not path.is_file():
        return 0
    last = -1
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                last = max(last, int(json.loads(line).get("seq", -1)))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    except OSError:
        return 0
    return last + 1


def read(root: Path) -> list[dict]:
    path = journal_path(root)
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


def fold(root: Path) -> dict:
    units: dict[str, dict] = {}
    order: list[str] = []
    for ev in read(root):
        uid = ev.get("unit")
        if uid is None:
            continue
        if uid not in units:
            units[uid] = {"unit": uid, "state": None, "events": 0, "workflow": None,
                          "phase_index": None, "outcome": None, "status": None,
                          "surfaced": None, "last": {}}
            order.append(uid)
        u = units[uid]
        u["events"] += 1
        etype = ev.get("event", "")
        for k, v in ev.items():
            if k in ("ts", "seq", "event", "unit"):
                continue
            u["last"][k] = v
            if k in ("workflow", "phase_index", "outcome", "status", "surfaced"):
                u[k] = v
        if etype in STATE_EVENTS:
            u["state"] = STATE_EVENTS[etype]

    open_units = [uid for uid in order if units[uid]["state"] in IN_FLIGHT]
    return {"units": units, "open_units": open_units, "summary": _summary(units, order)}


def _summary(units: dict[str, dict], order: list[str]) -> dict:
    def bucket() -> dict:
        return {"runs": 0, "result": 0, "stall": 0}

    by_phase: dict[str, dict] = {}
    by_workflow: dict[str, dict] = {}
    stalls: list[dict] = []
    for uid in order:
        u = units[uid]
        outcome = u.get("outcome")
        if outcome not in ("result", "stall"):
            continue
        phase = u["last"].get("label") or u["last"].get("unit_of_work") or uid
        bp = by_phase.setdefault(phase, bucket())
        bp["runs"] += 1
        bp[outcome] += 1
        flow = u.get("workflow")
        if flow:
            bw = by_workflow.setdefault(flow, bucket())
            bw["runs"] += 1
            bw[outcome] += 1
        if outcome == "stall":
            stalls.append({"unit": uid, "phase": phase, "workflow": flow,
                           "status": u.get("status"), "surfaced": u.get("surfaced")})
    return {"by_phase": by_phase, "by_workflow": by_workflow, "recent_stalls": stalls[-5:]}


def state_of(root: Path, unit: str) -> str | None:
    u = fold(root)["units"].get(unit)
    return u["state"] if u else None


def gaps(root: Path) -> list[dict]:
    return [e for e in read(root) if e.get("event") == "conductor.gap"]


def gap_candidates(root: Path) -> list[dict]:
    tally: dict[tuple[str, str], dict] = {}
    for e in gaps(root):
        suggested = (e.get("suggested") or "").strip().lower()
        if not suggested:
            continue
        vocab = e.get("vocabulary", "task_kind")
        key = (vocab, suggested)
        rec = tally.setdefault(key, {"suggested": suggested, "vocabulary": vocab,
                                     "count": 0, "chosen_as": [], "examples": []})
        rec["count"] += 1
        chosen = e.get("chosen")
        if chosen and chosen not in rec["chosen_as"]:
            rec["chosen_as"].append(chosen)
        if e.get("intent"):
            rec["examples"].append(e["intent"])
    return sorted(tally.values(), key=lambda r: r["count"], reverse=True)


def note(root: Path, *, unit: str | None = None, source: str, body: str, **extra) -> dict:
    return append(root, "note", unit=unit, source=source, body=body, **extra)


def notes(root: Path, *, unit: str | None = None) -> list[dict]:
    out = [e for e in read(root) if e.get("event") == "note"]
    if unit is not None:
        out = [e for e in out if e.get("unit") == unit]
    return out


def open_unit(root: Path) -> dict | None:
    f = fold(root)
    if not f["open_units"]:
        return None
    uid = f["open_units"][-1]
    return f["units"][uid]

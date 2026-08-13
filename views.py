#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import journal

def cost(root: Path) -> dict:
    per_unit: dict[str, dict] = {}
    tokens = usd = calls = 0
    for e in journal.read(root):
        if e.get("event") != "unit.receipt":
            continue
        uid = e.get("unit")
        c = e.get("cost") or {}
        t = int(c.get("tokens", 0) or 0)
        d = float(c.get("usd", 0) or 0)
        n = int(e.get("tool_calls", 0) or 0)
        tokens += t
        usd += d
        calls += n
        pu = per_unit.setdefault(uid, {"tokens": 0, "usd": 0.0, "tool_calls": 0})
        pu["tokens"] += t
        pu["usd"] = round(pu["usd"] + d, 6)
        pu["tool_calls"] += n
    return {"tokens": tokens, "usd": round(usd, 6), "tool_calls": calls, "per_unit": per_unit}

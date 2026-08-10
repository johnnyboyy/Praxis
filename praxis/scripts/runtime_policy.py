#!/usr/bin/env python3
"""runtime_policy — praxis's decision of HOW a unit of work runs (the reasoning budget), separate
from corpora's decision of WHAT to think.

Deciding *how and when* something runs is a process/orchestration concern, so it lives here on the
praxis side, not in corpora. Corpora supplies an input — a unit of work carries a *stance* (design
work is divergent: generate and compare options; implementation is convergent: settle on the one
right change) — but the mapping from that stance to a concrete runtime knob (the thinking level the
harness runs the unit under) is a routing judgment praxis owns.

This module is deliberately small, data-driven, and reviewable: the two unit-of-work sets and the
matrix below ARE the policy. It is a recommendation — praxis proposes, the harness (the Pi
extension) applies it (child `--thinking` for a spawn, `setThinkingLevel` for inline) and logs what
it applied, so every runtime decision is auditable after the fact (see `work_status`'s
`runtime_audit`).

Operators review/override per root in `.praxis/config.md`:
    runtime-policy: off            # disable entirely (no recommendation applied)
    runtime-thinking: high         # force one level for every unit on this root

Standalone review:
    python3 runtime_policy.py recommend --unit-of-work implement-feature --size-floor by-judgment
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# ── The policy (this is the whole thing — edit here to change how units run) ─────────────────────

# Divergent = exploratory: the unit wants options generated and compared before converging.
DIVERGENT_UNITS = {
    "scan-architecture", "architecture-scan", "design", "plan-work", "route-work",
    "writing-draft", "debugging", "explore", "interview",
}
# Convergent = a target to settle on: refine toward the one right change.
CONVERGENT_UNITS = {
    "implement-feature", "fix-bug", "refactor", "comment-cleanup", "testing",
    "prose-revision", "writing-revision", "runtime-verification", "release-readiness",
    "scaffold-tests", "triage-scaffold",
}

VALID_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")


def stance_for(unit_of_work: str | None) -> str:
    if unit_of_work in DIVERGENT_UNITS:
        return "divergent"
    if unit_of_work in CONVERGENT_UNITS:
        return "convergent"
    return "neutral"


def _thinking_for(stance: str, size_floor: str | None) -> tuple[str, str]:
    """(level, reason) from the two praxis-owned facts: the unit's stance and the deterministic
    size floor (decompose / underspecified / by-judgment)."""
    if size_floor == "underspecified":
        return "high", "underspecified frame — reasoning is needed to disambiguate before acting"
    if size_floor == "decompose":
        return "high", "spans roots — multi-root decomposition/planning benefits from deeper reasoning"
    if stance == "divergent":
        return "high", "divergent stance — exploration benefits from a larger reasoning budget"
    if stance == "convergent":
        return "medium", "convergent stance — a settled target needs standard reasoning"
    return "medium", "neutral stance — default reasoning budget"


# ── Config overrides ─────────────────────────────────────────────────────────────────────────────

def _parse_overrides(config_text: str | None) -> dict:
    if not config_text:
        return {}
    out: dict = {}
    m = re.search(r"^runtime-policy:\s*(\w+)\s*$", config_text, re.MULTILINE | re.IGNORECASE)
    if m and m.group(1).lower() in ("off", "no", "false"):
        out["enabled"] = False
    m = re.search(r"^runtime-thinking:\s*([\w-]+)\s*$", config_text, re.MULTILINE | re.IGNORECASE)
    if m and m.group(1).lower() in VALID_LEVELS:
        out["forced_thinking"] = m.group(1).lower()
    return out


def recommend(unit_of_work: str | None, size_floor: str | None,
              composition: list[str] | None = None, config_text: str | None = None) -> dict:
    """The runtime recommendation for a unit of work. Pure — same inputs, same output.

    Returns: {enabled, stance, thinking, reason, inputs}. `enabled: False` means the operator
    turned the policy off for this root; the recommendation is still computed (for the audit) but
    the harness should not apply it."""
    overrides = _parse_overrides(config_text)
    stance = stance_for(unit_of_work)
    level, reason = _thinking_for(stance, size_floor)
    if overrides.get("forced_thinking"):
        level = overrides["forced_thinking"]
        reason = f"operator override in .praxis/config.md (runtime-thinking: {level})"
    return {
        "enabled": overrides.get("enabled", True),
        "stance": stance,
        "thinking": level,
        "reason": reason,
        "inputs": {"unit_of_work": unit_of_work, "size_floor": size_floor,
                   "composition_size": len(composition) if composition else None},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="runtime_policy")
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("recommend", help="print the runtime recommendation as JSON")
    r.add_argument("--unit-of-work", default=None)
    r.add_argument("--size-floor", default=None)
    r.add_argument("--composition", default=None, help="comma-separated domain names")
    args = ap.parse_args(argv)
    comp = [c.strip() for c in args.composition.split(",")] if args.composition else None
    print(json.dumps(recommend(args.unit_of_work, args.size_floor, comp), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

class EdgeType(str, Enum):
    create = "create"
    carry = "carry"
    extract = "extract"

GATES: dict[EdgeType, str] = {
    EdgeType.create: "does-it",
    EdgeType.carry: "regression",
    EdgeType.extract: "coverage-diff",
}

WHENS = ("pass", "fail", "always", "feeds", "fact")
STANCES = ("divergent", "convergent", "neutral")
DELIVERIES = ("inline", "spawn", "deterministic")

@dataclass
class Phase:

    name: str
    stance: str = "neutral"
    intent: str = ""
    produces: str = ""
    delivery: str = "inline"
    run: object | None = None

@dataclass
class Workflow:

    name: str
    phases: list
    edges: list
    verifiers: object | None = None  # optional factory: (root) -> {gate-name: Verifier}

    def phase(self, name: str) -> Phase | None:
        return next((p for p in self.phases if p.name == name), None)

    @property
    def first(self) -> Phase:
        return self.phases[0]

def edge_parts(edge) -> tuple:
    frm, to, when, et = edge[0], edge[1], edge[2], edge[3]
    predicate = edge[4] if len(edge) > 4 else None
    return frm, to, when, et, predicate

def next_phases(workflow: Workflow, from_phase: str, when: str) -> list:
    targets = [t for (f, t, w, _et, _pred) in map(edge_parts, workflow.edges)
               if f == from_phase and w == when]
    return [p for p in workflow.phases if p.name in targets]

PLAN = Phase("plan", stance="divergent",
             intent="extract an open request into units/edges", produces="spec")
IMPLEMENT = Phase("implement", stance="convergent",
                  intent="make the tests pass", produces="code")
VERIFY = Phase("verify", stance="neutral",
               intent="run the suite", produces="verdict", delivery="deterministic")
FIX = Phase("fix", stance="convergent",
            intent="repair a failed verification", produces="code")
CLOSE = Phase("close", stance="neutral", intent="finalize the unit", produces="closure")

SEED_PHASES: dict[str, Phase] = {
    p.name: p for p in (PLAN, IMPLEMENT, VERIFY, FIX, CLOSE)
}


BUILD_VERIFY = Workflow(
    name="build-verify",
    phases=[IMPLEMENT, VERIFY, FIX, CLOSE],
    edges=[
        ("implement", "verify", "pass", EdgeType.carry),
        ("verify", "close", "pass", EdgeType.carry),
        ("verify", "fix", "fail", EdgeType.carry),
        ("fix", "verify", "pass", EdgeType.carry),
    ],
)

SEED_WORKFLOWS: dict[str, Workflow] = {
    w.name: w for w in (BUILD_VERIFY,)
}

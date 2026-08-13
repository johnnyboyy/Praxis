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

WHENS = ("pass", "fail", "always", "agent-choice", "feeds", "fact")
STANCES = ("divergent", "convergent", "neutral")
DELIVERIES = ("inline", "spawn", "deterministic")


@dataclass
class Phase:

    name: str
    stance: str = "neutral"
    intent: str = ""
    produces: str = ""
    delivery: str = "inline"
    run: object | None = None  # Callable[(root, unit, composed)] -> evidence dict, for delivery=="deterministic"


@dataclass
class Workflow:

    name: str
    phases: list
    edges: list
    expand: dict | None = None

    def phase(self, name: str) -> Phase | None:
        return next((p for p in self.phases if p.name == name), None)

    @property
    def first(self) -> Phase:
        return self.phases[0]


def edge_parts(edge) -> tuple:
    """Normalize an edge to (frm, to, when, edge_type, predicate).

    4-tuples (from,to,when,EdgeType) pad predicate=None — fully backward-compatible.
    5-tuples (from,to,"fact",EdgeType,predicate) carry a Callable[[dict], bool]."""
    frm, to, when, et = edge[0], edge[1], edge[2], edge[3]
    predicate = edge[4] if len(edge) > 4 else None
    return frm, to, when, et, predicate


def next_phases(workflow: Workflow, from_phase: str, when: str) -> list:
    targets = [t for (f, t, w, _et, _pred) in map(edge_parts, workflow.edges)
               if f == from_phase and w == when]
    return [p for p in workflow.phases if p.name in targets]


PLAN = Phase("plan", stance="divergent",
             intent="extract an open request into units/edges", produces="spec")
WRITE_TESTS = Phase("write-tests", stance="divergent",
                    intent="author intent as executable tests", produces="tests")
IMPLEMENT = Phase("implement", stance="convergent",
                  intent="make the tests pass", produces="code")
REFACTOR = Phase("refactor", stance="convergent",
                 intent="improve structure with behavior fixed", produces="code")
TEST_CLEANUP = Phase("test-cleanup", stance="convergent",
                     intent="prune tests editorially", produces="tests")
VERIFY = Phase("verify", stance="neutral",
               intent="run the suite", produces="verdict", delivery="deterministic")
FIX = Phase("fix", stance="convergent",
            intent="repair a failed verification", produces="code")
CLOSE = Phase("close", stance="neutral", intent="finalize the unit", produces="closure")
EXTRACT = Phase("extract", stance="divergent",
                intent="inventory/classify the original into a spec", produces="spec")
SYNTHESIZE = Phase("synthesize", stance="convergent",
                   intent="rebuild to the interface, free of the attractor", produces="code")

SEED_PHASES: dict[str, Phase] = {
    p.name: p for p in (PLAN, WRITE_TESTS, IMPLEMENT, REFACTOR, TEST_CLEANUP,
                        VERIFY, FIX, CLOSE, EXTRACT, SYNTHESIZE)
}


TDD_UNIT = Workflow(
    name="tdd-unit",
    phases=[WRITE_TESTS, IMPLEMENT, REFACTOR, TEST_CLEANUP],
    edges=[
        ("write-tests", "implement", "pass", EdgeType.carry),
        ("implement", "refactor", "pass", EdgeType.carry),
        ("refactor", "test-cleanup", "pass", EdgeType.carry),
    ],
)

REBUILD_TRIPLE = Workflow(
    name="rebuild-triple",
    # SYNTHESIZE is terminal. The preservation gate is the edge-verifier keyed
    # `coverage-diff` (GATES[extract]) that fires at synthesize-exit — the spec is
    # already threaded into composed["spec"] via the extract edge, so no separate
    # coverage-diff phase is needed. The does-it gate at extract-exit is the
    # adequacy gate (extracted tests vs the ORIGINAL + spec split-enforcement).
    phases=[EXTRACT, SYNTHESIZE],
    edges=[
        ("extract", "synthesize", "pass", EdgeType.extract),
    ],
)

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
    w.name: w for w in (TDD_UNIT, REBUILD_TRIPLE, BUILD_VERIFY)
}

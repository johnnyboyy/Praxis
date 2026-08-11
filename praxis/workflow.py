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

WHENS = ("pass", "fail", "always", "agent-choice", "feeds")
STANCES = ("divergent", "convergent", "neutral")
DELIVERIES = ("inline", "spawn", "deterministic")


@dataclass
class Phase:

    name: str
    stance: str = "neutral"
    intent: str = ""
    produces: str = ""
    delivery: str = "inline"


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


def next_phases(workflow: Workflow, from_phase: str, when: str) -> list:
    targets = [t for (f, t, w, _et) in workflow.edges if f == from_phase and w == when]
    return [p for p in workflow.phases if p.name in targets]


PLAN = Phase("plan", stance="divergent",
             intent="extract an open request into units/edges", produces="ir")
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
                intent="inventory/classify the original into an IR", produces="ir")
SYNTHESIZE = Phase("synthesize", stance="convergent",
                   intent="rebuild to the interface, free of the attractor", produces="code")
COVERAGE_DIFF = Phase("coverage-diff", stance="neutral",
                      intent="losslessness + completeness, both directions",
                      produces="diff", delivery="deterministic")

SEED_PHASES: dict[str, Phase] = {
    p.name: p for p in (PLAN, WRITE_TESTS, IMPLEMENT, REFACTOR, TEST_CLEANUP,
                        VERIFY, FIX, CLOSE, EXTRACT, SYNTHESIZE, COVERAGE_DIFF)
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
    phases=[EXTRACT, SYNTHESIZE, COVERAGE_DIFF],
    edges=[
        ("extract", "synthesize", "pass", EdgeType.extract),
        ("synthesize", "coverage-diff", "pass", EdgeType.carry),
        ("extract", "coverage-diff", "feeds", EdgeType.carry),
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

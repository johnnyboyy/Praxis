#!/usr/bin/env python3
"""Coding-process vocabulary: the tdd-unit workflow and its phases.
Registering this plugin gives a root TDD process vocabulary; the core seed
carries only the minimal build-verify loop."""
from __future__ import annotations

from workflow import EdgeType, Phase, Workflow

PRAXIS_PLUGIN = True

WRITE_TESTS = Phase("write-tests", stance="divergent",
                    intent="author intent as executable tests", produces="tests")
REFACTOR = Phase("refactor", stance="convergent",
                 intent="improve structure with behavior fixed", produces="code")
TEST_CLEANUP = Phase("test-cleanup", stance="convergent",
                     intent="prune tests editorially", produces="tests")

TDD_UNIT = Workflow(
    name="tdd-unit",
    phases=[WRITE_TESTS,
            Phase("implement", stance="convergent",
                  intent="make the tests pass", produces="code"),
            REFACTOR, TEST_CLEANUP],
    edges=[
        ("write-tests", "implement", "pass", EdgeType.carry),
        ("implement", "refactor", "pass", EdgeType.carry),
        ("refactor", "test-cleanup", "pass", EdgeType.carry),
    ],
)

class CodingProcessContributor:

    source = "coding-process"

    def contribute(self, situation):
        return []

    def phases(self):
        return [WRITE_TESTS, REFACTOR, TEST_CLEANUP]

    def workflows(self):
        return [TDD_UNIT]

def make(root):
    return CodingProcessContributor()

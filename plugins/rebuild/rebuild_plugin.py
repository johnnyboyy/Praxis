#!/usr/bin/env python3
"""The rebuild triple as a plugin: extract → (drop the original) → synthesize,
gated by spec adequacy at extract-exit and tripwire ∘ coverage-diff at
synthesize-exit. Registering this plugin gives a root the `rebuild-triple`
workflow; an unregistered root has no rebuild vocabulary.

The tripwire's capture hook (`hooks/tripwire_log.sh`) is wired via the praxis
plugin's hooks.json; without it, tool-log capture is inactive and the tripwire
only sees a `tool_log` the driver passes explicitly."""
from __future__ import annotations

from rebuild_verifiers import rebuild_triple_verifiers
from workflow import EdgeType, Phase, Workflow

PRAXIS_PLUGIN = True

EXTRACT = Phase("extract", stance="divergent",
                intent="inventory/classify the original into a spec", produces="spec")
SYNTHESIZE = Phase("synthesize", stance="convergent",
                   intent="rebuild to the interface, free of the attractor", produces="code")

REBUILD_TRIPLE = Workflow(
    name="rebuild-triple",
    phases=[EXTRACT, SYNTHESIZE],
    edges=[
        ("extract", "synthesize", "pass", EdgeType.extract),
    ],
    verifiers=rebuild_triple_verifiers,
)

class RebuildContributor:

    source = "rebuild"

    def contribute(self, situation):
        return []

    def phases(self):
        return [EXTRACT, SYNTHESIZE]

    def workflows(self):
        return [REBUILD_TRIPLE]

def make(root):
    return RebuildContributor()

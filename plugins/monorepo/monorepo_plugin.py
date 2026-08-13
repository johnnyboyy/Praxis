"""monorepo — a judgment plugin carrying a small coordination PROCESS face.

Carries the hand-authored `monorepo-coordination` domain for the corpora composer
to discover and inject (the JUDGMENT face). Corpora finds this plugin via
`contributors_for(root)`, reads `*.md` from `domains_dir`, and stamps every domain
`owner = "monorepo"`.

It also injects a little PROCESS framing for units that run at a coordination root —
a root whose children include other praxis roots. That framing is *judgment about
orchestration only*: frame at the border, decompose one unit per child root, hand
each unit through the child's OWN front door, carry cross-root dependencies through
interop. It deliberately does NOT resolve, traverse, or map the root tree — that is
core `root_tree`'s job (find_roots / nearest_root / span / interop_root). This plugin
never re-implements traversal; it only frames the process once core has established
which roots exist.
"""

from __future__ import annotations

from pathlib import Path

from contributors import Contribution

PRAXIS_PLUGIN = True

_COORDINATION_PHASES = {"coordination", "coordinate-work"}

_FRAMING_PRIORITY = 5

_COORDINATION_FRAMING = (
    "This unit runs at a coordination root — a root whose children include other "
    "praxis roots. The root's job at this border is to FRAME, DECOMPOSE, and HAND OFF; "
    "the work itself runs inside whichever child root owns it, through that child's own "
    "front door.\n"
    "- Which root owns which file is a FACT from core root_tree (find_roots / "
    "nearest_root / span) — do not re-derive it by hand and do not re-implement "
    "traversal here.\n"
    "- A spanning task is one framed unit per child root; hand each through the "
    "CHILD's own front door so it composes and ratifies against the child's own pool, "
    "never the parent's.\n"
    "- Cross-root dependencies go through an interop handoff between the two child "
    "roots — a bidirectional handoff, never one agent straddling both.\n"
    "- Root-only work (workspace tooling, shared pipeline config the coordination root "
    "itself owns) is an ordinary unit at the coordination root, composed from its own "
    "pool.\n"
    "The judgment seam (not scripted): which child owns an ambiguous outcome, whether a "
    "task is genuinely cross-cutting or one child's work wearing a broad description, "
    "and which decomposed unit must land first."
)

def _is_coordination(situation) -> bool:
    if getattr(situation, "subject", None) == "process":
        return True
    if getattr(situation, "phase_name", None) in _COORDINATION_PHASES:
        return True
    if getattr(situation, "workflow", None) in _COORDINATION_PHASES:
        return True
    return False

class MonorepoJudgment:

    source = "monorepo"

    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):

        self.root = root

    def contribute(self, situation) -> list:
        if not _is_coordination(situation):
            return []
        return [Contribution(
            source="monorepo",
            title="Coordination-root process framing",
            body=_COORDINATION_FRAMING,
            priority=_FRAMING_PRIORITY,
            meta={"framing": "coordination"},
        )]

def make(root) -> "MonorepoJudgment":
    return MonorepoJudgment(root)

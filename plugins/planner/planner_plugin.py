"""planner — a PROCESS-face praxis plugin providing the `intake` workflow.

The planner turns an open, under-specified request into a plannable unit of
work. Its four phases form the `intake` workflow:

  1. interview  (inline, divergent) — an operator dialogue that surfaces the
     decisions the work hinges on and writes a *decision-frontier* artifact.
  2. frontier   (deterministic)     — a PURE reader of that artifact: it counts
     the still-unanswered decisions and emits a fact the workflow routes on.
  3. barrier    (inline, convergent) — define the contract the work must clear
     (for code: the tests / acceptance conditions).
  4. plan       (inline, convergent) — emit a sequenced tasklist referencing the
     barrier.

Routing: interview -> frontier (always). frontier loops back to interview while
the frontier is "open" (any unanswered decision), and advances to barrier once
it is "clear". barrier -> plan (pass), plan -> close (the seed close phase, as in
the uiux / writing workflows).

The planner carries JUDGMENT, but the contributor itself injects nothing via
`contribute()` (it returns `[]`). Its judgment reaches context through the
corpora composer over this plugin's own `domains_dir` (./domains) — the same
JUDGMENT-face mechanism the other judgment plugins use.

--------------------------------------------------------------------------------
FRONTIER ARTIFACT FORMAT  (`<root>/.praxis/planner/frontier.md`)
--------------------------------------------------------------------------------
The decision frontier is a plain markdown checklist. Each decision is one
GitHub-style task-list item:

    # Decision frontier

    - [ ] Which datastore backs the queue?
    - [x] Auth is out of scope for this unit.
    - [ ] Do we support in-place migration?

An item `- [ ]` (empty box) is an UNANSWERED decision; `- [x]` / `- [X]`
(a checked box) is ANSWERED. Any other line (headings, prose, blank lines) is
ignored. The parser is deliberately tolerant: leading whitespace is allowed and
the box may be `[ ]`, `[x]`, or `[X]`.

The `frontier` fact is:
  - "open"  when one or more decisions are unanswered, else "clear".
  - the count of unanswered decisions rides alongside as `open`.

A MISSING or EMPTY artifact (no task-list items at all) is read as `open` with
`open == 0`: there is no evidence the operator dialogue has surfaced and settled
the decisions yet, so intake must not fall through to barrier/plan. This is the
honest reading — "no frontier written" is not "frontier cleared". The interview
phase always writes the artifact, so a real cleared frontier is a file whose
every item is checked (open == 0 AND at least one item), which the routing
distinguishes because that state emits "clear".

Both the `interview` phase (which writes the artifact) and the pl-skill / pl-tests
(which read it) can rely on this shape.
"""

from __future__ import annotations

import re
from pathlib import Path

from workflow import CLOSE, EdgeType, Phase, Workflow

PRAXIS_PLUGIN = True

source = "planner"

_ITEM_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s*(.*\S)?\s*$")

def frontier_path(root) -> Path:
    return Path(root) / ".praxis" / "planner" / "frontier.md"

def parse_frontier(text: str) -> dict:
    total = 0
    answered = 0
    for line in (text or "").splitlines():
        m = _ITEM_RE.match(line)
        if not m:
            continue
        total += 1
        if m.group(1) in ("x", "X"):
            answered += 1
    open_count = total - answered

    frontier = "clear" if (total > 0 and open_count == 0) else "open"
    return {"total": total, "answered": answered, "open": open_count,
            "frontier": frontier}

def read_frontier(root) -> dict:
    try:
        text = frontier_path(root).read_text()
    except OSError:
        text = ""
    return parse_frontier(text)

INTERVIEW = Phase(
    "interview", stance="divergent", delivery="inline",
    intent=("operator dialogue: surface the decisions the work hinges on and "
            "record them as a decision-frontier checklist at "
            ".praxis/planner/frontier.md, each marked answered or not"),
    produces="frontier")

FRONTIER = Phase(
    "frontier", stance="neutral", delivery="deterministic",
    intent="count the still-unanswered decisions on the frontier artifact",
    produces="frontier-state")

BARRIER = Phase(
    "barrier", stance="convergent", delivery="inline",
    intent=("define the contract the work must satisfy — for code, the tests / "
            "acceptance conditions the work must clear"),
    produces="barrier")

PLAN = Phase(
    "plan", stance="convergent", delivery="inline",
    intent="emit a sequenced tasklist that references the barrier",
    produces="tasklist")

def _run_frontier(root, unit, composed) -> dict:
    summary = read_frontier(root)
    return {"passed": True,
            "facts": {"frontier": summary["frontier"], "open": summary["open"]}}

FRONTIER.run = _run_frontier

PLANNER_PHASES = [INTERVIEW, FRONTIER, BARRIER, PLAN]

def _frontier_open(ev) -> bool:
    return (ev.get("facts") or {}).get("frontier") == "open"

def _frontier_clear(ev) -> bool:
    return (ev.get("facts") or {}).get("frontier") == "clear"

INTAKE = Workflow(
    name="intake",
    phases=[INTERVIEW, FRONTIER, BARRIER, PLAN, CLOSE],
    edges=[
        ("interview", "frontier", "always", EdgeType.carry),

        ("frontier", "interview", "fact", EdgeType.carry, _frontier_open),
        ("frontier", "barrier", "fact", EdgeType.create, _frontier_clear),
        ("barrier", "plan", "pass", EdgeType.carry),
        ("plan", "close", "pass", EdgeType.carry),
    ],
)

PLANNER_WORKFLOWS = [INTAKE]

class PlannerProcess:

    source = "planner"

    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):

        self.root = root

    def contribute(self, situation) -> list:
        return []

    def phases(self) -> list:
        return list(PLANNER_PHASES)

    def workflows(self) -> list:
        return list(PLANNER_WORKFLOWS)

def make(root) -> "PlannerProcess":
    return PlannerProcess(root)

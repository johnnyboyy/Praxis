
from pathlib import Path

import planner_plugin
import registry
import run as R
from workflow import edge_parts
from workflow_run import _choose_edge

def _planner(root):
    return planner_plugin.make(str(root))

def test_resolve_phases_contains_planner_phases_plus_seed(tmp_path):
    phases = registry.resolve_phases(str(tmp_path), [_planner(tmp_path)])
    assert {"interview", "frontier", "barrier", "plan"} <= set(phases)
    assert "close" in phases

def test_every_planner_phase_validates(tmp_path):
    for p in _planner(tmp_path).phases():
        assert registry.validate_phase(p) == [], p.name

def test_resolve_workflows_contains_intake_and_validates(tmp_path):
    contributor = _planner(tmp_path)
    phases = registry.resolve_phases(str(tmp_path), [contributor])
    workflows = registry.resolve_workflows(str(tmp_path), [contributor], phases)
    assert "intake" in workflows
    intake = workflows["intake"]
    edges = {(f, t) for (f, t, _w, _et, _p) in map(edge_parts, intake.edges)}
    assert ("interview", "frontier") in edges
    assert ("frontier", "interview") in edges
    assert ("frontier", "barrier") in edges
    assert ("barrier", "plan") in edges
    assert ("plan", "close") in edges

    assert registry.validate_workflow(intake, phases) == []

def _write_frontier(root, text):
    p = planner_plugin.frontier_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p

def test_frontier_open_when_any_unanswered(tmp_path):
    _write_frontier(tmp_path,
                    "# Decision frontier\n\n- [ ] a?\n- [x] b\n- [ ] c?\n")
    ev = planner_plugin._run_frontier(tmp_path, None, None)
    assert ev["facts"]["frontier"] == "open"
    assert ev["facts"]["open"] == 2

def test_frontier_clear_when_all_answered(tmp_path):
    _write_frontier(tmp_path, "# Decision frontier\n\n- [x] a\n- [X] b\n")
    ev = planner_plugin._run_frontier(tmp_path, None, None)
    assert ev["facts"]["frontier"] == "clear"
    assert ev["facts"]["open"] == 0

def test_frontier_missing_file_reads_open_never_clear(tmp_path):

    ev = planner_plugin._run_frontier(tmp_path, None, None)
    assert ev["facts"]["frontier"] == "open"
    assert ev["facts"]["open"] == 0

def test_frontier_itemless_file_reads_open_never_clear(tmp_path):
    _write_frontier(tmp_path, "# Decision frontier\n\njust prose, no items.\n")
    ev = planner_plugin._run_frontier(tmp_path, None, None)
    assert ev["facts"]["frontier"] == "open"
    assert ev["facts"]["open"] == 0

class _Capture:

    def __init__(self):
        self.seen = []

    def run(self, unit, composed):
        self.seen.append(composed.get("phase"))
        return R.Receipt(outcome="result",
                         evidence={"produces": f"art-{len(self.seen)}"})

def _intake(tmp_path):
    contributor = _planner(tmp_path)
    return registry.resolve_workflows(
        str(tmp_path), [contributor])["intake"]

def test_walk_interview_always_advances_to_frontier(tmp_path):
    wf = _intake(tmp_path)
    nxt = _choose_edge(wf, "interview", passed=True)
    assert nxt is not None and nxt[0] == "frontier"

def test_walk_frontier_open_loops_back_to_interview(tmp_path):
    wf = _intake(tmp_path)
    nxt = _choose_edge(wf, "frontier", passed=True,
                       evidence={"facts": {"frontier": "open"}})
    assert nxt is not None and nxt[0] == "interview"

def test_walk_frontier_clear_advances_through_barrier_plan_to_close(tmp_path):
    wf = _intake(tmp_path)
    step = _choose_edge(wf, "frontier", passed=True,
                        evidence={"facts": {"frontier": "clear"}})
    assert step is not None and step[0] == "barrier"
    step = _choose_edge(wf, "barrier", passed=True)
    assert step is not None and step[0] == "plan"
    step = _choose_edge(wf, "plan", passed=True)
    assert step is not None and step[0] == "close"

def test_walk_end_to_end_cleared_frontier_reaches_close(tmp_path):
    _write_frontier(tmp_path, "# Decision frontier\n\n- [x] settled\n")
    wf = _intake(tmp_path)
    from workflow_run import run_workflow
    from situation import Situation
    sit = Situation(task_kind="create", intent="intake", subject="process",
                    phase="none", root=str(tmp_path))
    out = run_workflow(tmp_path, R.Unit("u1", sit), wf, [_planner(tmp_path)],
                       _Capture())
    assert out["phases"] == ["interview", "frontier", "barrier", "plan", "close"]

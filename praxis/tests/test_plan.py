#!/usr/bin/env python3
"""Tests for the tasklist intake + planning head (plan.py): deterministic assembly, the planner
seam (passthrough / inline-interview / spawned), the recorded plan/pause, and the head-to-tail
`plan_and_run` that sets a DAG cascading through run_dag."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import journal  # noqa: E402
import plan as plan_mod  # noqa: E402
from plan import (CallablePlanner, PassthroughPlanner, PlanOutcome, SubprocessPlanner, TaskSpec,
                  build_units, plan_and_run, plan_tasks, reconstruct_units, spec_to_unit)  # noqa: E402
from providers import NullProvider  # noqa: E402
from run import InlineExecutor, Receipt, Unit  # noqa: E402


class TempRoot:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".praxis").mkdir()
        return self.root

    def __exit__(self, *a):
        self._tmp.cleanup()


class DeterministicAssemblyTest(unittest.TestCase):
    def test_spec_to_unit_projects_features(self):
        u = spec_to_unit(TaskSpec(intent="add a button", id="t1", subject="design",
                                  suggested_kind="style", fit="loose"), root=Path("/x"))
        self.assertEqual(u.id, "t1")
        self.assertEqual(u.situation.subject, "design")
        self.assertEqual(u.situation.suggested_kind, "style")
        self.assertEqual(u.situation.fit, "loose")
        self.assertEqual(u.situation.root, "/x")

    def test_build_units_generates_ids_and_preserves_edges(self):
        specs = [TaskSpec(intent="scaffold"), TaskSpec(intent="wire", depends_on=[])]
        specs[1].id = "b"
        units = build_units(specs)
        self.assertTrue(units[0].id)                 # generated
        self.assertEqual(units[1].id, "b")           # declared kept
        # a declared edge is preserved onto the Unit
        specs2 = [TaskSpec(intent="a", id="a"), TaskSpec(intent="b", id="b", depends_on=["a"])]
        u = build_units(specs2)
        self.assertEqual(u[1].depends_on, ["a"])

    def test_build_units_rejects_duplicate_id(self):
        with self.assertRaises(ValueError):
            build_units([TaskSpec(intent="a", id="x"), TaskSpec(intent="b", id="x")])

    def test_build_units_rejects_dangling_dependency(self):
        with self.assertRaises(ValueError):
            build_units([TaskSpec(intent="a", id="a", depends_on=["ghost"])])

    def test_taskspec_validates_closed_vocab(self):
        with self.assertRaises(ValueError):
            TaskSpec(intent="x", subject="bogus")


class PlannerSeamTest(unittest.TestCase):
    def test_passthrough_is_ready_from_declared_specs(self):
        with TempRoot() as root:
            out = PassthroughPlanner().plan([TaskSpec(intent="a", id="a")], root)
            self.assertEqual(out.status, "ready")
            self.assertEqual(out.units[0].id, "a")

    def test_callable_planner_can_pause_to_interview(self):
        with TempRoot() as root:
            planner = CallablePlanner(lambda specs, r: {"status": "questions",
                                                        "questions": ["which framework?"]})
            out = planner.plan([TaskSpec(intent="build ui")], root)
            self.assertEqual(out.status, "questions")
            self.assertEqual(out.questions, ["which framework?"])

    def test_callable_planner_can_decompose_into_a_dag(self):
        with TempRoot() as root:
            def handler(specs, r):
                return {"status": "ready", "units": [
                    {"intent": "schema", "id": "s"},
                    {"intent": "api", "id": "api", "depends_on": ["s"]},
                ]}
            out = CallablePlanner(handler).plan([TaskSpec(intent="feature")], root)
            self.assertEqual(out.status, "ready")
            self.assertEqual([u.id for u in out.units], ["s", "api"])
            self.assertEqual(out.units[1].depends_on, ["s"])

    def test_subprocess_planner_failure_pauses_not_crashes(self):
        with TempRoot() as root:
            planner = SubprocessPlanner(lambda specs, r: ["false"])  # nonzero exit
            out = planner.plan([TaskSpec(intent="x")], root)
            self.assertEqual(out.status, "questions")
            self.assertEqual(out.note, "planner-failure")

    def test_subprocess_planner_parses_a_plan(self):
        with TempRoot() as root:
            payload = '{"status":"ready","units":[{"intent":"a","id":"a"}]}'
            planner = SubprocessPlanner(lambda specs, r: ["printf", "%s", payload])
            out = planner.plan([TaskSpec(intent="x")], root)
            self.assertEqual(out.status, "ready")
            self.assertEqual(out.units[0].id, "a")


class PlanTasksRecordingTest(unittest.TestCase):
    def test_ready_plan_is_recorded_with_units_and_edges(self):
        with TempRoot() as root:
            specs = [TaskSpec(intent="a", id="a"), TaskSpec(intent="b", id="b", depends_on=["a"])]
            plan_tasks(root, specs)
            ev = [e for e in journal.read(root) if e["event"] == "conductor.plan"]
            self.assertEqual(len(ev), 1)
            self.assertEqual(ev[0]["status"], "ready")
            self.assertEqual(ev[0]["units"], ["a", "b"])
            self.assertIn(["a", "b"], ev[0]["edges"])

    def test_questions_plan_records_a_pause(self):
        with TempRoot() as root:
            planner = CallablePlanner(lambda specs, r: PlanOutcome(status="questions",
                                                                   questions=["scope?"]))
            plan_tasks(root, [TaskSpec(intent="x")], planner)
            ev = [e for e in journal.read(root) if e["event"] == "conductor.plan"]
            self.assertEqual(ev[0]["status"], "questions-pending")
            self.assertEqual(ev[0]["questions"], ["scope?"])


class ReconstructTest(unittest.TestCase):
    def test_reconstruct_units_from_journal(self):
        with TempRoot() as root:
            specs = [TaskSpec(intent="a", id="a", subject="design"),
                     TaskSpec(intent="b", id="b", depends_on=["a"])]
            plan_tasks(root, specs)
            units = reconstruct_units(root)
            self.assertEqual([u.id for u in units], ["a", "b"])
            self.assertEqual(units[0].situation.subject, "design")
            self.assertEqual(units[1].depends_on, ["a"])

    def test_reconstruct_none_when_no_plan(self):
        with TempRoot() as root:
            self.assertIsNone(reconstruct_units(root))


class PlanAndRunTest(unittest.TestCase):
    def test_questions_pause_runs_nothing(self):
        with TempRoot() as root:
            ran = []
            executor = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            planner = CallablePlanner(lambda specs, r: {"status": "questions",
                                                        "questions": ["confirm target?"]})
            out = plan_and_run(root, [TaskSpec(intent="x")], NullProvider(), executor,
                               planner=planner)
            self.assertEqual(out["status"], "questions")
            self.assertEqual(ran, [])                       # nothing dispatched
            # no unit lifecycle events were written
            self.assertFalse([e for e in journal.read(root) if e["event"] == "unit.proposed"])

    def test_tasklist_cascades_through_run_dag_in_dependency_order(self):
        with TempRoot() as root:
            order = []

            def handler(unit, composed):
                order.append(unit.id)
                return Receipt(outcome="result")

            executor = InlineExecutor(handler)
            specs = [TaskSpec(intent="schema", id="s"),
                     TaskSpec(intent="api", id="api", depends_on=["s"]),
                     TaskSpec(intent="ui", id="ui", depends_on=["api"])]
            out = plan_and_run(root, specs, NullProvider(), executor, concurrency=1)
            self.assertEqual(out["status"], "ran")
            self.assertEqual(order, ["s", "api", "ui"])     # topological
            self.assertEqual([r["outcome"] for r in out["results"]], ["result", "result", "result"])
            # the whole run is a fold: every unit reached done
            fold = journal.fold(root)
            self.assertTrue(all(fold["units"][u]["state"] == "done" for u in ["s", "api", "ui"]))

    def test_blocked_dependency_cascades(self):
        with TempRoot() as root:
            def handler(unit, composed):
                if unit.id == "s":
                    return Receipt(outcome="stall", status="blocked", surfaced=["cannot"])
                return Receipt(outcome="result")

            executor = InlineExecutor(handler)
            specs = [TaskSpec(intent="schema", id="s"),
                     TaskSpec(intent="api", id="api", depends_on=["s"])]
            out = plan_and_run(root, specs, NullProvider(), executor, concurrency=1)
            outcomes = {r["unit"]: r["outcome"] for r in out["results"]}
            self.assertEqual(outcomes["s"], "stall")
            self.assertEqual(outcomes["api"], "stall")      # blocked by its dep, cascaded


if __name__ == "__main__":
    unittest.main()

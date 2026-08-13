#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import journal  # noqa: E402
from plan import (TaskSpec, build_units, plan_tasks, reconstruct_units,
                  spec_to_unit)  # noqa: E402

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
        self.assertTrue(units[0].id)
        self.assertEqual(units[1].id, "b")
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

class PlanTasksRecordingTest(unittest.TestCase):
    def test_ready_plan_is_recorded_with_units_and_edges(self):
        with TempRoot() as root:
            specs = [TaskSpec(intent="a", id="a"), TaskSpec(intent="b", id="b", depends_on=["a"])]
            units = plan_tasks(root, specs)
            self.assertEqual([u.id for u in units], ["a", "b"])
            ev = [e for e in journal.read(root) if e["event"] == "conductor.plan"]
            self.assertEqual(len(ev), 1)
            self.assertEqual(ev[0]["status"], "ready")
            self.assertEqual(ev[0]["units"], ["a", "b"])
            self.assertIn(["a", "b"], ev[0]["edges"])

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

if __name__ == "__main__":
    unittest.main()

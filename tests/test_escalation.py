#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conduct as conduct_engine  # noqa: E402
import journal  # noqa: E402

class EscalationTerminalTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_escalate_journals_unit_escalated_with_reason(self):
        out = conduct_engine.escalate_unit(self.root, "u1", reason="needs a human decision")
        self.assertEqual(out["status"], "escalated")
        self.assertEqual(out["unit"], "u1")
        evs = self._events("unit.escalated")
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["reason"], "needs a human decision")

        self.assertEqual(journal.state_of(self.root, "u1"), "escalated")
        self.assertIn("escalated", journal.CONCLUDED)

    def test_close_unit_rejected_on_escalated(self):
        conduct_engine.escalate_unit(self.root, "u1", reason="exhausted fix loop")
        out = conduct_engine.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "blocked")
        self.assertTrue(out.get("escalated"))
        self.assertIn("exhausted", out["reason"])
        self.assertFalse(self._events("unit.done"))

    def test_record_receipt_result_rejected_on_escalated(self):
        conduct_engine.escalate_unit(self.root, "u1", reason="needs human")
        out = conduct_engine.record_receipt(self.root, "u1", outcome="result")
        self.assertEqual(out["status"], "blocked")
        self.assertTrue(out.get("escalated"))
        self.assertFalse(self._events("unit.done"))

    def test_stall_still_retryable_and_not_escalated(self):
        out = conduct_engine.record_receipt(self.root, "u2", outcome="stall", note="dep missing")
        self.assertEqual(out["status"], "recorded")
        self.assertEqual(out["outcome"], "stall")
        self.assertEqual(journal.state_of(self.root, "u2"), "stalled")

        self.assertFalse(self._events("unit.escalated"))

        out2 = conduct_engine.close_unit(self.root, unit_id="u2")
        self.assertEqual(out2["status"], "closed")

class EscalationBucketTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_status_buckets_escalated_distinct_from_stalled(self):
        tasks = [
            {"intent": "esc unit", "id": "u1"},
            {"intent": "stall unit", "id": "u2"},
            {"intent": "open unit", "id": "u3"},
        ]
        conduct_engine.register_plan(self.root, tasks)
        conduct_engine.escalate_unit(self.root, "u1", reason="needs human")
        conduct_engine.record_receipt(self.root, "u2", outcome="stall", note="blocked on dep")

        prog = conduct_engine.plan_status(self.root)["progress"]
        self.assertIn("escalated", prog)
        self.assertEqual(prog["escalated"], ["u1"])
        self.assertEqual(prog["stalled"], ["u2"])

        self.assertNotIn("u1", prog["stalled"])
        self.assertNotIn("u2", prog["escalated"])
        self.assertEqual(prog["waiting"], ["u3"])

if __name__ == "__main__":
    unittest.main()

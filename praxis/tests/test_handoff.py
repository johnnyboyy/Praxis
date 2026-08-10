#!/usr/bin/env python3
"""Tests for the forward handoff (handoff.py): on-demand assembly, next-ready selection over the
journal, the progress fold, and the gate-backed pull that records payload_read so a self-advancing
agent may edit only after it has pulled."""
import sys
import tempfile
import unittest
from pathlib import Path

# the cannibalized scripts dir first so `gate` is importable, then conductor's dir at index 0 so its
# `handoff` (not any same-named module) wins.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import handoff as handoff_mod  # noqa: E402
import journal  # noqa: E402
from plan import build_units, TaskSpec  # noqa: E402
from providers import NullProvider  # noqa: E402
from situation import Situation  # noqa: E402


class TempRoot:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".praxis").mkdir()
        return self.root

    def __exit__(self, *a):
        self._tmp.cleanup()


def _units():
    return build_units([TaskSpec(intent="schema", id="s"),
                        TaskSpec(intent="api", id="api", depends_on=["s"])])


class AssembleTest(unittest.TestCase):
    def test_assembles_judgment_and_brief(self):
        composed = {"artifacts": [{"body": "principle A"}, {"body": "principle B"}],
                    "domains": ["d1"]}
        ho = handoff_mod.assemble("do the thing", composed)
        self.assertIn("principle A", ho["judgment"])
        self.assertIn("principle B", ho["judgment"])
        self.assertIn("do the thing", ho["brief"])
        self.assertEqual(ho["domains"], ["d1"])

    def test_feedback_is_appended_to_brief(self):
        ho = handoff_mod.assemble("x", {"artifacts": []}, feedback=["missing test"])
        self.assertIn("did not pass verification", ho["brief"])
        self.assertIn("missing test", ho["brief"])


class NextReadyTest(unittest.TestCase):
    def test_leaf_is_ready_dependent_is_not(self):
        with TempRoot() as root:
            units = _units()
            nxt = handoff_mod.next_ready(root, units)
            self.assertEqual(nxt.id, "s")             # api waits on s

    def test_dependent_ready_once_dep_done(self):
        with TempRoot() as root:
            units = _units()
            journal.append(root, "unit.done", unit="s", outcome="result", status="complete")
            nxt = handoff_mod.next_ready(root, units)
            self.assertEqual(nxt.id, "api")

    def test_none_when_dep_stalled(self):
        with TempRoot() as root:
            units = _units()
            journal.append(root, "unit.stalled", unit="s", outcome="stall", status="blocked")
            self.assertIsNone(handoff_mod.next_ready(root, units))


class StatusTest(unittest.TestCase):
    def test_progress_buckets(self):
        with TempRoot() as root:
            units = _units()
            journal.append(root, "unit.done", unit="s", outcome="result", status="complete")
            st = handoff_mod.status(root, units)
            self.assertEqual(st["done"], ["s"])
            self.assertEqual(st["waiting"], ["api"])
            self.assertFalse(st["complete"])


class PullTest(unittest.TestCase):
    def test_pull_delivers_handoff_and_records_read_so_gate_opens(self):
        import gate  # praxis-side edit gate, journal-first
        with TempRoot() as root:
            units = _units()
            out = handoff_mod.pull(root, units, NullProvider())
            self.assertEqual(out["status"], "ready")
            self.assertEqual(out["unit"], "s")
            self.assertIn("schema", out["brief"])
            # the unit is now the open unit, and payload_read was recorded → the gate allows an edit
            self.assertEqual(journal.open_unit(root)["unit"], "s")
            verdict, _ = gate.gate_decision(root, str(root / "schema.py"))
            self.assertEqual(verdict, "allow")

    def test_gate_denies_before_pull(self):
        import gate
        with TempRoot() as root:
            units = _units()
            # frame a spawn-delivery unit WITHOUT a pull/read → gate must deny the edit
            journal.append(root, "unit.proposed", unit="s", unit_of_work="s")
            journal.append(root, "unit.framed", unit="s", unit_of_work="s", delivery="spawn")
            verdict, reason = gate.gate_decision(root, str(root / "schema.py"))
            self.assertEqual(verdict, "deny")
            self.assertIn("payload", reason.lower())

    def test_pull_reports_complete_when_all_done(self):
        with TempRoot() as root:
            units = _units()
            for uid in ("s", "api"):
                journal.append(root, "unit.done", unit=uid, outcome="result", status="complete")
            out = handoff_mod.pull(root, units, NullProvider())
            self.assertEqual(out["status"], "complete")


if __name__ == "__main__":
    unittest.main()

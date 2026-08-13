#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import conduct  # noqa: E402
import handoff as handoff_mod  # noqa: E402
import journal  # noqa: E402
from contributors import Contribution  # noqa: E402
from plan import build_units, plan_tasks, TaskSpec  # noqa: E402
from run import Unit  # noqa: E402
from situation import Situation  # noqa: E402

class _DocsLeaseContributor:
    source = "docs-lease"

    def contribute(self, situation):
        return []

    def surface(self, situation):
        return ["docs/**", "*.md"]

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
    def test_assembles_overlay_and_brief(self):
        composed = {"contributions": [Contribution(source="s", title="A", body="principle A"),
                                      Contribution(source="s", title="B", body="principle B")],
                    "sources": ["s"]}
        ho = handoff_mod.assemble("do the thing", composed)
        self.assertIn("## A\nprinciple A", ho["overlay"])
        self.assertIn("## B\nprinciple B", ho["overlay"])
        self.assertIn("do the thing", ho["brief"])
        self.assertEqual(ho["sources"], ["s"])

    def test_feedback_is_appended_to_brief(self):
        ho = handoff_mod.assemble("x", {"contributions": []}, feedback=["missing test"])
        self.assertIn("did not pass verification", ho["brief"])
        self.assertIn("missing test", ho["brief"])

class NextReadyTest(unittest.TestCase):
    def test_leaf_is_ready_dependent_is_not(self):
        with TempRoot() as root:
            units = _units()
            nxt = handoff_mod.next_ready(root, units)
            self.assertEqual(nxt.id, "s")

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
        import gate
        with TempRoot() as root:
            units = _units()
            out = handoff_mod.pull(root, units, [])
            self.assertEqual(out["status"], "ready")
            self.assertEqual(out["unit"], "s")
            self.assertIn("schema", out["brief"])
            self.assertEqual(journal.open_unit(root)["unit"], "s")
            verdict, _ = gate.gate_decision(root, str(root / "schema.py"))
            self.assertEqual(verdict, "allow")

    def test_gate_denies_before_pull(self):
        import gate
        with TempRoot() as root:
            units = _units()
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
            out = handoff_mod.pull(root, units, [])
            self.assertEqual(out["status"], "complete")

class LeaseSurfaceTest(unittest.TestCase):
    def _unit(self):
        sit = Situation(task_kind="change", intent="edit code", subject="coding",
                        targets=["src/x.py"])
        return Unit(id="u", situation=sit, unit_of_work="u")

    def test_contributor_lease_overrides_targets_and_gate_enforces(self):
        import gate
        with TempRoot() as root:
            out = handoff_mod.pull(root, [self._unit()], [_DocsLeaseContributor()],
                                   delivery="inline")
            self.assertEqual(out["status"], "ready")
            rroot = root.resolve()
            framed = journal.open_unit(rroot)["last"]
            self.assertEqual(framed["surface"], ["*.md", "docs/**"])

            verdict, reason = gate.gate_decision(rroot, str(rroot / "src" / "x.py"))
            self.assertEqual(verdict, "deny")
            self.assertIn("lease surface", reason.lower())

            verdict, _ = gate.gate_decision(rroot, str(rroot / "docs" / "guide.md"))
            self.assertEqual(verdict, "allow")

    def test_fail_open_surface_derives_from_targets(self):
        import gate
        with TempRoot() as root:
            out = handoff_mod.pull(root, [self._unit()], [], delivery="inline")
            self.assertEqual(out["status"], "ready")
            rroot = root.resolve()
            framed = journal.open_unit(rroot)["last"]
            self.assertEqual(framed["surface"], ["src/x.py"])

            verdict, _ = gate.gate_decision(rroot, str(rroot / "src" / "x.py"))
            self.assertEqual(verdict, "allow")
            verdict, _ = gate.gate_decision(rroot, str(rroot / "docs" / "guide.md"))
            self.assertEqual(verdict, "deny")

class ReadHandoffTest(unittest.TestCase):
    def _specs(self):
        return [TaskSpec(intent="schema", id="s"),
                TaskSpec(intent="api", id="api", depends_on=["s"])]

    def test_no_plan(self):
        with TempRoot() as root:
            out = conduct.read_handoff(root, "s")
            self.assertEqual(out["status"], "no-plan")

    def test_unknown_unit(self):
        with TempRoot() as root:
            plan_tasks(root, self._specs())
            out = conduct.read_handoff(root, "nope")
            self.assertEqual(out["status"], "unknown-unit")
            self.assertEqual(out["unit"], "nope")

    def test_read_before_pull_returns_brief_and_surface(self):
        with TempRoot() as root:
            plan_tasks(root, self._specs())
            out = conduct.read_handoff(root, "s")
            self.assertEqual(out["status"], "handoff")
            self.assertEqual(out["unit"], "s")
            self.assertIn("schema", out["brief"])
            self.assertIn("surface", out)

    def test_read_after_pull_matches_pull_brief_and_is_idempotent(self):
        with TempRoot() as root:
            units = plan_tasks(root, self._specs())
            pulled = handoff_mod.pull(root, units, [])
            self.assertEqual(pulled["unit"], "s")
            first = conduct.read_handoff(root, "s")
            second = conduct.read_handoff(root, "s")
            self.assertEqual(first["brief"], pulled["brief"])
            self.assertEqual(first["overlay"], pulled["overlay"])
            self.assertEqual(first["brief"], second["brief"])
            self.assertEqual(first["overlay"], second["overlay"])
            self.assertEqual(first["sources"], second["sources"])
            self.assertEqual(first["surface"], second["surface"])

    def test_read_does_not_advance_state_or_change_next_ready(self):
        with TempRoot() as root:
            units = plan_tasks(root, self._specs())
            # "api" waits on "s"; reading it should not journal anything that
            # would make it look ready/framed and should not change what's next.
            def _state():
                u = journal.fold(root)["units"].get("api")
                return u["state"] if u else None
            before_state = _state()
            conduct.read_handoff(root, "api")
            after_state = _state()
            self.assertEqual(before_state, after_state)
            self.assertIsNone(after_state)
            nxt = handoff_mod.next_ready(root, units)
            self.assertEqual(nxt.id, "s")

    def test_payload_read_note_is_journaled(self):
        with TempRoot() as root:
            plan_tasks(root, self._specs())
            conduct.read_handoff(root, "s")
            notes = [e for e in journal.read(root)
                    if e.get("event") == "unit.note" and e.get("unit") == "s"
                    and e.get("payload_read")]
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0]["reader"], "read_handoff")

if __name__ == "__main__":
    unittest.main()

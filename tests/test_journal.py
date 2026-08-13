import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402

class JournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_assigns_monotonic_seq_and_ts(self):
        a = journal.append(self.root, "unit.proposed", "u1", label="implement-feature")
        b = journal.append(self.root, "unit.framed", "u1", composition=["testing"])
        self.assertEqual(a["seq"], 0)
        self.assertEqual(b["seq"], 1)
        self.assertIn("ts", a)
        lines = journal.journal_path(self.root).read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["event"], "unit.proposed")

    def test_seq_survives_reopen(self):
        journal.append(self.root, "unit.proposed", "u1")
        seq = journal._next_seq(journal.journal_path(self.root))
        self.assertEqual(seq, 1)

    def test_fold_advances_state_and_merges_payload(self):
        journal.append(self.root, "unit.proposed", "u1", label="fix-bug", workflow="hotfix")
        journal.append(self.root, "unit.framed", "u1", composition=["testing"])
        journal.append(self.root, "unit.dispatched", "u1", executor="spawn")
        u = journal.fold(self.root)["units"]["u1"]
        self.assertEqual(u["state"], "dispatched")
        self.assertEqual(u["events"], 3)
        self.assertEqual(u["workflow"], "hotfix")
        self.assertEqual(u["last"]["composition"], ["testing"])
        self.assertEqual(u["last"]["executor"], "spawn")

    def test_open_unit_reflects_lifecycle(self):
        self.assertIsNone(journal.open_unit(self.root))
        journal.append(self.root, "unit.framed", "u1", label="implement-feature")
        self.assertEqual(journal.open_unit(self.root)["unit"], "u1")
        journal.append(self.root, "unit.receipt", "u1", outcome="result", status="complete")
        self.assertEqual(journal.open_unit(self.root)["unit"], "u1")
        journal.append(self.root, "unit.done", "u1")
        self.assertIsNone(journal.open_unit(self.root))

    def test_stalled_is_concluded_not_open(self):
        journal.append(self.root, "unit.framed", "u1", label="implement-feature")
        journal.append(self.root, "unit.stalled", "u1", status="questions-pending",
                       surfaced="which auth?")
        self.assertIsNone(journal.open_unit(self.root))
        self.assertEqual(journal.state_of(self.root, "u1"), "stalled")

    def test_summary_counts_by_phase_and_workflow(self):
        for uid, out, st in [("u1", "result", "complete"), ("u2", "stall", "questions-pending")]:
            journal.append(self.root, "unit.framed", uid, label="testing", workflow="ship-feature")
            journal.append(self.root, "unit.receipt", uid, outcome=out, status=st,
                           surfaced=("fixtures?" if out == "stall" else None))
        s = journal.fold(self.root)["summary"]
        self.assertEqual(s["by_phase"]["testing"], {"runs": 2, "result": 1, "stall": 1})
        self.assertEqual(s["by_workflow"]["ship-feature"]["runs"], 2)
        self.assertEqual(len(s["recent_stalls"]), 1)
        self.assertEqual(s["recent_stalls"][0]["surfaced"], "fixtures?")

    def test_unknown_event_type_is_preserved_not_crashing(self):
        journal.append(self.root, "unit.framed", "u1", label="x")
        journal.append(self.root, "unit.future_thing", "u1", detail="from a later phase")
        u = journal.fold(self.root)["units"]["u1"]
        self.assertEqual(u["state"], "framed")
        self.assertEqual(u["last"]["detail"], "from a later phase")

    def test_gaps_are_queryable_and_conductor_scoped(self):
        journal.append(self.root, "conductor.gap", vocabulary="task_kind",
                       intent="provision a k8s namespace with quotas", fit="none",
                       note="no verb fits infra provisioning")
        journal.append(self.root, "unit.framed", "u1", label="create")
        g = journal.gaps(self.root)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["vocabulary"], "task_kind")
        self.assertEqual(g[0]["fit"], "none")
        self.assertNotIn(None, journal.fold(self.root)["units"])

    def test_gap_candidates_tally_recurrence_is_the_mint_signal(self):
        for intent in ["spin up a staging namespace", "provision a prod db", "add cluster quotas"]:
            journal.append(self.root, "conductor.gap", vocabulary="task_kind",
                           chosen="change", suggested="provision-infra", fit="loose", intent=intent)
        journal.append(self.root, "conductor.gap", vocabulary="task_kind",
                       chosen="create", suggested="write-runbook", fit="loose", intent="docs")
        cands = journal.gap_candidates(self.root)
        self.assertEqual(cands[0]["suggested"], "provision-infra")
        self.assertEqual(cands[0]["count"], 3)
        self.assertIn("change", cands[0]["chosen_as"])
        self.assertEqual(len(cands[0]["examples"]), 3)
        self.assertEqual(cands[1]["suggested"], "write-runbook")

    def test_corrupt_line_is_skipped(self):
        p = journal.journal_path(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"seq":0,"event":"unit.framed","unit":"u1","label":"x"}\nNOT JSON\n')
        u = journal.fold(self.root)["units"]["u1"]
        self.assertEqual(u["state"], "framed")

if __name__ == "__main__":
    unittest.main()

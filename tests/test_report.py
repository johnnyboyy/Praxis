
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "scripts" / "report.py"
sys.path.insert(0, str(REPO))

import journal  # noqa: E402

def mkroot(base: Path) -> Path:
    (base / ".praxis").mkdir(parents=True, exist_ok=True)
    (base / ".praxis" / "config.json").write_text("{}\n")
    return base

def seed(root: Path) -> None:

    journal.append(root, "unit.proposed", unit="A", label="build-api", workflow="delivery")
    journal.append(root, "unit.framed", unit="A", label="build-api", workflow="delivery")
    journal.append(root, "unit.dispatched", unit="A", label="build-api", workflow="delivery")
    journal.append(root, "unit.receipt", unit="A", label="build-api", workflow="delivery",
                   outcome="result", status="ok")
    journal.append(root, "unit.verified", unit="A", label="build-api", workflow="delivery")
    journal.append(root, "unit.done", unit="A", label="build-api", workflow="delivery")

    journal.append(root, "unit.proposed", unit="B", label="write-docs", workflow="delivery")
    journal.append(root, "unit.framed", unit="B", label="write-docs", workflow="delivery")
    journal.append(root, "unit.receipt", unit="B", label="write-docs", workflow="delivery",
                   outcome="result", status="ok")
    journal.append(root, "unit.done", unit="B", label="write-docs", workflow="delivery")

    journal.append(root, "unit.proposed", unit="C", label="flaky-step", workflow="research")
    journal.append(root, "unit.framed", unit="C", label="flaky-step", workflow="research")
    journal.append(root, "unit.receipt", unit="C", label="flaky-step", workflow="research",
                   outcome="stall", status="blocked")
    journal.append(root, "unit.stalled", unit="C", label="flaky-step", workflow="research")

    journal.append(root, "conductor.gap", suggested="triage", vocabulary="task_kind",
                   chosen="debug", intent="figure out the failure")
    journal.append(root, "conductor.gap", suggested="triage", vocabulary="task_kind",
                   chosen="debug", intent="root-cause the outage")

    journal.note(root, source="conductor", body="remember to revisit the flaky step")

def run_report(root: Path, *args):
    return subprocess.run([sys.executable, str(REPORT), *args, "--root", str(root)],
                          capture_output=True, text=True)

class EmptyRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = mkroot(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_no_journal_is_graceful(self):
        r = run_report(self.root, "summary")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no journal", r.stdout)

    def test_metrics_no_journal_is_graceful(self):
        r = run_report(self.root, "metrics")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no journal", r.stdout)

    def test_journal_no_journal_is_graceful(self):
        r = run_report(self.root, "journal")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no journal", r.stdout)

class SeededRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = mkroot(Path(self.tmp.name))
        seed(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_journal_text_shows_events_and_note(self):
        r = run_report(self.root, "journal", "--limit", "50")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("unit.proposed", r.stdout)
        self.assertIn("note", r.stdout)
        self.assertIn("remember to revisit", r.stdout)

    def test_journal_limit_bounds_output(self):
        r = run_report(self.root, "journal", "--limit", "3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("showing 3 of", r.stdout)

    def test_journal_json_is_parseable(self):
        r = run_report(self.root, "journal", "--limit", "100", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertIsInstance(data, list)
        events = {e.get("event") for e in data}
        self.assertIn("unit.proposed", events)
        self.assertIn("conductor.gap", events)
        self.assertIn("note", events)

    def test_journal_event_filter(self):
        r = run_report(self.root, "journal", "--event", "conductor.gap", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertTrue(data)
        self.assertTrue(all(e.get("event") == "conductor.gap" for e in data))

    def test_journal_unit_filter(self):
        r = run_report(self.root, "journal", "--unit", "A", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertTrue(data)
        self.assertTrue(all(e.get("unit") == "A" for e in data))

    def test_gaps_text_shows_recurring_term_with_count(self):
        r = run_report(self.root, "gaps")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("triage", r.stdout)
        self.assertIn("2", r.stdout)

    def test_gaps_json_candidate_count(self):
        r = run_report(self.root, "gaps", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        cands = data["candidates"]
        triage = [c for c in cands if c["suggested"] == "triage"]
        self.assertEqual(len(triage), 1)
        self.assertGreaterEqual(triage[0]["count"], 2)

    def test_metrics_text_reflects_phases_workflows_and_stall(self):
        r = run_report(self.root, "metrics")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("by phase", r.stdout)
        self.assertIn("by workflow", r.stdout)
        self.assertIn("delivery", r.stdout)
        self.assertIn("build-api", r.stdout)

        self.assertIn("C", r.stdout)
        self.assertIn("stall", r.stdout.lower())

    def test_metrics_json_is_parseable_and_buckets_present(self):
        r = run_report(self.root, "metrics", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["total_units"], 3)
        summary = data["summary"]
        self.assertIn("delivery", summary["by_workflow"])
        self.assertEqual(summary["by_workflow"]["delivery"]["result"], 2)
        self.assertIn("build-api", summary["by_phase"])

        stalls = summary["recent_stalls"]
        self.assertTrue(any(s.get("unit") == "C" for s in stalls))

    def test_summary_default_no_subcommand(self):

        r = subprocess.run([sys.executable, str(REPORT)], cwd=str(self.root),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("praxis report", r.stdout)
        self.assertIn("units:", r.stdout)
        self.assertIn("triage", r.stdout)

    def test_summary_json_high_level_counts(self):
        r = run_report(self.root, "summary", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["total_units"], 3)
        self.assertIn("done", data["state_counts"])
        self.assertEqual(data["state_counts"]["done"], 2)
        self.assertEqual(data["state_counts"]["stalled"], 1)

if __name__ == "__main__":
    unittest.main()

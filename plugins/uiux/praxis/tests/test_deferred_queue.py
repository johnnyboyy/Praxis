"""Tests for deferred_queue — the uiux plugin's non-blocking UI/UX decision queue (moved out of
corpora-core's corpus.py). Run: cd plugins/uiux/praxis && python3 -m unittest discover -s tests"""

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import deferred_queue as dq  # noqa: E402

SCRIPT = SCRIPTS / "deferred_queue.py"


def entry(identifier="empty-state", stance="convergent", status="queued", blocking="no"):
    return textwrap.dedent(f"""\
        decisions:
          - id: {identifier}
            stance: {stance}
            domain: validation-feedback
            question: "Preserve filters or offer reset?"
            context: "Results panel."
            source-workstream: search
            created: 2026-07-14
            blocking: {blocking}
            provisional-treatment: "Preserve filters; no reset yet."
            status: {status}""")


class DeferredQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "corpora").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_config(self, has_ui="yes", state_dir="corpora"):
        (self.tmp / state_dir).mkdir(parents=True, exist_ok=True)
        (self.tmp / state_dir / "config.md").write_text(
            f"# Config\n\n## project-shape\nhas-ui: {has_ui}\n")

    def write_queue(self, body="decisions: []", state_dir="corpora"):
        (self.tmp / state_dir).mkdir(parents=True, exist_ok=True)
        (self.tmp / state_dir / "deferred-decisions.md").write_text(
            "# Deferred decisions\n\n```yaml\n" + textwrap.dedent(body).strip() + "\n```\n")

    def invoke(self, *argv):
        return subprocess.run([sys.executable, str(SCRIPT), *argv, "--root", str(self.tmp)],
                              text=True, capture_output=True, check=False)

    # --- validation (deferred_problems) ---
    def test_valid_queue_passes(self):
        self.write_config(); self.write_queue(entry())
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("PASS", r.stdout)
        self.assertIn("1 open", r.stdout)

    def test_blocking_must_be_no(self):
        self.assertTrue(any("surface blockers" in p
                            for p in dq.deferred_problems(dq.parse_deferred(self._q(entry(blocking="yes"))))))

    def test_missing_fields_flagged(self):
        probs = dq.deferred_problems(dq.parse_deferred(self._q("decisions:\n  - id: incomplete")))
        self.assertTrue(any("missing stance" in p for p in probs))
        self.assertTrue(any("missing provisional-treatment" in p for p in probs))

    def test_invalid_stance_status_date_flagged(self):
        bad = entry(stance="sideways", status="waiting").replace("created: 2026-07-14", "created: today")
        probs = dq.deferred_problems(dq.parse_deferred(self._q(bad)))
        self.assertTrue(any("stance must be" in p for p in probs))
        self.assertTrue(any("status must be" in p for p in probs))
        self.assertTrue(any("created must be YYYY-MM-DD" in p for p in probs))

    def test_duplicate_ids_flagged(self):
        first = entry().strip()
        second = entry().strip().removeprefix("decisions:\n")
        probs = dq.deferred_problems(dq.parse_deferred(self._q(first + "\n" + second)))
        self.assertTrue(any("duplicate id" in p for p in probs))

    def test_resolved_trace_needs_a_resolution(self):
        # The backward spine: a resolved entry is KEPT, but only earns its keep if it records how it
        # was settled — a bare 'resolved' with no resolution is a lint failure, not a removal nag.
        self.write_config(); self.write_queue(entry(status="resolved"))
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing resolution", r.stdout)

    def test_resolve_keeps_the_entry_as_a_trace(self):
        self.write_config(); self.write_queue(entry())
        r = self.invoke("resolve", "--id", "empty-state", "--resolution", "Ratified into validation-feedback.")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        text = (self.tmp / "corpora" / "deferred-decisions.md").read_text()
        self.assertIn("status: resolved", text)
        self.assertIn("Ratified into validation-feedback.", text)
        self.assertIn("empty-state", text)                       # NOT deleted — the trace survives
        # and it now passes lint as a valid resolved trace, listed under --all
        self.assertEqual(self.invoke("lint").returncode, 0)
        self.assertIn("resolved trace (1)", self.invoke("list", "--all").stdout)

    def test_resolve_unknown_id_is_rejected(self):
        self.write_config(); self.write_queue(entry())
        r = self.invoke("resolve", "--id", "nope", "--resolution", "x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no deferred decision with id", r.stderr)

    # --- has-ui gating ---
    def test_non_ui_project_does_not_require_queue(self):
        self.write_config(has_ui="no")
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("no deferred-decision queue needed", r.stdout)

    def test_ui_project_requires_queue(self):
        self.write_config(has_ui="yes")
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 1)
        self.assertIn("has no", r.stderr)

    # --- list grouping ---
    def test_list_groups_by_stance(self):
        self.write_config()
        ux = entry(identifier="ux-choice").strip()
        ui = entry(identifier="ui-choice", stance="divergent").strip().removeprefix("decisions:\n")
        self.write_queue(ux + "\n" + ui)
        r = self.invoke("list")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("divergent (1)", r.stdout)
        self.assertIn("convergent (1)", r.stdout)
        self.assertIn("ui-choice", r.stdout)
        self.assertIn("ux-choice", r.stdout)

    def _q(self, body):
        """Write a queue file and return its path (for direct parse/validate tests)."""
        self.write_queue(body)
        return str(self.tmp / "corpora" / "deferred-decisions.md")

    # --- `.corpora/` (standard) layout, beside the legacy `corpora/` cases above ---

    def test_dot_corpora_valid_queue_passes(self):
        self.write_config(state_dir=".corpora")
        self.write_queue(entry(), state_dir=".corpora")
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("PASS", r.stdout)
        self.assertIn("1 open", r.stdout)

    def test_dot_corpora_ui_project_requires_queue(self):
        self.write_config(has_ui="yes", state_dir=".corpora")
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 1)
        self.assertIn("has no", r.stderr)

    def test_dot_corpora_non_ui_project_does_not_require_queue(self):
        self.write_config(has_ui="no", state_dir=".corpora")
        r = self.invoke("lint")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("no deferred-decision queue needed", r.stdout)


if __name__ == "__main__":
    unittest.main()

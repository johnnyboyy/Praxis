"""Finding 16(c): smoke tests for the corpora shell hooks — the finding-1 class of bug (a hook
calling a subcommand that no longer exists, blocking every session Stop with an argparse error) is
exactly what a one-line "runs clean in a fixture" test catches the day the drift lands.

Both hooks are driven as the harness drives them: as a subprocess with the fixture project as cwd,
asserting a clean exit and (for the Stop hook, whose output the harness parses) empty-or-valid-JSON
output. Cases run with and without `.corpora/config.md`, the state-dir marker the hooks branch on.

session-start.sh IS cleanly drivable (it always exits 0; with a config it prints an informational
banner and runs corpus.py reconciliations that swallow their own errors), so it is covered here
rather than skipped.

Run: python3 -m unittest discover -s corpora/tests
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
STOP_CHECK = SCRIPTS / "stop-check.sh"
SESSION_START = SCRIPTS / "session-start.sh"


def _run(hook: Path, cwd: Path):
    return subprocess.run([str(hook)], cwd=str(cwd), capture_output=True, text=True)


def _assert_empty_or_valid_json(testcase, text: str):
    stripped = text.strip()
    if stripped:
        json.loads(stripped)  # raises if it is neither empty nor valid JSON


class StopCheckSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_exits_clean_without_config(self):
        res = _run(STOP_CHECK, self.tmp)
        self.assertEqual(res.returncode, 0, res.stderr)
        _assert_empty_or_valid_json(self, res.stdout)

    def test_exits_clean_with_config(self):
        (self.tmp / ".corpora").mkdir()
        (self.tmp / ".corpora" / "config.md").write_text("## project-shape\nname: p\n")
        res = _run(STOP_CHECK, self.tmp)
        self.assertEqual(res.returncode, 0, res.stderr)
        _assert_empty_or_valid_json(self, res.stdout)


class SessionStartSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_exits_clean_without_config_and_stays_silent(self):
        res = _run(SESSION_START, self.tmp)
        self.assertEqual(res.returncode, 0, res.stderr)
        # No corpora project here ⇒ the hook must not emit its banner or run reconciliations.
        self.assertEqual(res.stdout.strip(), "")

    def test_exits_clean_with_config(self):
        (self.tmp / ".corpora").mkdir()
        (self.tmp / ".corpora" / "config.md").write_text("## project-shape\nname: p\n")
        res = _run(SESSION_START, self.tmp)
        # Informational hook: it must never block a session, whatever the reconciliations report.
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("praxis front door", res.stdout)


if __name__ == "__main__":
    unittest.main()

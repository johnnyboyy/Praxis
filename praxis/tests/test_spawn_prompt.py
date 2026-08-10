"""Tests for spawn_prompt.py — composing a spawn prompt from pluggable engine parts.

praxis owns the skeleton (stance line + engine parts + task) and the save lifecycle (debug-honoring);
the engine injects its parts + judges composition validity via the `spawn-parts` hook. These use a
GENERIC stub engine (its parts are literal placeholders) — zero real engine. They cover: assembly
order + byte-for-byte part bodies, the composition gate (engine-reported problems stop praxis), the
debug-vs-explicit save policy, and no-engine degrade. Run: python3 -m unittest discover -s praxis/tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
SCRIPTS = PRAXIS / "scripts"
SPAWN = SCRIPTS / "spawn_prompt.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import spawn_prompt  # noqa: E402
from _stub_engine import write_stub, write_plugin_slot, SPAWN_PARTS_CAP  # noqa: E402


def run(*args: str, env=None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=60, env=e)


class SpawnPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # A praxis root (marker only — spawn_prompt reads praxis's own config, not an engine's).
        (self.tmp / "praxis").mkdir(parents=True)
        (self.tmp / "praxis" / "config.md").write_text("name: proj\n")
        self.stub = write_stub(self.tmp)
        # Register the stub in the root's own convention slot so it auto-resolves (no --engine-plugins).
        write_plugin_slot(self.tmp / "praxis" / "engine", self.stub, extra_caps=[SPAWN_PARTS_CAP])
        self.task = self.tmp / "task.md"
        self.task.write_text("Do the work.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra, env=None):
        return run(str(SPAWN), "--from", str(self.tmp), "--stance", "convergent",
                   "--domains", "d1", "--task-file", str(self.task), *extra, env=env)

    def test_assembles_stance_engine_parts_and_task_in_order(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        # praxis frame: stance line on top, task on the bottom
        self.assertTrue(out.startswith("stance: convergent"))
        self.assertIn("## Task\n\nDo the work.", out)
        # engine parts, byte-for-byte, between the frame and in the engine's own order
        self.assertIn("STANCE FRAME", out)
        self.assertIn("### Domain: d1\n\nBODY-D1", out)
        self.assertIn("HANDOFF SCHEMA", out)
        self.assertLess(out.index("STANCE FRAME"), out.index("BODY-D1"))
        self.assertLess(out.index("BODY-D1"), out.index("HANDOFF SCHEMA"))
        self.assertLess(out.index("HANDOFF SCHEMA"), out.index("## Task"))

    def test_composition_problems_gate_the_prompt(self):
        # The engine reports a problem → praxis stops, emits no prompt (owns the gate).
        r = self._run(env={"STUB_PROBLEMS": "mixed subjects in one composition"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("composition gate failed", r.stderr)
        self.assertIn("mixed subjects", r.stderr)
        self.assertNotIn("## Task", r.stdout)

    def test_debug_true_saves_under_praxis_spawn_prompts(self):
        (self.tmp / "praxis" / "config.md").write_text("name: proj\ndebug: yes\n")
        r = self._run("--composition", "coder")
        self.assertEqual(r.returncode, 0, r.stderr)
        written = list((self.tmp / "praxis" / "spawn-prompts").glob("*-coder.md"))
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].read_text().startswith("stance: convergent"))

    def test_no_debug_no_output_saves_nothing(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("debug not enabled", r.stderr)
        self.assertFalse((self.tmp / "praxis" / "spawn-prompts").exists())

    def test_explicit_output_writes_regardless_of_debug(self):
        out = self.tmp / "prompt.md"
        r = self._run("--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out.is_file())

    def test_no_engine_registered_degrades(self):
        # Point at an empty slot: nothing to compose from → praxis reports and stops, no crash.
        empty = self.tmp / "empty-slot"
        empty.mkdir()
        r = self._run("--engine-plugins", str(empty))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no engine registered", r.stderr)

    def test_missing_task_file_is_reported(self):
        r = run(str(SPAWN), "--from", str(self.tmp), "--stance", "convergent",
                "--domains", "d1", "--task-file", str(self.tmp / "nope.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no such task file", r.stderr)


if __name__ == "__main__":
    unittest.main()

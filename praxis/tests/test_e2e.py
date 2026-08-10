"""Baseline end-to-end: a throwaway fixture project, praxis scripts driven as REAL subprocesses,
checking the process artifacts (frame, interop entry, handoff) — the loop a task actually takes.
Composition comes from a GENERIC stub engine registered in an engine plugin slot; no real engine.

Fixture shape (a healthy multi-root project):

    platform/            interop root (name: platform)
      app/               child root (name: app)
      admin/             child root (name: admin)

Run with: python3 -m unittest discover -s praxis/tests -v
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
FRAME = PRAXIS / "scripts" / "frame.py"
ROOT_TREE = PRAXIS / "scripts" / "root_tree.py"
HANDOFF = PRAXIS / "scripts" / "handoff.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stub_engine import write_stub, write_plugin_slot  # noqa: E402


def run(*args: str, env=None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=60, env=e)


def mkroot(base: Path, rel: str, name: str) -> Path:
    d = base / rel
    (d / "praxis").mkdir(parents=True, exist_ok=True)
    (d / "praxis" / "config.md").write_text(f"## project-shape\nname: {name}\n")
    return d


def make_and_validate_handoff(tmp: Path, name: str, unit: str, domains: list[str]) -> subprocess.CompletedProcess:
    t = run(str(HANDOFF), "template", "--unit-of-work", unit, "--workstream", name, "--stance", "convergent")
    filled = t.stdout.replace("domains-loaded: []", f"domains-loaded: [{', '.join(domains) or 'x'}]")
    path = tmp / f"handoff-{name}.md"
    path.write_text(filled)
    return run(str(HANDOFF), "validate", str(path))


class BaselineE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        mkroot(self.tmp, ".", "platform")           # interop root
        mkroot(self.tmp, "app", "app")
        mkroot(self.tmp, "admin", "admin")
        self.stub = write_stub(self.tmp)
        self.slot = write_plugin_slot(self.tmp, self.stub)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_root_task_full_loop(self):
        # frame (root + composition via the registered generic engine) -> handoff -> validate.
        r = run(str(FRAME), "--from", str(self.tmp), "--target", "app/src/x.ts",
                "--unit-of-work", "implement-feature", "--engine-plugins", str(self.slot), "--json",
                env={"STUB_DOMAINS": "coding-general"})
        self.assertEqual(r.returncode, 0, r.stderr)
        f = json.loads(r.stdout)
        self.assertEqual(f["verdict"], "single-root")
        self.assertEqual(f["roots"][0]["name"], "app")
        domains = f["composition"] or []
        self.assertIn("coding-general", domains, f.get("composition_note"))
        v = make_and_validate_handoff(self.tmp, "app", "implement-feature", domains)
        self.assertEqual(v.returncode, 0, v.stdout)

    def test_spanning_task_enters_at_interop_then_hands_off_each_child(self):
        r = run(str(FRAME), "--from", str(self.tmp), "--files", "app/x.ts,admin/y.ts",
                "--unit-of-work", "implement-feature", "--engine-plugins", str(self.slot), "--json")
        f = json.loads(r.stdout)
        self.assertTrue(f["spans_multiple_roots"])
        self.assertEqual(f["verdict"], "decompose")
        self.assertIsNone(f["composition"])                       # never composed as one task
        self.assertEqual(f["interop_root"]["name"], "platform")   # enter at the parent

        for child_file, child_name in (("app/x.ts", "app"), ("admin/y.ts", "admin")):
            cr = run(str(FRAME), "--from", str(self.tmp), "--target", child_file,
                     "--unit-of-work", "implement-feature", "--engine-plugins", str(self.slot), "--json",
                     env={"STUB_DOMAINS": "coding-general"})
            cf = json.loads(cr.stdout)
            self.assertEqual(cf["verdict"], "single-root")
            self.assertEqual(cf["roots"][0]["name"], child_name)   # each piece in its own context
            v = make_and_validate_handoff(self.tmp, child_name, "implement-feature", cf["composition"] or [])
            self.assertEqual(v.returncode, 0, v.stdout)            # each child produces a valid handoff

    def test_spanning_with_no_interop_parent_is_a_hard_stop(self):
        # Remove the platform root's marker so the two children have no common-ancestor root.
        (self.tmp / "praxis" / "config.md").unlink()
        r = run(str(ROOT_TREE), "interop", "--from", str(self.tmp), "--files", "app/x.ts,admin/y.ts")
        self.assertEqual(r.returncode, 1)                          # cannot proceed
        self.assertIn("NO interop root", r.stdout)
        self.assertIn("define one", r.stdout)

    def test_incomplete_handoff_is_rejected(self):
        path = self.tmp / "bad.md"
        path.write_text("---\nunit-of-work: x\nstance: none\n---\n\n## Artifact\na\n")
        v = run(str(HANDOFF), "validate", str(path))
        self.assertEqual(v.returncode, 1)
        self.assertIn("missing", v.stdout)


if __name__ == "__main__":
    unittest.main()

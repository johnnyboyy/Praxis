"""Tests for frame_store — the persisted frame trace (framing Stage 3, the backward spine's first
vertebra). Covers: render/parse round-trip, append-not-overwrite (a re-frame lands beside the old),
and the CLI write/show a fresh spawn reads. Run: python3 -m unittest discover -s praxis/tests"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import frame_store as fs  # noqa: E402


def frame(uow="implement-feature", root="app", floor="by-judgment", verdict="single-root",
          comp=None, assumptions=None):
    return {
        "unit_of_work": uow,
        "roots": [{"name": root, "path": f"/x/{root}"}],
        "verdict": verdict,
        "size_floor": floor,
        "composition": comp if comp is not None else [],
        "assumptions": assumptions if assumptions is not None else [f"governing root: {root}",
                                                                     f"unit-of-work: {uow}"],
    }


class FrameStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_then_parse_round_trips(self):
        entries = [fs.frame_entry(frame(comp=["a", "b"], assumptions=["x", "y"]))]
        text = fs.render_frames("ws-1", entries)
        p = self.root / "praxis" / "frames" / "ws-1.md"
        p.parent.mkdir(parents=True)
        p.write_text(text)
        ws, got = fs.parse_frames(p)
        self.assertEqual(ws, "ws-1")
        self.assertEqual(got[0]["unit-of-work"], "implement-feature")
        self.assertEqual(got[0]["composition"], ["a", "b"])
        self.assertEqual(got[0]["assumptions"], ["x", "y"])

    def test_append_leaves_the_prior_frame_beside_the_new(self):
        # A redirect: re-frame the same workstream; the old frame stays as the trace.
        fs.append_frame(self.root, "ws-1", frame(uow="implement-feature"))
        fs.append_frame(self.root, "ws-1", frame(uow="fix-bug"))          # the redirect
        _, entries = fs.parse_frames(fs.frame_path(self.root, "ws-1"))
        self.assertEqual([e["unit-of-work"] for e in entries], ["implement-feature", "fix-bug"])

    def test_cli_write_then_show(self):
        import subprocess
        (self.root / "praxis" / "config.md").write_text("name: app\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "x.ts").write_text("x")
        w = subprocess.run([sys.executable, str(SCRIPTS / "frame_store.py"), "write",
                            "--root", str(self.root), "--workstream", "w", "--unit-of-work",
                            "implement-feature", "--target", "src/x.ts"],
                           text=True, capture_output=True)
        self.assertEqual(w.returncode, 0, w.stderr)
        s = subprocess.run([sys.executable, str(SCRIPTS / "frame_store.py"), "show",
                            "--root", str(self.root), "--workstream", "w"],
                           text=True, capture_output=True)
        self.assertEqual(s.returncode, 0, s.stderr)
        self.assertIn("unit-of-work: implement-feature", s.stdout)
        self.assertIn("workstream: w", s.stdout)

    def test_show_missing_is_reported(self):
        import subprocess
        s = subprocess.run([sys.executable, str(SCRIPTS / "frame_store.py"), "show",
                            "--root", str(self.root), "--workstream", "nope"],
                           text=True, capture_output=True)
        self.assertEqual(s.returncode, 1)
        self.assertIn("no frame trace", s.stdout)


if __name__ == "__main__":
    unittest.main()

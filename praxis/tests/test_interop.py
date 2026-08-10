"""Tests for interop_root. Run with: python3 -m unittest discover -s praxis/tests -v"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import root_tree as rt  # noqa: E402


def mkroot(base: Path, rel: str, name: str | None = None) -> Path:
    d = base / rel
    (d / "praxis").mkdir(parents=True, exist_ok=True)
    (d / "praxis" / "config.md").write_text("## project-shape\n" + (f"name: {name}\n" if name else ""))
    return d


class InteropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_root_does_not_span(self):
        mkroot(self.tmp, "app", name="app")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        info = rt.interop_root([self.tmp / "app/src/x.ts", self.tmp / "app/src/y.ts"], roots)
        self.assertFalse(info["spans"])
        self.assertEqual(info["entry"], (self.tmp / "app").resolve())

    def test_nested_parent_is_the_entry_root(self):
        # FAMOUS shape: app root contains an admin root. A task touching both enters at the app root.
        mkroot(self.tmp, "app", name="app")
        mkroot(self.tmp, "app/admin", name="admin")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        info = rt.interop_root([self.tmp / "app/src/x.ts", self.tmp / "app/admin/y.ts"], roots)
        self.assertTrue(info["spans"])
        self.assertEqual(info["entry"], (self.tmp / "app").resolve())
        self.assertIsNone(info["define_at"])

    def test_siblings_with_no_parent_have_no_entry_root(self):
        # motors shape: two sibling roots under apps/, nothing above → nowhere to enter.
        mkroot(self.tmp, "apps/a", name="a")
        mkroot(self.tmp, "apps/b", name="b")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        info = rt.interop_root([self.tmp / "apps/a/x.ts", self.tmp / "apps/b/y.ts"], roots)
        self.assertTrue(info["spans"])
        self.assertIsNone(info["entry"])
        self.assertEqual(Path(info["define_at"]), (self.tmp / "apps").resolve())

    def test_defined_interop_parent_becomes_the_entry_root(self):
        # Add a real interop root above the two siblings → it becomes the entry point, gap resolved.
        mkroot(self.tmp, "apps", name="interop")
        mkroot(self.tmp, "apps/a", name="a")
        mkroot(self.tmp, "apps/b", name="b")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        info = rt.interop_root([self.tmp / "apps/a/x.ts", self.tmp / "apps/b/y.ts"], roots)
        self.assertTrue(info["spans"])
        self.assertEqual(info["entry"], (self.tmp / "apps").resolve())
        self.assertIsNone(info["define_at"])


if __name__ == "__main__":
    unittest.main()

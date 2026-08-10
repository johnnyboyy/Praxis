"""Tests for praxis_init — the root-marker bootstrap. Proves the produced config.md is a real,
root_tree-discoverable root whose debug flag handoff reads. Run: cd praxis && python3 -m unittest discover -s tests"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import praxis_init as pi  # noqa: E402
import root_tree as rt    # noqa: E402
import handoff as ho      # noqa: E402


class PraxisInitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_creates_a_root_tree_discovers(self):
        root = self.tmp / "house"
        pi.init_root(root, name="house", debug=False, force=False)
        config = root / ".praxis" / "config.md"
        self.assertTrue(config.is_file())
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        self.assertIn(root.resolve(), {r.resolve() for r in roots})   # discoverable as a real root

    def test_debug_flag_is_read_by_handoff(self):
        off = self.tmp / "off"
        on = self.tmp / "on"
        pi.init_root(off, name=None, debug=False, force=False)
        pi.init_root(on, name=None, debug=True, force=False)
        self.assertFalse(ho.project_debug(off))
        self.assertTrue(ho.project_debug(on))

    def test_name_recorded(self):
        root = self.tmp / "named"
        pi.init_root(root, name="my-house", debug=False, force=False)
        self.assertIn("my-house", (root / ".praxis" / "config.md").read_text())

    def test_name_is_discoverable_by_root_tree(self):
        # The declared name must be what root_tree.root_name resolves — interop addressing routes by
        # it (addressed-to/return-to). A `# praxis root: NAME` header alone was not discoverable.
        import root_tree as rt
        root = self.tmp / "disc"
        pi.init_root(root, name="checkout", debug=False, force=False)
        self.assertEqual(rt.root_name(root, rt.DEFAULT_MARKERS), "checkout")

    def test_refuses_overwrite_without_force(self):
        root = self.tmp / "r"
        pi.init_root(root, name="a", debug=False, force=False)
        with self.assertRaises(SystemExit):
            pi.init_root(root, name="b", debug=False, force=False)
        # unchanged
        self.assertIn("root: a", (root / ".praxis" / "config.md").read_text())

    def test_force_overwrites(self):
        root = self.tmp / "r"
        pi.init_root(root, name="a", debug=False, force=False)
        pi.init_root(root, name="b", debug=True, force=True)
        text = (root / ".praxis" / "config.md").read_text()
        self.assertIn("root: b", text)
        self.assertTrue(ho.project_debug(root))


if __name__ == "__main__":
    unittest.main()

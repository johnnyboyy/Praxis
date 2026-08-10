"""Tests for root_tree. Run with: python3 -m unittest discover -s praxis/tests -v"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import root_tree as rt  # noqa: E402


def mkroot(base: Path, rel: str, marker: str = "praxis/config.md", name: str | None = None) -> Path:
    """Create a root dir at base/rel with a marker file, optionally carrying a `name:`."""
    d = base / rel
    (d / Path(marker).parent).mkdir(parents=True, exist_ok=True)
    body = "## project-shape\n"
    if name:
        body += f"name: {name}\n"
    (d / marker).write_text(body)
    return d


class RootTreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nesting_makes_parent_child(self):
        mkroot(self.tmp, "app")
        mkroot(self.tmp, "app/admin")
        nodes = rt.build_tree(rt.find_roots(self.tmp, rt.DEFAULT_MARKERS), rt.DEFAULT_MARKERS)
        app = nodes[str((self.tmp / "app").resolve())]
        admin = nodes[str((self.tmp / "app/admin").resolve())]
        self.assertIsNone(app["parent"])
        self.assertEqual(admin["parent"], app["path"])
        self.assertIn(admin["path"], app["children"])

    def test_sibling_roots_flag_missing_interop(self):
        mkroot(self.tmp, "apps/circuit-builder")
        mkroot(self.tmp, "apps/marketing")
        nodes = rt.build_tree(rt.find_roots(self.tmp, rt.DEFAULT_MARKERS), rt.DEFAULT_MARKERS)
        groups = rt.orphan_sibling_groups(nodes)
        self.assertEqual(len(groups), 1)
        self.assertEqual(sorted(groups[0]["members"]), ["circuit-builder", "marketing"])

    def test_a_real_parent_root_suppresses_the_flag(self):
        mkroot(self.tmp, ".", name="interop")
        mkroot(self.tmp, "apps/circuit-builder")
        mkroot(self.tmp, "apps/marketing")
        nodes = rt.build_tree(rt.find_roots(self.tmp, rt.DEFAULT_MARKERS), rt.DEFAULT_MARKERS)
        self.assertEqual(rt.orphan_sibling_groups(nodes), [])

    def test_name_from_config_else_basename(self):
        mkroot(self.tmp, "svc", name="billing")
        mkroot(self.tmp, "other")
        self.assertEqual(rt.root_name((self.tmp / "svc"), rt.DEFAULT_MARKERS), "billing")
        self.assertEqual(rt.root_name((self.tmp / "other"), rt.DEFAULT_MARKERS), "other")

    def test_nearest_root_wins(self):
        mkroot(self.tmp, "app")
        mkroot(self.tmp, "app/admin")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        self.assertEqual(rt.nearest_root(self.tmp / "app/admin/src/x.ts", roots),
                         (self.tmp / "app/admin").resolve())
        self.assertEqual(rt.nearest_root(self.tmp / "app/src/y.ts", roots),
                         (self.tmp / "app").resolve())

    def test_multiple_markers_are_recognized_generically(self):
        # The marker set is data: praxis's own plus any extra a project supplies (e.g. an engine's).
        markers = ["praxis/config.md", "engine/config.md"]
        mkroot(self.tmp, "a", marker="praxis/config.md")
        mkroot(self.tmp, "b", marker="engine/config.md")
        roots = rt.find_roots(self.tmp, markers)
        owners = {rt.root_name(r, markers): rt.which_marker(r, markers) for r in roots}
        self.assertEqual(owners, {"a": "praxis", "b": "engine"})

    def test_node_modules_pruned(self):
        mkroot(self.tmp, "app")
        mkroot(self.tmp, "app/node_modules/somepkg")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        self.assertEqual([r.name for r in roots], ["app"])


if __name__ == "__main__":
    unittest.main()


class PraxisDirTests(unittest.TestCase):
    """`.praxis/` is the standard marker dir; bare `praxis/` stays recognized for existing roots."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _mk(self, rel):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("name: t\n")

    def test_dotted_marker_resolves(self):
        self._mk(".praxis/config.md")
        self.assertEqual(rt.praxis_dir(self.tmp), self.tmp / ".praxis")

    def test_legacy_marker_resolves(self):
        self._mk("praxis/config.md")
        self.assertEqual(rt.praxis_dir(self.tmp), self.tmp / "praxis")

    def test_dotted_wins_when_both_exist(self):
        self._mk(".praxis/config.md")
        self._mk("praxis/config.md")
        self.assertEqual(rt.praxis_dir(self.tmp), self.tmp / ".praxis")

    def test_uninitialized_dir_lands_on_dotted(self):
        self.assertEqual(rt.praxis_dir(self.tmp), self.tmp / ".praxis")

    def test_find_roots_discovers_dotted_root(self):
        self._mk("proj/.praxis/config.md")
        roots = rt.find_roots(self.tmp, rt.DEFAULT_MARKERS)
        self.assertIn(self.tmp / "proj", roots)
        self.assertEqual(rt.which_marker(self.tmp / "proj", rt.DEFAULT_MARKERS), ".praxis")


class GoverningRootAboveTests(unittest.TestCase):
    """The upward walk: nearest ancestor of a path carrying a marker, `.praxis` then legacy `praxis`.
    Unlike nearest_root(path, find_roots(base)), it escapes any search base — an O(depth) answer."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _mk(self, rel):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("name: t\n")

    def test_found_at_depth(self):
        self._mk("proj/.praxis/config.md")
        (self.tmp / "proj" / "src" / "deep").mkdir(parents=True)
        self.assertEqual(rt.governing_root_above(self.tmp / "proj" / "src" / "deep" / "x.ts"),
                         self.tmp / "proj")

    def test_found_at_path_itself(self):
        self._mk("proj/.praxis/config.md")
        self.assertEqual(rt.governing_root_above(self.tmp / "proj"), self.tmp / "proj")

    def test_none_when_no_ancestor_is_a_root(self):
        (self.tmp / "loose").mkdir()
        self.assertIsNone(rt.governing_root_above(self.tmp / "loose" / "x.ts"))

    def test_dotted_recognized_beside_legacy_on_the_same_dir(self):
        self._mk("proj/.praxis/config.md")
        self._mk("proj/praxis/config.md")
        self.assertEqual(rt.governing_root_above(self.tmp / "proj" / "x.ts"), self.tmp / "proj")

    def test_stops_at_nearest_when_nested_roots_exist(self):
        self._mk("outer/.praxis/config.md")
        self._mk("outer/inner/.praxis/config.md")
        self.assertEqual(rt.governing_root_above(self.tmp / "outer" / "inner" / "src" / "x.ts"),
                         self.tmp / "outer" / "inner")

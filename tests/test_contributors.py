import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import contributors as cb  # noqa: E402
import journal  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class _StubContributor:
    def __init__(self, source, title, body, priority=0):
        self._c = cb.Contribution(source=source, title=title, body=body, priority=priority)

    def contribute(self, situation):
        return [self._c]


class ContributorsForTest(unittest.TestCase):
    def test_defaults_to_empty(self):
        self.assertEqual(cb.contributors_for("/any/root"), [])

    def test_config_declared_contributor_loads_and_contributes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            modroot = root / "plugindir"
            modroot.mkdir()
            (modroot / "fake_contrib.py").write_text(textwrap.dedent("""
                class _C:
                    source = "fake"
                    def contribute(self, situation):
                        from contributors import Contribution
                        return [Contribution(source="fake", title="T", body="B")]
                def make(root):
                    return _C()
            """))
            config.write(root, "contributors", {"fake": "fake_contrib:make"})
            sys.path.insert(0, str(modroot))
            try:
                got = cb.contributors_for(root)
                self.assertEqual(len(got), 1)
                contribs = got[0].contribute(_sit())
                self.assertEqual([c.title for c in contribs], ["T"])
            finally:
                sys.path.remove(str(modroot))
                sys.modules.pop("fake_contrib", None)

    def test_bad_spec_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config.write(root, "contributors", {"broken": "no_such_module:make"})
            self.assertEqual(cb.contributors_for(root), [])


class ValidateContributorTest(unittest.TestCase):
    def test_conforming_stub_has_no_problems(self):
        class _OK:
            source = "s"
            def contribute(self, situation):
                return []
        self.assertEqual(cb.validate_contributor(_OK()), [])

    def test_missing_contribute_is_problem(self):
        class _NoContribute:
            source = "s"
        self.assertTrue(cb.validate_contributor(_NoContribute()))

    def test_non_callable_hooks_is_problem(self):
        class _BadHooks:
            source = "s"
            hooks = "not callable"
            def contribute(self, situation):
                return []
        self.assertTrue(cb.validate_contributor(_BadHooks()))


class GatherEmptyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_contributors_yields_empty_overlay(self):
        r = cb.gather([], _sit(fit="clean", suggested_kind="change"), root=self.root)
        self.assertEqual(r["contributions"], [])
        self.assertEqual(r["sources"], [])
        self.assertFalse(r["gap_surfaced"])
        self.assertEqual(journal.gaps(self.root), [])

    def test_loose_fit_surfaces_gap(self):
        r = cb.gather([], _sit(fit="loose", suggested_kind="refactor"), root=self.root)
        self.assertTrue(r["gap_surfaced"])
        self.assertEqual(len(journal.gaps(self.root)), 1)

    def test_none_fit_surfaces_and_routes_unclassified(self):
        r = cb.gather([], _sit(fit="none", suggested_kind="migrate"), root=self.root)
        self.assertTrue(r["gap_surfaced"])
        self.assertEqual(r["routed_kind"], "unclassified")

    def test_no_root_records_nothing_but_reflects_routing(self):
        r = cb.gather([], _sit(fit="none", suggested_kind="migrate"), root=None)
        self.assertFalse(r["gap_surfaced"])
        self.assertEqual(r["routed_kind"], "unclassified")


class GatherComposeTest(unittest.TestCase):
    def test_composes_and_orders_by_priority(self):
        contribs = [_StubContributor("b", "B", "body b", priority=5),
                    _StubContributor("a", "A", "body a", priority=1)]
        r = cb.gather(contribs, _sit(fit="clean"))
        self.assertEqual(r["sources"], ["a", "b"])
        self.assertEqual([c.title for c in r["contributions"]], ["A", "B"])

    def test_stable_within_priority(self):
        contribs = [_StubContributor("first", "F", "x", priority=0),
                    _StubContributor("second", "S", "y", priority=0)]
        r = cb.gather(contribs, _sit(fit="clean"))
        self.assertEqual(r["sources"], ["first", "second"])

    def test_stance_derived_from_phase(self):
        self.assertEqual(cb.gather([], _sit(phase="divergent"))["stance"], "divergent")
        self.assertIsNone(cb.gather([], _sit(phase="none"))["stance"])


if __name__ == "__main__":
    unittest.main()

"""Tests for plugin_registry — the helpers behind :register-plugins, plus the Part-1
contributors.py `plugins_path` -> sys.path enablement.

Run with: python3 -m pytest praxis/tests/test_plugin_registry.py -q
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import plugin_registry as pr  # noqa: E402
import config  # noqa: E402
import contributors as cb  # noqa: E402

PLUGINS_ROOT = str(ROOT / "plugins")


# A minimal, self-contained markered plugin main module (marker + source + make).
MARKERED_TMPL = textwrap.dedent('''
    PRAXIS_PLUGIN = True

    class _C:
        source = "{name}"
        def contribute(self, situation):
            return []

    def make(root):
        return _C()
''')

# Same shape but WITHOUT the marker — must NOT be discovered even when *_plugin.py-named.
UNMARKED_TMPL = textwrap.dedent('''
    class _C:
        source = "{name}"
        def contribute(self, situation):
            return []

    def make(root):
        return _C()
''')


def _write_markered(directory: Path, name: str, filename: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / (filename or f"{name}_plugin.py")
    f.write_text(MARKERED_TMPL.format(name=name))
    return f


def _write_unmarked(directory: Path, name: str, filename: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / (filename or f"{name}_plugin.py")
    f.write_text(UNMARKED_TMPL.format(name=name))
    return f


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        # global_root=None keeps the bundled layer hermetic (no dependence on ~/.claude/plugins).
        self.entries = pr.discover(plugins_root=PLUGINS_ROOT, global_root=None)
        self.by_name = {e["name"]: e for e in self.entries}

    def test_finds_all_known_plugins(self):
        self.assertEqual(
            set(self.by_name),
            {"corpora", "general", "coding-stack", "uiux", "writing", "monorepo"},
        )

    def test_specs_and_dirs(self):
        self.assertEqual(self.by_name["corpora"]["spec"], "corpora.injector:make")
        self.assertEqual(self.by_name["general"]["spec"], "general_plugin:make")
        self.assertEqual(self.by_name["coding-stack"]["spec"], "coding_stack_plugin:make")
        # corpora dir is the package parent so `corpora.injector` imports
        self.assertTrue(self.by_name["corpora"]["dir"].endswith("/corpora"))
        self.assertTrue(self.by_name["uiux"]["dir"].endswith("/uiux"))

    def test_all_bundled_are_origin_bundled(self):
        for e in self.entries:
            self.assertEqual(e["origin"], "bundled")
            self.assertEqual(e["layer"], "bundled")

    def test_descriptions_are_first_sentences(self):
        self.assertIn("compose layer", self.by_name["corpora"]["description"])
        self.assertTrue(self.by_name["general"]["description"].endswith("."))
        for e in self.entries:
            self.assertTrue(e["description"], f"{e['name']} has no description")

    def test_empty_plugins_root_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(pr.discover(plugins_root=d, global_root=None), [])

    def test_missing_plugins_root_is_empty(self):
        self.assertEqual(
            pr.discover(plugins_root="/no/such/plugins/root", global_root=None), []
        )


class MarkerDetectionTest(unittest.TestCase):
    """Discovery is marker-driven, not filename-driven, and static."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_markered_module_is_found(self):
        _write_markered(self.dir, "alpha", filename="alpha_main.py")  # non-*_plugin name
        found = {e["name"]: e for e in pr.discover(plugins_root=self.dir, global_root=None)}
        self.assertIn("alpha", found)
        self.assertEqual(found["alpha"]["spec"], "alpha_main:make")

    def test_unmarkered_module_is_not_found(self):
        _write_unmarked(self.dir, "beta", filename="beta_main.py")
        self.assertEqual(pr.discover(plugins_root=self.dir, global_root=None), [])

    def test_plugin_named_file_without_marker_is_ignored(self):
        # Proves detection is marker- not filename-driven: a *_plugin.py without the marker.
        _write_unmarked(self.dir, "gamma")  # gamma_plugin.py, no PRAXIS_PLUGIN
        self.assertEqual(pr.discover(plugins_root=self.dir, global_root=None), [])


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.discovered = pr.discover(PLUGINS_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_registers_selected_and_writes_plugins_path(self):
        summary = pr.apply(self.root, ["corpora", "general"], self.discovered)
        self.assertEqual(set(summary["added"]), {"corpora", "general"})
        self.assertEqual(summary["removed"], [])
        self.assertEqual(
            config.read(self.root, "contributors"),
            {"corpora": "corpora.injector:make", "general": "general_plugin:make"},
        )
        pp = config.read(self.root).get("plugins_path")
        self.assertEqual(len(pp), 2)
        self.assertTrue(any(d.endswith("/corpora") for d in pp))

    def test_rerun_registers_and_unregisters(self):
        pr.apply(self.root, ["corpora", "general"], self.discovered)
        summary = pr.apply(self.root, ["corpora", "uiux"], self.discovered)
        self.assertEqual(summary["added"], ["uiux"])
        self.assertEqual(summary["removed"], ["general"])
        self.assertEqual(
            set(config.read(self.root, "contributors")), {"corpora", "uiux"}
        )

    def test_idempotent_to_selection(self):
        a = pr.apply(self.root, ["corpora", "general"], self.discovered)
        b = pr.apply(self.root, ["general", "corpora"], self.discovered)
        self.assertEqual(a["contributors"], b["contributors"])
        self.assertEqual(b["added"], [])
        self.assertEqual(b["removed"], [])

    def test_empty_selection_clears_all(self):
        pr.apply(self.root, ["corpora"], self.discovered)
        summary = pr.apply(self.root, [], self.discovered)
        self.assertEqual(summary["removed"], ["corpora"])
        self.assertEqual(config.read(self.root, "contributors"), {})
        self.assertIsNone(config.read(self.root).get("plugins_path"))

    def test_unknown_names_ignored(self):
        summary = pr.apply(self.root, ["corpora", "bogus"], self.discovered)
        self.assertEqual(summary["added"], ["corpora"])

    def test_preserves_other_config_sections(self):
        config.write(self.root, "corpora", {"project_shape": {"language": "python"}})
        pr.apply(self.root, ["general"], self.discovered)
        self.assertEqual(
            config.read(self.root, "corpora"), {"project_shape": {"language": "python"}}
        )

    def test_current_reflects_registration(self):
        self.assertEqual(pr.current(self.root), {})
        pr.apply(self.root, ["general"], self.discovered)
        self.assertEqual(pr.current(self.root), {"general": "general_plugin:make"})


class PluginsPathEnablementTest(unittest.TestCase):
    """Part 1: a dir listed in top-level plugins_path becomes importable by contributors_for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugin_dir = self.root / "external_plugins"
        self.plugin_dir.mkdir()
        (self.plugin_dir / "temp_plugin_xyz.py").write_text(textwrap.dedent("""
            class _C:
                source = "tempxyz"
                def contribute(self, situation):
                    from contributors import Contribution
                    return [Contribution(source="tempxyz", title="T", body="B")]
            def make(root):
                return _C()
        """))

    def tearDown(self):
        self.tmp.cleanup()
        sys.modules.pop("temp_plugin_xyz", None)
        while str(self.plugin_dir) in sys.path:
            sys.path.remove(str(self.plugin_dir))

    def test_plugins_path_makes_module_importable(self):
        # Module dir NOT on sys.path yet; registration provides it via plugins_path.
        self.assertNotIn(str(self.plugin_dir), sys.path)
        config.write(self.root, "contributors", {"tempxyz": "temp_plugin_xyz:make"})
        config.write(self.root, None, {"plugins_path": [str(self.plugin_dir)]})
        loaded = cb.contributors_for(self.root)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].source, "tempxyz")

    def test_absent_plugins_path_is_unchanged_behavior(self):
        # No plugins_path and module not importable -> simply no contributors, no error.
        config.write(self.root, "contributors", {"tempxyz": "temp_plugin_xyz:make"})
        self.assertEqual(cb.contributors_for(self.root), [])


class LayeredDiscoveryTest(unittest.TestCase):
    """bundled < global < project < explicit, unioned by name."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_layer_discovered(self):
        _write_markered(self.root / ".praxis" / "plugins", "projonly")
        found = {e["name"]: e for e in pr.discover(self.root, global_root=None)}
        self.assertIn("projonly", found)
        self.assertEqual(found["projonly"]["origin"], "project")
        # bundled still contributes the six alongside the project plugin.
        self.assertIn("corpora", found)

    def test_explicit_search_path_discovered(self):
        ext = self.root / "elsewhere"
        _write_markered(ext, "extra")
        config.write(self.root, None, {"plugins_search_paths": [str(ext)]})
        found = {e["name"]: e for e in pr.discover(self.root, global_root=None)}
        self.assertIn("extra", found)
        self.assertEqual(found["extra"]["origin"], "explicit")

    def test_global_layer_discovered(self):
        cc = self.root / "cc_plugins"
        # Nested arbitrarily deep, as a CC-packaged praxis plugin might be.
        _write_markered(cc / "vendor" / "widget", "glob1")
        found = {e["name"]: e for e in pr.discover(self.root, global_root=cc)}
        self.assertIn("glob1", found)
        self.assertEqual(found["glob1"]["origin"], "global")

    def test_absent_global_root_is_fail_soft(self):
        # A non-existent global dir must not raise and must add nothing.
        found = pr.discover(plugins_root=str(self.root / "empty"),
                            global_root=str(self.root / "no_such_cc"))
        self.assertEqual(found, [])


class PrecedenceTest(unittest.TestCase):
    """Same name in two layers → the higher-precedence layer wins."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_beats_bundled_lookalike(self):
        # Put a plugin in a fake "bundled" dir AND in the project layer under the same name.
        bundled = self.root / "bundled"
        _write_markered(bundled, "dup")
        proj = self.root / ".praxis" / "plugins"
        _write_markered(proj, "dup")
        found = {e["name"]: e for e in
                 pr.discover(self.root, plugins_root=bundled, global_root=None)}
        self.assertEqual(found["dup"]["origin"], "project")
        self.assertEqual(found["dup"]["dir"], str(proj.resolve()))

    def test_explicit_beats_project(self):
        proj = self.root / ".praxis" / "plugins"
        _write_markered(proj, "dup")
        ext = self.root / "ext"
        _write_markered(ext, "dup")
        config.write(self.root, None, {"plugins_search_paths": [str(ext)]})
        found = {e["name"]: e for e in
                 pr.discover(self.root, plugins_root=str(self.root / "empty"), global_root=None)}
        self.assertEqual(found["dup"]["origin"], "explicit")
        self.assertEqual(found["dup"]["dir"], str(ext.resolve()))

    def test_global_beats_bundled(self):
        bundled = self.root / "bundled"
        _write_markered(bundled, "dup")
        cc = self.root / "cc"
        _write_markered(cc, "dup")
        found = {e["name"]: e for e in
                 pr.discover(plugins_root=bundled, global_root=cc)}
        self.assertEqual(found["dup"]["origin"], "global")
        self.assertEqual(found["dup"]["dir"], str(cc.resolve()))


if __name__ == "__main__":
    unittest.main()

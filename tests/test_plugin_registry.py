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

PLUGINS_ROOT = "/Users/johnzdanis/jdev/skills/praxis-plugins"


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.entries = pr.discover(PLUGINS_ROOT)
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

    def test_descriptions_are_first_sentences(self):
        self.assertIn("compose layer", self.by_name["corpora"]["description"])
        self.assertTrue(self.by_name["general"]["description"].endswith("."))
        for e in self.entries:
            self.assertTrue(e["description"], f"{e['name']} has no description")

    def test_missing_plugins_root_is_empty(self):
        self.assertEqual(pr.discover("/no/such/plugins/root"), [])


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


if __name__ == "__main__":
    unittest.main()

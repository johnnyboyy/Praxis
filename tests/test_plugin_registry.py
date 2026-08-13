
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

MARKERED_TMPL = textwrap.dedent('''
    PRAXIS_PLUGIN = True

    class _C:
        source = "{name}"
        def contribute(self, situation):
            return []

    def make(root):
        return _C()
''')

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

def _write_installed_plugins(global_root: Path, install_paths) -> None:
    manifest = global_root / "plugins" / "installed_plugins.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    plugins = {
        f"pkg{i}@marketplace": [{"scope": "user", "installPath": str(p)}]
        for i, p in enumerate(install_paths)
    }
    manifest.write_text(json.dumps({"version": 2, "plugins": plugins}))

def _link_skill(global_root: Path, name: str, target: Path) -> None:
    skills = global_root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / name).symlink_to(target)

class DiscoverTest(unittest.TestCase):
    def setUp(self):

        self.entries = pr.discover(plugins_root=PLUGINS_ROOT, global_root=None)
        self.by_name = {e["name"]: e for e in self.entries}

    def test_finds_all_known_plugins(self):
        self.assertEqual(
            set(self.by_name),
            {"uiux", "writing", "planner", "rebuild", "coding-process"},
        )

    def test_specs_and_dirs(self):
        self.assertEqual(self.by_name["uiux"]["spec"], "uiux_plugin:make")
        self.assertTrue(self.by_name["uiux"]["dir"].endswith("/uiux"))

    def test_all_bundled_are_origin_bundled(self):
        for e in self.entries:
            self.assertEqual(e["origin"], "bundled")
            self.assertEqual(e["layer"], "bundled")

    def test_descriptions_are_first_sentences(self):
        self.assertIn("intake", self.by_name["planner"]["description"])
        self.assertTrue(self.by_name["uiux"]["description"].endswith("."))
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

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_markered_module_is_found(self):
        _write_markered(self.dir, "alpha", filename="alpha_main.py")
        found = {e["name"]: e for e in pr.discover(plugins_root=self.dir, global_root=None)}
        self.assertIn("alpha", found)
        self.assertEqual(found["alpha"]["spec"], "alpha_main:make")

    def test_unmarkered_module_is_not_found(self):
        _write_unmarked(self.dir, "beta", filename="beta_main.py")
        self.assertEqual(pr.discover(plugins_root=self.dir, global_root=None), [])

    def test_plugin_named_file_without_marker_is_ignored(self):

        _write_unmarked(self.dir, "gamma")
        self.assertEqual(pr.discover(plugins_root=self.dir, global_root=None), [])

class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.discovered = pr.discover(PLUGINS_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_registers_selected_and_writes_plugins_path(self):
        summary = pr.apply(self.root, ["corpora", "writing"], self.discovered)
        self.assertEqual(set(summary["added"]), {"corpora", "writing"})
        self.assertEqual(summary["removed"], [])
        self.assertEqual(
            config.read(self.root, "contributors"),
            {"corpora": "corpora.plugin:make", "writing": "writing_plugin:make"},
        )
        pp = config.read(self.root).get("plugins_path")
        self.assertEqual(len(pp), 2)
        self.assertTrue(any(d.endswith("/corpora") for d in pp))

    def test_rerun_registers_and_unregisters(self):
        pr.apply(self.root, ["corpora", "writing"], self.discovered)
        summary = pr.apply(self.root, ["corpora", "uiux"], self.discovered)
        self.assertEqual(summary["added"], ["uiux"])
        self.assertEqual(summary["removed"], ["writing"])
        self.assertEqual(
            set(config.read(self.root, "contributors")), {"corpora", "uiux"}
        )

    def test_idempotent_to_selection(self):
        a = pr.apply(self.root, ["corpora", "writing"], self.discovered)
        b = pr.apply(self.root, ["writing", "corpora"], self.discovered)
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
        pr.apply(self.root, ["writing"], self.discovered)
        self.assertEqual(
            config.read(self.root, "corpora"), {"project_shape": {"language": "python"}}
        )

    def test_current_reflects_registration(self):
        self.assertEqual(pr.current(self.root), {})
        pr.apply(self.root, ["writing"], self.discovered)
        self.assertEqual(pr.current(self.root), {"writing": "writing_plugin:make"})

    def test_preexisting_non_plugin_source_survives_reregistration(self):
        # A root's corpora scope may point `sources` at entries that are NOT
        # any bundled plugin's domains/ dir (e.g. the peer domains bucket).
        # Re-registering plugins with no domains/ of their own must not wipe
        # those out — only entries whose `dir` matches a discovered plugin's
        # own domains/ dir are refreshed/replaced.
        bucket_source = {"owner": "bucket", "dir": "/some/other/root/domains/uiux"}
        config.write(self.root, "corpora", {"sources": [bucket_source]})
        summary = pr.apply(self.root, ["corpora", "uiux"], self.discovered)
        sources = config.read(self.root, "corpora")["sources"]
        self.assertIn(bucket_source, sources)
        self.assertEqual(summary["corpora_sources"], sources)

class PluginsPathEnablementTest(unittest.TestCase):

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

        self.assertNotIn(str(self.plugin_dir), sys.path)
        config.write(self.root, "contributors", {"tempxyz": "temp_plugin_xyz:make"})
        config.write(self.root, None, {"plugins_path": [str(self.plugin_dir)]})
        loaded = cb.contributors_for(self.root)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].source, "tempxyz")

    def test_absent_plugins_path_is_unchanged_behavior(self):

        config.write(self.root, "contributors", {"tempxyz": "temp_plugin_xyz:make"})
        self.assertEqual(cb.contributors_for(self.root), [])

class LayeredDiscoveryTest(unittest.TestCase):

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

        self.assertIn("uiux", found)

    def test_explicit_search_path_discovered(self):
        ext = self.root / "elsewhere"
        _write_markered(ext, "extra")
        config.write(self.root, None, {"plugins_search_paths": [str(ext)]})
        found = {e["name"]: e for e in pr.discover(self.root, global_root=None)}
        self.assertIn("extra", found)
        self.assertEqual(found["extra"]["origin"], "explicit")

    def test_global_layer_discovered_via_installed_plugins(self):

        gr = self.root / "dot_claude"
        install = self.root / "cache" / "vendor" / "widget" / "1.0.0"
        _write_markered(install, "glob1")
        _write_installed_plugins(gr, [install])
        found = {e["name"]: e for e in pr.discover(self.root, global_root=gr)}
        self.assertIn("glob1", found)
        self.assertEqual(found["glob1"]["origin"], "global")

    def test_global_layer_discovered_via_skills_symlink(self):

        gr = self.root / "dot_claude"
        src = self.root / "elsewhere" / "myplugin"
        _write_markered(src, "glob2")
        _link_skill(gr, "myplugin", src)
        found = {e["name"]: e for e in pr.discover(self.root, global_root=gr)}
        self.assertIn("glob2", found)
        self.assertEqual(found["glob2"]["origin"], "global")

    def test_global_root_itself_is_not_scanned(self):

        gr = self.root / "dot_claude"
        _write_markered(gr / "plugins" / "stray", "notreal")
        found = {e["name"]: e for e in pr.discover(self.root, global_root=gr)}
        self.assertNotIn("notreal", found)

    def test_malformed_installed_plugins_is_fail_soft(self):
        gr = self.root / "dot_claude"
        manifest = gr / "plugins" / "installed_plugins.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{ this is not json")
        found = pr.discover(plugins_root=str(self.root / "empty"), global_root=gr)
        self.assertEqual(found, [])

    def test_absent_global_root_is_fail_soft(self):

        found = pr.discover(plugins_root=str(self.root / "empty"),
                            global_root=str(self.root / "no_such_cc"))
        self.assertEqual(found, [])

class PrecedenceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_beats_bundled_lookalike(self):

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
        gr = self.root / "dot_claude"
        install = self.root / "cache" / "dup" / "1.0.0"
        _write_markered(install, "dup")
        _write_installed_plugins(gr, [install])
        found = {e["name"]: e for e in
                 pr.discover(plugins_root=bundled, global_root=gr)}
        self.assertEqual(found["dup"]["origin"], "global")
        self.assertEqual(found["dup"]["dir"], str(install.resolve()))

    def test_project_beats_global(self):
        gr = self.root / "dot_claude"
        install = self.root / "cache" / "dup" / "1.0.0"
        _write_markered(install, "dup")
        _write_installed_plugins(gr, [install])
        proj = self.root / ".praxis" / "plugins"
        _write_markered(proj, "dup")
        found = {e["name"]: e for e in
                 pr.discover(self.root, plugins_root=str(self.root / "empty"), global_root=gr)}
        self.assertEqual(found["dup"]["origin"], "project")
        self.assertEqual(found["dup"]["dir"], str(proj.resolve()))

if __name__ == "__main__":
    unittest.main()

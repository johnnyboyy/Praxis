"""Tests for plugin_scaffold — generic plugin authoring (new + validate), praxis-core.
Run: cd praxis && python3 -m unittest discover -s tests"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plugin_scaffold as ps  # noqa: E402

HOUSE = Path(__file__).resolve().parents[2]   # skills/


class PluginScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_new_then_validate_roundtrips(self):
        p = self.tmp / "myplug"
        ps.scaffold(p, "myplug", phases=True, scripts=True, judgment_face="engine/domains")
        data = json.loads((p / "plugin.json").read_text())
        self.assertEqual(data["name"], "myplug")
        self.assertEqual(data["provides"], {"phases": "praxis/phases", "scripts": "praxis/scripts"})
        self.assertEqual(data["judgment_face"], "engine/domains")
        self.assertTrue((p / "praxis/phases").is_dir())
        self.assertTrue((p / "praxis/scripts").is_dir())
        self.assertTrue((p / "engine/domains").is_dir())
        self.assertEqual(ps.validate(p), [])

    def test_new_refuses_to_overwrite(self):
        p = self.tmp / "myplug"
        ps.scaffold(p, "myplug", phases=True, scripts=False, judgment_face=None)
        with self.assertRaises(SystemExit):
            ps.scaffold(p, "myplug", phases=True, scripts=False, judgment_face=None)

    def test_praxis_only_plugin_is_valid(self):
        p = self.tmp / "proc"
        ps.scaffold(p, "proc", phases=True, scripts=False, judgment_face=None)
        self.assertEqual(ps.validate(p), [])   # writing-style: praxis face only, no judgment face

    def test_validate_flags_missing_manifest(self):
        self.assertTrue(any("no plugin.json" in m for m in ps.validate(self.tmp / "nope")))

    def test_validate_flags_unknown_slot(self):
        p = self.tmp / "bad"
        p.mkdir()
        (p / "plugin.json").write_text(json.dumps({"name": "bad", "provides": {"widgets": "x"}}))
        problems = ps.validate(p)
        self.assertTrue(any("unknown slot 'widgets'" in m for m in problems))

    def test_validate_flags_provides_pointing_at_missing_dir(self):
        p = self.tmp / "bad"
        p.mkdir()
        (p / "plugin.json").write_text(json.dumps({"name": "bad", "provides": {"phases": "praxis/phases"}}))
        problems = ps.validate(p)
        self.assertTrue(any("not a directory" in m for m in problems))

    def test_validate_flags_missing_judgment_face_dir(self):
        p = self.tmp / "bad"
        p.mkdir()
        (p / "plugin.json").write_text(json.dumps({"name": "bad", "judgment_face": "engine/domains"}))
        problems = ps.validate(p)
        self.assertTrue(any("judgment_face" in m and "not a directory" in m for m in problems))

    def test_validate_flags_empty_plugin(self):
        p = self.tmp / "empty"
        p.mkdir()
        (p / "plugin.json").write_text(json.dumps({"name": "empty", "provides": {}}))
        self.assertTrue(any("neither a praxis face" in m for m in ps.validate(p)))

    def test_real_repo_plugins_are_valid(self):
        # integration: every plugin actually shipped under plugins/ validates clean (whatever they are).
        for d in sorted((HOUSE / "plugins").glob("*")):
            if (d / "plugin.json").is_file():
                self.assertEqual(ps.validate(d), [], f"{d.name} should validate clean")


if __name__ == "__main__":
    unittest.main()

"""Tests for handoff. Run with: python3 -m unittest discover -s praxis/tests -v"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import handoff as ho  # noqa: E402

BASE = Path(__file__).resolve().parent.parent / "handoff" / "base.json"


def write_plugin(d: Path, name: str, frontmatter: list[dict], sections: list[dict] | None = None):
    (d / f"{name}.json").write_text(json.dumps(
        {"plugin": name, "frontmatter": frontmatter, "sections": sections or []}))


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plugins = self.tmp / "plugins"
        self.plugins.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_schema_composes_base_plus_plugins(self):
        write_plugin(self.plugins, "acme",
                     [{"field": "acme-thing", "required": True, "shape": "scalar"}])
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))
        fields = {f["field"]: f["plugin"] for f in schema["frontmatter"]}
        self.assertEqual(fields["unit-of-work"], "praxis-base")  # base still there
        self.assertEqual(fields["acme-thing"], "acme")            # plugin extended it

    def test_validate_flags_missing_required_from_any_plugin(self):
        write_plugin(self.plugins, "acme",
                     [{"field": "acme-thing", "required": True, "shape": "scalar"}])
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))
        doc = ("---\nunit-of-work: x\nworkstream: w\nstance: none\nagent-continuity: new\n"
               "status: complete\n---\n\n## Artifact\na\n\n## Surfaced\nnone\n")  # no acme-thing
        missing = ho.validate(doc, schema)
        self.assertTrue(any("acme-thing" in m and "acme" in m for m in missing))

    def test_complete_handoff_validates(self):
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))  # no extra plugins here
        doc = ("---\nunit-of-work: x\nworkstream: w\nstance: none\nagent-continuity: new\n"
               "status: complete\ndomains-loaded: [a, b]\n---\n\n## Artifact\na\n\n## Surfaced\nnone\n")
        self.assertEqual(ho.validate(doc, schema), [])

    def test_template_round_trips_valid(self):
        # A generated template must itself pass validation (all required fields/sections present).
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))
        tmpl = ho.render_template(schema, {"unit-of-work": "u", "workstream": "w", "stance": "none"})
        self.assertEqual(ho.validate(tmpl, schema), [])

    def test_plugin_cannot_override_a_base_field(self):
        # A plugin redeclaring a base field is refused (base wins) and the conflict is recorded, so a
        # plugin can't silently downgrade a required base field to optional.
        write_plugin(self.plugins, "sneaky",
                     [{"field": "status", "required": False, "shape": "scalar"}])
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))
        status = next(f for f in schema["frontmatter"] if f["field"] == "status")
        self.assertEqual(status["plugin"], "praxis-base")
        self.assertTrue(status["required"])
        self.assertTrue(any("status" in c for c in schema["conflicts"]))

    def test_missing_section_is_a_violation(self):
        schema = ho.compose(ho.load_manifests(BASE, self.plugins))
        doc = ("---\nunit-of-work: x\nworkstream: w\nstance: none\nagent-continuity: new\n"
               "status: complete\ndomains-loaded: []\n---\n\n## Artifact\na\n")  # no ## Surfaced
        missing = ho.validate(doc, schema)
        self.assertTrue(any("Surfaced" in m for m in missing))


class HandoffCloseTests(unittest.TestCase):
    """close is the third lifecycle op (create/validate/close), fully praxis-native: delete by
    default, archive under <handoffs-dir>/archive/ when the governing root's config sets debug: yes,
    guarded so it only ever acts on a file sitting directly inside the handoffs dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "proj"
        self.handoffs = self.root / "praxis" / "handoffs"
        self.handoffs.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self, text: str):
        (self.root / "praxis" / "config.md").write_text(text)

    def _handoff(self) -> Path:
        h = self.handoffs / "h.md"
        h.write_text("---\nworkstream: w\n---\n")
        return h

    def test_debug_off_deletes(self):
        h = self._handoff()  # no config → debug off
        rc, msg = ho.close(str(h), self.handoffs, ho.project_debug(self.root))
        self.assertEqual(rc, 0)
        self.assertFalse(h.exists())
        self.assertFalse((self.handoffs / "archive").exists())

    def test_debug_on_archives(self):
        self._config("## project-shape\nname: proj\ndebug: yes\n")
        h = self._handoff()
        self.assertTrue(ho.project_debug(self.root))
        rc, msg = ho.close(str(h), self.handoffs, ho.project_debug(self.root))
        self.assertEqual(rc, 0)
        self.assertFalse(h.exists())
        self.assertTrue((self.handoffs / "archive" / "h.md").is_file())

    def test_guard_refuses_file_not_directly_in_handoffs_dir(self):
        outside = self.root / "praxis" / "elsewhere.md"
        outside.write_text("x")
        rc, msg = ho.close(str(outside), self.handoffs, False)
        self.assertEqual(rc, 1)
        self.assertIn("not directly inside", msg)
        self.assertTrue(outside.exists())  # untouched

    def test_missing_file_is_reported(self):
        rc, msg = ho.close(str(self.handoffs / "nope.md"), self.handoffs, False)
        self.assertEqual(rc, 1)
        self.assertIn("no such file", msg)

    def test_cli_close_deletes(self):
        h = self._handoff()
        rc = ho.main(["close", str(h), "--handoffs-dir", str(self.handoffs)])
        self.assertEqual(rc, 0)
        self.assertFalse(h.exists())


if __name__ == "__main__":
    unittest.main()

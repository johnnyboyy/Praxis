"""Tests for units — the lease declarations (edit surface + output) per unit of work.
Run with: python3 -m unittest discover -s praxis/tests -v

Covers the deterministic lease surface: parsing units.md, fail-open on absence, the
always-allowed praxis bookkeeping paths, and glob semantics (`*` crosses `/`, matching the
bash-`case` matching the gate hook applies).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import units  # noqa: E402

SAMPLE = """# Units of work — lease declarations

Prose between sections is ignored.

## design-ux-flow
edit-surface: docs/*, *.md
output: a design/UX-flow document

## implement-feature
edit-surface: src/*, tests/*
output: implemented code with passing tests

## retrospect
output: a retrospective note
"""


def mkroot(base: Path, units_text: str | None = None) -> Path:
    (base / ".praxis").mkdir(parents=True, exist_ok=True)
    (base / ".praxis" / "config.json").write_text("{}\n")
    if units_text is not None:
        (base / ".praxis" / "units.md").write_text(units_text)
    return base


class TestParse(unittest.TestCase):
    def test_sections_surfaces_outputs(self):
        parsed = units.parse_units(SAMPLE)
        self.assertEqual(parsed["design-ux-flow"]["edit_surface"], ["docs/*", "*.md"])
        self.assertEqual(parsed["design-ux-flow"]["output"], "a design/UX-flow document")
        self.assertEqual(parsed["implement-feature"]["edit_surface"], ["src/*", "tests/*"])

    def test_output_only_section_is_unrestricted(self):
        parsed = units.parse_units(SAMPLE)
        self.assertIsNone(parsed["retrospect"]["edit_surface"])
        self.assertEqual(parsed["retrospect"]["output"], "a retrospective note")

    def test_empty_text(self):
        self.assertEqual(units.parse_units(""), {})


class TestLease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = mkroot(Path(self.tmp.name), SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lease_for_declared_unit(self):
        lease = units.lease_for(self.root, "design-ux-flow")
        self.assertEqual(lease["edit_surface"], ["docs/*", "*.md"])

    def test_undeclared_unit_fails_open(self):
        self.assertIsNone(units.lease_for(self.root, "debug-issue"))

    def test_no_units_file_fails_open(self):
        with tempfile.TemporaryDirectory() as bare:
            root = mkroot(Path(bare))
            self.assertEqual(units.load_units(root), {})
            self.assertIsNone(units.lease_for(root, "design-ux-flow"))

    def test_no_unit_named_fails_open(self):
        self.assertIsNone(units.lease_for(self.root, None))


class TestSurfaceAllows(unittest.TestCase):
    def test_none_is_unrestricted(self):
        self.assertTrue(units.surface_allows(None, "anything/at/all.ts"))

    def test_glob_crosses_slashes(self):
        self.assertTrue(units.surface_allows(["src/*"], "src/deep/nested/file.ts"))

    def test_out_of_surface(self):
        self.assertFalse(units.surface_allows(["docs/*", "*.md"], "src/app.tsx"))

    def test_top_level_md_matches(self):
        self.assertTrue(units.surface_allows(["docs/*", "*.md"], "README.md"))
        self.assertTrue(units.surface_allows(["docs/*", "*.md"], "docs/spec.md"))

    def test_praxis_bookkeeping_always_allowed(self):
        self.assertTrue(units.surface_allows(["docs/*"], ".praxis/chunks/w.md"))
        self.assertTrue(units.surface_allows(["docs/*"], "praxis/handoffs/h.md"))


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = mkroot(Path(self.tmp.name), SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def run_units(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "units.py"), *args],
                              capture_output=True, text=True)

    def test_check_in_surface(self):
        (self.root / "docs").mkdir()
        result = self.run_units("check", "--root", str(self.root), "--unit", "design-ux-flow",
                                "--file", "docs/spec.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_out_of_surface(self):
        result = self.run_units("check", "--root", str(self.root), "--unit", "design-ux-flow",
                                "--file", "src/app.tsx")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("authorizes only", result.stdout)

    def test_check_outside_root(self):
        result = self.run_units("check", "--root", str(self.root), "--unit", "design-ux-flow",
                                "--file", "/etc/hosts")
        self.assertEqual(result.returncode, 2)

    def test_list(self):
        result = self.run_units("list", "--root", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertIn("design-ux-flow", result.stdout)
        self.assertIn("docs/*", result.stdout)


if __name__ == "__main__":
    unittest.main()

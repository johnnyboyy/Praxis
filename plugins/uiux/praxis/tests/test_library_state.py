"""Tests for library_state — the uiux plugin's deterministic library-eligibility fact (its praxis
face). Run: cd plugins/uiux/praxis && python3 -m unittest discover -s tests"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import library_state as ls  # noqa: E402


def mkroot(base: Path, has_ui: bool, state_dir: str = "corpora") -> Path:
    (base / state_dir).mkdir(parents=True, exist_ok=True)
    (base / state_dir / "config.md").write_text(
        f"## project-shape\nname: app\nhas-ui: {'yes' if has_ui else 'no'}\n")
    return base


def touch(base: Path, rel: str) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# lib\n")


def eligible(s: dict) -> set:
    return set(s["eligible"])


class LibraryStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_ui_means_no_phases(self):
        mkroot(self.tmp, has_ui=False)
        s = ls.build_state(self.tmp)
        self.assertFalse(s["has_ui"])
        self.assertEqual(eligible(s), set())

    def test_greenfield_ui_only_ui_init_eligible(self):
        mkroot(self.tmp, has_ui=True)
        s = ls.build_state(self.tmp)
        self.assertIn("ui-library-init", eligible(s))
        self.assertNotIn("ux-library-init", eligible(s))       # blocked until ui exists
        self.assertNotIn("screenshot-library-init", eligible(s))
        self.assertEqual(s["next_bootstrap_step"], "ui-library-init")

    def test_after_ui_library_screenshot_and_ux_init_unlock(self):
        mkroot(self.tmp, has_ui=True)
        touch(self.tmp, "corpora/ui-library.md")
        s = ls.build_state(self.tmp)
        elig = eligible(s)
        self.assertNotIn("ui-library-init", elig)              # already founded
        self.assertIn("screenshot-library-init", elig)
        self.assertIn("ux-library-init", elig)
        self.assertIn("ui-library-sync", elig)                 # sync becomes possible once present
        # next bootstrap step is the lowest-numbered eligible init (screenshot=3 before ux=4)
        self.assertEqual(s["next_bootstrap_step"], "screenshot-library-init")

    def test_fully_bootstrapped_only_syncs_remain(self):
        mkroot(self.tmp, has_ui=True)
        touch(self.tmp, "corpora/ui-library.md")
        touch(self.tmp, "corpora/ux-library.md")
        touch(self.tmp, "corpora/screenshots/manifest.md")
        s = ls.build_state(self.tmp)
        self.assertEqual(eligible(s), {"ui-library-sync", "ux-library-sync", "screenshot-library-sync"})
        self.assertIsNone(s["next_bootstrap_step"])

    def test_init_stances_and_units_of_work(self):
        mkroot(self.tmp, has_ui=True)
        s = ls.build_state(self.tmp)
        ui_init = next(p for p in s["phases"] if p["phase"] == "ui-library-init")
        self.assertEqual((ui_init["stance"], ui_init["unit_of_work"]), ("divergent", "bootstrap-ui-surface"))

    def test_syncs_are_marked_drift_gated(self):
        mkroot(self.tmp, has_ui=True)
        touch(self.tmp, "corpora/ui-library.md")
        s = ls.build_state(self.tmp)
        ui_sync = next(p for p in s["phases"] if p["phase"] == "ui-library-sync")
        self.assertTrue(ui_sync["drift_gated"])

    # --- `.corpora/` (standard) layout, beside the legacy `corpora/` cases above ---

    def test_dot_corpora_greenfield_ui_only_ui_init_eligible(self):
        mkroot(self.tmp, has_ui=True, state_dir=".corpora")
        s = ls.build_state(self.tmp)
        self.assertIn("ui-library-init", eligible(s))
        self.assertEqual(s["next_bootstrap_step"], "ui-library-init")

    def test_dot_corpora_after_ui_library_screenshot_and_ux_init_unlock(self):
        mkroot(self.tmp, has_ui=True, state_dir=".corpora")
        touch(self.tmp, ".corpora/ui-library.md")
        s = ls.build_state(self.tmp)
        elig = eligible(s)
        self.assertNotIn("ui-library-init", elig)
        self.assertIn("screenshot-library-init", elig)
        self.assertIn("ux-library-init", elig)
        self.assertIn("ui-library-sync", elig)

    def test_dot_corpora_fully_bootstrapped_only_syncs_remain(self):
        mkroot(self.tmp, has_ui=True, state_dir=".corpora")
        touch(self.tmp, ".corpora/ui-library.md")
        touch(self.tmp, ".corpora/ux-library.md")
        touch(self.tmp, ".corpora/screenshots/manifest.md")
        s = ls.build_state(self.tmp)
        self.assertEqual(eligible(s), {"ui-library-sync", "ux-library-sync", "screenshot-library-sync"})
        self.assertIsNone(s["next_bootstrap_step"])


if __name__ == "__main__":
    unittest.main()

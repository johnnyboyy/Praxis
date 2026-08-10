import atexit
import datetime
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "corpus.py"
SEED_DOMAINS_DIR = Path(__file__).parents[1] / "domains"
# Several domains have been extracted into plugins under plugins/*/corpora/domains/ — the
# styling-engine-agnostic UI/UX design domains (color, motion, design-method, …) into uiux, and
# interviewing (clarifying-dialogue judgment that companions planning) into routing. prose-craft
# stays in corpora-core as its own artifact-authoring hygiene; css stays too (a coding/styling
# concern). A real project moves the plugins it needs in, so its own corpora/domains/ carries those
# domains alongside the core ones. MERGED_DOMAINS_DIR reconstitutes exactly that shape — core seed ∪
# every plugin's domains — so select()/check-composition tests exercise real compositions the way a
# plugged-in project sees them.
PLUGIN_DOMAIN_DIRS = sorted((Path(__file__).parents[2] / "plugins").glob("*/corpora/domains"))


def _domain_source(name: str) -> Path:
    """Where a domain working file lives now: whichever plugin extracted it, else corpora-core seed."""
    for pdir in PLUGIN_DOMAIN_DIRS:
        cand = pdir / f"{name}.md"
        if cand.is_file():
            return cand
    return SEED_DOMAINS_DIR / f"{name}.md"


def _build_merged_domains_dir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="corpora-merged-domains-"))
    for src_dir in (SEED_DOMAINS_DIR, *PLUGIN_DOMAIN_DIRS):
        for f in src_dir.glob("*.md"):
            if f.name == "audit.md":
                continue  # composition reads domain frontmatter, not audit; skip the multi-way collision
            shutil.copy2(f, d / f.name)
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    return d


MERGED_DOMAINS_DIR = _build_merged_domains_dir()


class CorpusCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "corpora" / "domains").mkdir(parents=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_config(self, has_ui="yes"):
        (self.root / "corpora" / "config.md").write_text(
            f"# Config\n\nschema-version: 1\n\nhas-ui: {has_ui}\n"
        )

    def write_candidates(self, entries="candidates: []"):
        (self.root / "corpora" / "deterministic-shortcut-candidates.md").write_text(
            "# Deterministic shortcut candidates\n\n```yaml\n"
            + textwrap.dedent(entries).strip()
            + "\n```\n"
        )

    def write_manifest(self, entries="screens: []"):
        manifest_dir = self.root / "corpora" / "screenshots"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "manifest.md").write_text(
            "# Screenshot manifest\n\n```yaml\n"
            + textwrap.dedent(entries).strip()
            + "\n```\n"
        )

    def write_image(self, relative_path):
        image_path = self.root / "corpora" / "screenshots" / relative_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake-png")

    def write_handoff(self, ui_drift="ui-drift:\n  screens: []\n  components: []", status="complete"):
        path = self.root / "handoff.md"
        path.write_text(f"""---
stance: convergent
composition: coder
status: {status}
domains-loaded: [coding-general]
proposals: []
deterministic-shortcut-candidates: []
violations-noted: []
{ui_drift}
token-usage: "n/a"
delegated-workers: []
---

## Artifact

Nothing.

## Surfaced

""")
        return path

    def run_command(self, command):
        command = [command] if isinstance(command, str) else command
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *command],
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def candidate(identifier="color-math", status="open", reason="", second_evidence=False):
        disposition = (
            f'\n            disposition:\n              reason: "{reason}"' if reason else ""
        )
        return f"""
        candidates:
          - id: {identifier}
            operation-shape: "Deterministic perceptual color transformation."
            status: {status}
            evidence:
              - date: 2026-07-14
                workstream: settings-redesign
                burden: "Repeated manual color derivation."{'\n              - date: 2026-08-03\n                workstream: reporting-redesign\n                burden: "Manual compositing recurred."' if second_evidence else ''}{disposition}
        """

class DeterministicShortcutCommandsTest(CorpusCommandTestCase):
    def test_valid_deterministic_shortcut_candidate_passes(self):
        self.write_candidates(self.candidate())

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("1 entries", result.stdout)

    def test_empty_deterministic_shortcut_candidate_ledger_passes(self):
        self.write_candidates()

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("0 entries", result.stdout)

    def test_missing_deterministic_shortcut_candidate_ledger_fails(self):
        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 2)
        self.assertIn("no .corpora/deterministic-shortcut-candidates.md", result.stderr)

    def test_invalid_deterministic_shortcut_candidate_status_and_date_fail(self):
        self.write_candidates(
            self.candidate(status="maybe").replace("date: 2026-07-14", "date: today")
        )

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 1)
        self.assertIn("status must be", result.stdout)
        self.assertIn("date must be valid YYYY-MM-DD", result.stdout)

    def test_deterministic_shortcut_candidate_requires_evidence(self):
        candidate = self.candidate().replace(
            '            evidence:\n              - date: 2026-07-14\n                workstream: settings-redesign\n                burden: "Repeated manual color derivation."',
            "",
        )
        self.write_candidates(candidate)

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires at least one evidence record", result.stdout)

    def test_denied_deterministic_shortcut_candidate_requires_reason(self):
        self.write_candidates(self.candidate(status="denied"))

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 1)
        self.assertIn("denied status requires disposition reason", result.stdout)

    def test_duplicate_deterministic_shortcut_candidate_ids_fail(self):
        first = textwrap.dedent(self.candidate()).strip()
        second = textwrap.dedent(self.candidate()).strip().removeprefix("candidates:\n")
        self.write_candidates(first + "\n" + second)

        result = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate id", result.stdout)

    def test_deterministic_shortcut_candidates_lists_status_and_sightings(self):
        self.write_candidates(
            self.candidate(status="denied", reason="Wait for recurrence.", second_evidence=True)
        )

        result = self.run_command("deterministic-shortcut-candidates")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("color-math  status=denied  sightings=2", result.stdout)
        self.assertIn("first=2026-07-14  last=2026-08-03", result.stdout)

    def test_record_deterministic_shortcut_candidate_creates_and_resurfaces_recurrence(self):
        self.write_candidates()
        base = [
            "record-deterministic-shortcut-candidate",
            "--id", "color-math",
            "--operation-shape", "Deterministic perceptual color transformation.",
            "--workstream", "settings-redesign",
            "--burden", "Repeated manual color derivation.",
        ]

        first = self.run_command([*base, "--date", "2026-07-14"])
        second = self.run_command([
            "record-deterministic-shortcut-candidate",
            "--id", "color-math",
            "--operation-shape", "Deterministic perceptual color transformation.",
            "--workstream", "reporting-redesign",
            "--burden", "Manual compositing recurred.",
            "--date", "2026-08-03",
        ])
        listing = self.run_command("deterministic-shortcut-candidates")

        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertIn("recorded sighting 1", first.stdout)
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertIn("RESURFACE", second.stdout)
        self.assertIn("sightings=2", listing.stdout)
        self.assertIn("first=2026-07-14  last=2026-08-03", listing.stdout)

    def test_record_deterministic_shortcut_candidate_deduplicates_identical_evidence(self):
        self.write_candidates()
        command = [
            "record-deterministic-shortcut-candidate",
            "--id", "color-math",
            "--operation-shape", "Deterministic perceptual color transformation.",
            "--workstream", "settings-redesign",
            "--burden", "Repeated manual color derivation.",
            "--date", "2026-07-14",
        ]
        self.run_command(command)

        duplicate = self.run_command(command)
        listing = self.run_command("deterministic-shortcut-candidates")

        self.assertEqual(duplicate.returncode, 0, duplicate.stderr + duplicate.stdout)
        self.assertIn("identical evidence already recorded", duplicate.stdout)
        self.assertIn("sightings=1", listing.stdout)

    def test_set_deterministic_shortcut_status_requires_and_persists_denial_reason(self):
        self.write_candidates(self.candidate())

        missing = self.run_command([
            "set-deterministic-shortcut-status", "--id", "color-math", "--status", "denied"
        ])
        saved = self.run_command([
            "set-deterministic-shortcut-status", "--id", "color-math", "--status", "denied",
            "--reason", "Wait for recurrence.",
        ])
        linted = self.run_command("lint-deterministic-shortcut-candidates")

        self.assertEqual(missing.returncode, 2)
        self.assertIn("requires --reason", missing.stderr)
        self.assertEqual(saved.returncode, 0, saved.stderr + saved.stdout)
        self.assertEqual(linted.returncode, 0, linted.stderr + linted.stdout)


class ScreenshotCommandsTest(CorpusCommandTestCase):
    @staticmethod
    def screen(identifier="now-playing", components="transport-cluster, like-button",
               status="current", last_touched="2026-07-21", variant_label="default",
               variant_path=None, captured="2026-07-21"):
        variant_path = variant_path or f"{identifier}/{variant_label}.png"
        return f"""
        screens:
          - id: {identifier}
            components: [{components}]
            status: {status}
            last-touched: {last_touched}
            variants:
              - label: {variant_label}
                path: {variant_path}
                captured: {captured}
        """

    def test_lint_missing_manifest_fails(self):
        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 2)
        self.assertIn("no .corpora/screenshots/manifest.md", result.stderr)

    def test_lint_valid_manifest_passes(self):
        self.write_manifest(self.screen())
        self.write_image("now-playing/default.png")

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("1 screens", result.stdout)

    def test_lint_empty_manifest_passes(self):
        self.write_manifest()

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("0 screens", result.stdout)

    def test_lint_catches_missing_path_on_disk(self):
        self.write_manifest(self.screen())
        # deliberately do not write the image file

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist on disk", result.stdout)

    def test_lint_catches_missing_captured_date(self):
        self.write_manifest(self.screen(captured=""))
        self.write_image("now-playing/default.png")

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing captured date", result.stdout)

    def test_lint_catches_orphaned_image(self):
        self.write_manifest()
        self.write_image("stray/orphan.png")

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 1)
        self.assertIn("orphaned image not in manifest: stray/orphan.png", result.stdout)

    def test_lint_catches_duplicate_ids(self):
        first = textwrap.dedent(self.screen()).strip()
        second = textwrap.dedent(self.screen()).strip().removeprefix("screens:\n")
        self.write_manifest(first + "\n" + second)
        self.write_image("now-playing/default.png")

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate id", result.stdout)

    def test_lint_catches_invalid_status(self):
        self.write_manifest(self.screen(status="fresh"))
        self.write_image("now-playing/default.png")

        result = self.run_command("lint-screenshots")

        self.assertEqual(result.returncode, 1)
        self.assertIn("status must be one of", result.stdout)

    def test_screenshot_record_creates_new_screen(self):
        self.write_manifest()

        result = self.run_command([
            "screenshot-record", "--screen", "now-playing", "--variant", "default",
            "--path", "now-playing/default.png",
            "--components", "transport-cluster, like-button",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        manifest_text = (self.root / "corpora" / "screenshots" / "manifest.md").read_text()
        self.assertIn("id: now-playing", manifest_text)
        self.assertIn("status: current", manifest_text)
        self.assertIn("components: [transport-cluster, like-button]", manifest_text)
        self.assertIn("path: now-playing/default.png", manifest_text)

    def test_screenshot_record_updates_existing_variant(self):
        self.write_manifest()
        self.run_command([
            "screenshot-record", "--screen", "now-playing", "--variant", "default",
            "--path", "now-playing/default.png", "--components", "transport-cluster",
        ])

        result = self.run_command([
            "screenshot-record", "--screen", "now-playing", "--variant", "default",
            "--path", "now-playing/default.png", "--components", "transport-cluster, queue-sheet",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        manifest_text = (self.root / "corpora" / "screenshots" / "manifest.md").read_text()
        self.assertIn("components: [transport-cluster, queue-sheet]", manifest_text)
        # only one variant entry for the same label, not a duplicate
        self.assertEqual(manifest_text.count("label: default"), 1)

    def test_screenshot_record_adds_second_variant(self):
        self.write_manifest()
        self.run_command([
            "screenshot-record", "--screen", "now-playing", "--variant", "default",
            "--path", "now-playing/default.png", "--components", "transport-cluster",
        ])

        result = self.run_command([
            "screenshot-record", "--screen", "now-playing", "--variant", "dark",
            "--path", "now-playing/dark.png", "--components", "transport-cluster",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        manifest_text = (self.root / "corpora" / "screenshots" / "manifest.md").read_text()
        self.assertIn("label: default", manifest_text)
        self.assertIn("label: dark", manifest_text)

    def test_screenshot_mark_stale_direct_screen(self):
        self.write_manifest(self.screen())
        self.write_image("now-playing/default.png")

        result = self.run_command([
            "screenshot-mark-stale", "--screens", "now-playing", "--components", "",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("marked stale: now-playing", result.stdout)
        manifest_text = (self.root / "corpora" / "screenshots" / "manifest.md").read_text()
        self.assertIn("status: stale", manifest_text)

    def test_screenshot_mark_stale_ripples_via_shared_component(self):
        entries = (
            textwrap.dedent(self.screen(identifier="now-playing", components="queue-sheet")).strip()
            + "\n"
            + textwrap.dedent(
                self.screen(identifier="discover", components="queue-sheet",
                            variant_path="discover/default.png")
            ).strip().removeprefix("screens:\n")
        )
        self.write_manifest(entries)
        self.write_image("now-playing/default.png")
        self.write_image("discover/default.png")

        result = self.run_command([
            "screenshot-mark-stale", "--screens", "", "--components", "queue-sheet",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("now-playing", result.stdout)
        self.assertIn("discover", result.stdout)
        manifest_text = (self.root / "corpora" / "screenshots" / "manifest.md").read_text()
        self.assertEqual(manifest_text.count("status: stale"), 2)

    def test_screenshot_mark_stale_unknown_screen_is_noop(self):
        self.write_manifest(self.screen())
        self.write_image("now-playing/default.png")

        result = self.run_command([
            "screenshot-mark-stale", "--screens", "nonexistent-screen", "--components", "",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("marked stale: none", result.stdout)

    def test_screenshot_status_lists_current_and_stale(self):
        entries = (
            textwrap.dedent(self.screen(identifier="now-playing")).strip()
            + "\n"
            + textwrap.dedent(
                self.screen(identifier="discover", status="stale", variant_path="discover/default.png")
            ).strip().removeprefix("screens:\n")
        )
        self.write_manifest(entries)
        self.write_image("now-playing/default.png")
        self.write_image("discover/default.png")

        result = self.run_command("screenshot-status")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("1 current, 1 stale", result.stdout)
        self.assertIn("now-playing", result.stdout)
        self.assertIn("discover", result.stdout)

    def test_screenshot_status_absent_manifest(self):
        result = self.run_command("screenshot-status")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("absent", result.stdout)

    def test_screenshot_lookup_finds_matching_screens(self):
        entries = (
            textwrap.dedent(self.screen(identifier="now-playing", components="queue-sheet")).strip()
            + "\n"
            + textwrap.dedent(
                self.screen(identifier="discover", components="hero-card",
                            variant_path="discover/default.png")
            ).strip().removeprefix("screens:\n")
        )
        self.write_manifest(entries)
        self.write_image("now-playing/default.png")
        self.write_image("discover/default.png")

        result = self.run_command(["screenshot-lookup", "--component", "queue-sheet"])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("now-playing", result.stdout)
        self.assertIn("now-playing/default.png", result.stdout)
        self.assertNotIn("discover", result.stdout)

    def test_screenshot_lookup_no_matches(self):
        self.write_manifest(self.screen())
        self.write_image("now-playing/default.png")

        result = self.run_command(["screenshot-lookup", "--component", "nonexistent-component"])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("no screens tagged", result.stdout)


class RecordGateCoOccurrenceTest(CorpusCommandTestCase):
    def write_domain(self, name):
        (self.root / "corpora" / "domains" / f"{name}.md").write_text(
            f'# Domain: {name}\n\n```yaml\nprinciples:\n\n- id: p1\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n```\n'
        )

    def record_gate(self, extra=()):
        return self.run_command([
            "record-gate", "--domain", "color", "--ratified", "0", "--killed", "0",
            "--violations", "0", *extra,
        ])

    def test_record_gate_tallies_domain_co_occurrence(self):
        self.write_domain("color")
        self.write_domain("motion")

        result = self.record_gate(["--co-occurs-with", "motion"])

        self.assertEqual(result.returncode, 0, result.stderr)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("domains: [color, motion]", audit_text)
        self.assertIn("count: 1", audit_text)

    def test_record_gate_co_occurrence_accumulates_across_gates(self):
        self.write_domain("color")
        self.write_domain("motion")

        for _ in range(2):
            result = self.record_gate(["--co-occurs-with", "motion"])
            self.assertEqual(result.returncode, 0, result.stderr)

        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("count: 2", audit_text)

    def test_record_gate_tracks_distinct_co_occurrence_pairs_independently(self):
        # Edge net for parse_state's list sections: two co-occurrence items must round-trip
        # through parse/render as separate records (each carrying a two-element inline `domains`
        # list) so a later gate increments only the matching pair.
        for name in ("color", "motion", "extra"):
            self.write_domain(name)

        self.assertEqual(self.record_gate(["--co-occurs-with", "motion, extra"]).returncode, 0)
        self.assertEqual(self.record_gate(["--co-occurs-with", "motion"]).returncode, 0)

        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("domains: [color, motion]", audit_text)
        self.assertIn("domains: [color, extra]", audit_text)
        motion_block = audit_text.split("domains: [color, motion]", 1)[1]
        self.assertTrue(motion_block.lstrip().startswith("count: 2"), audit_text)
        extra_block = audit_text.split("domains: [color, extra]", 1)[1]
        self.assertTrue(extra_block.lstrip().startswith("count: 1"), audit_text)



class ConventionsTest(CorpusCommandTestCase):
    """proposals/domain-repo-import.md §1: `conventions:` is a structured home for a graduated
    principle — id/rule/reason, no condition — that still keys into audit.md and the ledger like
    a principle does."""

    def write_domain_text(self, name, body):
        frontmatter = ("---\nsubject: coding\nposture: guardrail\n"
                       "units-of-work: [implement-feature]\nuniversal: false\n---\n\n")
        (self.root / "corpora" / "domains" / f"{name}.md").write_text(
            frontmatter + f"# Domain: {name}\n\n```yaml\n{body}```\n"
        )

    def domain_with_convention(self, extra_condition=""):
        return (
            "conventions:\n\n"
            "- id: block-arrow-bodies\n"
            '  rule: "Always use block arrow bodies."\n'
            '  reason: "The concise form has a silent failure mode."\n'
            + extra_condition +
            "\nprinciples:\n\n"
            '- id: p1\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n'
            "\nkilled:\n\n"
        )

    def test_lint_domains_passes_valid_convention(self):
        self.write_domain_text("conventions-test-domain", self.domain_with_convention())

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-domains", "--domains-dir",
             str(self.root / "corpora" / "domains")],
            text=True, capture_output=True, check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lint_domains_flags_convention_missing_reason(self):
        self.write_domain_text(
            "conventions-test-domain",
            "conventions:\n\n- id: no-reason\n  rule: \"R\"\n\nprinciples:\n\nkilled:\n\n",
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-domains", "--domains-dir",
             str(self.root / "corpora" / "domains")],
            text=True, capture_output=True, check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("missing reason", result.stderr)

    def test_lint_domains_flags_convention_with_condition(self):
        self.write_domain_text(
            "conventions-test-domain",
            self.domain_with_convention(extra_condition='  condition: "Should not be here."\n'),
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-domains", "--domains-dir",
             str(self.root / "corpora" / "domains")],
            text=True, capture_output=True, check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unconditioned by definition", result.stderr)

    def test_manifest_lists_convention_ids(self):
        self.write_domain_text("conventions-test-domain", self.domain_with_convention())

        result = self.run_command(["manifest", "--json"])

        import json
        data = json.loads(result.stdout)
        domain = next(d for d in data["domains"] if d["name"] == "conventions-test-domain")
        self.assertEqual(domain["conventions"], ["block-arrow-bodies"])

    def test_verify_reconciles_after_graduation(self):
        # Simulate: a principle already ratified, then graduated to a convention this gate.
        self.write_domain_text(
            "conventions-test-domain",
            "conventions:\n\n"
            '- id: block-arrow-bodies\n  rule: "R"\n  reason: "Why."\n'
            "\nprinciples:\n\nkilled:\n\n",
        )
        gate = self.run_command([
            "record-gate", "--domain", "conventions-test-domain", "--graduated", "1",
        ])
        self.assertEqual(gate.returncode, 0, gate.stderr)

        result = self.run_command(["verify"])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reconciled", result.stdout)

    def test_verify_flags_unrecorded_graduation(self):
        self.write_domain_text("conventions-test-domain", "principles:\n\nkilled:\n\n")
        measure = self.run_command(["measure"])
        self.assertEqual(measure.returncode, 0, measure.stderr)
        # A convention appears in the working file with no matching --graduated recorded.
        self.write_domain_text(
            "conventions-test-domain",
            "conventions:\n\n"
            '- id: block-arrow-bodies\n  rule: "R"\n  reason: "Why."\n'
            "\nprinciples:\n\nkilled:\n\n",
        )

        result = self.run_command(["verify"])

        self.assertEqual(result.returncode, 1)
        self.assertIn("UNRECORDED graduation", result.stdout)


class ArbitraryLayerOverrideTest(unittest.TestCase):
    """measure/verify/record-gate must work on any domains-dir + audit.md pair — e.g. this
    skill's own domains/, not only a project's own corpora/domains — the same treatment
    kill-report/graduate-kill already have."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.domains_dir = self.root / "seed-domains"
        self.domains_dir.mkdir()
        self.audit_path = self.domains_dir / "audit.md"
        (self.domains_dir / "widgets.md").write_text(
            '# Domain: widgets\n\n```yaml\nprinciples:\n\n- id: p1\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n```\n'
        )
        self.audit_path.write_text("# Audit\n\n```yaml\nprovenance:\n```\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *command],
            text=True, capture_output=True, check=False,
        )

    def layer_args(self):
        return ["--domains-dir", str(self.domains_dir), "--audit", str(self.audit_path)]

    def test_measure_registers_a_non_project_layer(self):
        result = self.run_command(["measure", *self.layer_args()])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("widgets:", result.stdout)
        self.assertIn("counters:", self.audit_path.read_text())

    def test_verify_reconciles_a_non_project_layer(self):
        self.run_command(["measure", *self.layer_args()])

        result = self.run_command(["verify", *self.layer_args()])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("ledger reconciled", result.stdout)

    def test_record_gate_writes_to_the_given_audit_file(self):
        self.run_command(["measure", *self.layer_args()])

        result = self.run_command([
            "record-gate", *self.layer_args(), "--domain", "widgets", "--ratified", "1",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ratified: 1", self.audit_path.read_text())

    def test_measure_without_domains_dir_falls_back_to_root_corpora_domains(self):
        (self.root / "corpora" / "domains").mkdir(parents=True)
        (self.root / "corpora" / "domains" / "color.md").write_text(
            "# Domain: color\n\n```yaml\nprinciples:\n```\n"
        )

        result = self.run_command(["--root", str(self.root), "measure"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("color:", result.stdout)


class EmitSpawnPartsTest(CorpusCommandTestCase):
    """emit-spawn-parts is the corpora side of spawn-prompt composition after the process/judgment
    split: corpora emits its PARTS (stance frame, byte-for-byte domain bodies, handoff-read schema)
    and judges composition validity; praxis owns the assembly + save lifecycle (tested praxis-side).
    The verb emits JSON — a hook praxis composes without knowing what a part means."""

    def parts(self, result):
        import json
        return json.loads(result.stdout)

    def test_emits_stance_frame_domains_and_handoff_schema_parts_byte_for_byte(self):
        result = self.run_command([
            "emit-spawn-parts", "--domains", "coding-general", "--domains-dir", str(SEED_DOMAINS_DIR),
        ])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = self.parts(result)
        self.assertEqual(payload["problems"], [])
        by_slot = {p["slot"]: p["body"] for p in payload["parts"]}
        self.assertIn("### Generative stance", by_slot["stance-frame"])
        self.assertIn("### Domain: coding-general", by_slot["domains"])
        self.assertIn("What corpora reads from a handoff", by_slot["handoff-schema"])
        # byte-for-byte, not summarized: a real principle id from the seed file must survive whole
        seed_text = (Path(__file__).parents[1] / "domains" / "coding-general.md").read_text()
        first_id_line = next(line for line in seed_text.splitlines() if line.strip().startswith("- id:"))
        self.assertIn(first_id_line.strip(), by_slot["domains"])

    def test_project_domain_is_the_sole_source_no_seed_merge(self):
        # proposals/domain-repo-import.md §2: a project's own corpora/domains/ is the whole domain
        # set; a same-named seed domain never leaks in (the skill's own coding-general carries an
        # "ask-before-architecture" principle that must NOT appear).
        (self.root / "corpora" / "domains" / "coding-general.md").write_text(
            "# Domain: coding-general (project)\n\n```yaml\n"
            "principles:\n\n- id: project-only-rule\n  rule: \"R\"\n  condition: \"C\"\n  reason: \"Why.\"\n\nkilled:\n```\n"
        )
        result = self.run_command(["emit-spawn-parts", "--domains", "coding-general"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        domains_body = {p["slot"]: p["body"] for p in self.parts(result)["parts"]}["domains"]
        self.assertIn("project-only-rule", domains_body)
        self.assertNotIn("ask-before-architecture", domains_body)

    def test_project_only_domain_with_no_seed_counterpart(self):
        (self.root / "corpora" / "domains" / "spatial-metaphor.md").write_text(
            "# Domain: spatial-metaphor\n\n```yaml\nprinciples:\n\nkilled:\n```\n"
        )
        result = self.run_command(["emit-spawn-parts", "--domains", "spatial-metaphor"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        domains_body = {p["slot"]: p["body"] for p in self.parts(result)["parts"]}["domains"]
        self.assertIn("### Domain: spatial-metaphor", domains_body)

    def test_unknown_domain_fails(self):
        result = self.run_command(["emit-spawn-parts", "--domains", "not-a-real-domain"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("nothing to compose", result.stderr)


class InitTest(CorpusCommandTestCase):
    """corpus.py init — the engine's own bootstrap (writes corpora/config.md), the symmetric
    counterpart to praxis_init's root marker. Structure not judgment: shape values are passed in."""

    def setUp(self):
        super().setUp()
        # init writes the config; start without one (base setUp only makes corpora/domains/).
        (self.root / "corpora" / "config.md").unlink(missing_ok=True)
        (self.root / ".corpora" / "config.md").unlink(missing_ok=True)

    def test_writes_config_with_shape(self):
        result = self.run_command(["init", "--language", "python", "--framework", "fastapi",
                                   "--has-ui", "no"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        text = (self.root / ".corpora" / "config.md").read_text()
        self.assertIn("language: python", text)
        self.assertIn("framework: fastapi", text)
        self.assertIn("has-ui: no", text)
        self.assertIn("utilities: []", text)

    def test_has_ui_yes_writes_ui_library_block(self):
        result = self.run_command(["init", "--has-ui", "yes", "--styling", "tailwind"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        text = (self.root / ".corpora" / "config.md").read_text()
        self.assertIn("## ui-library", text)
        self.assertIn("path: .corpora/ui-library.md", text)

    def test_has_ui_no_omits_ui_library_block(self):
        self.run_command(["init", "--has-ui", "no"])
        self.assertNotIn("## ui-library", (self.root / ".corpora" / "config.md").read_text())

    def test_creates_empty_shortcut_candidate_ledger(self):
        self.run_command(["init", "--has-ui", "no"])
        ledger = self.root / ".corpora" / "deterministic-shortcut-candidates.md"
        self.assertTrue(ledger.exists())
        result = self.run_command(["lint-deterministic-shortcut-candidates"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_reinit_preserves_existing_shortcut_ledger(self):
        self.run_command(["init"])
        ledger = self.root / ".corpora" / "deterministic-shortcut-candidates.md"
        recorded = ledger.read_text().replace("candidates: []", "candidates:\n- id: kept\n")
        ledger.write_text(recorded)
        self.run_command(["init", "--force"])
        self.assertEqual(ledger.read_text(), recorded)

    def test_refuses_to_overwrite_without_force(self):
        self.run_command(["init"])
        result = self.run_command(["init", "--language", "rust"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("already bootstrapped", result.stderr)
        # untouched
        self.assertNotIn("rust", (self.root / ".corpora" / "config.md").read_text())

    def test_force_overwrites(self):
        self.run_command(["init", "--language", "python"])
        result = self.run_command(["init", "--language", "rust", "--force"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("language: rust", (self.root / ".corpora" / "config.md").read_text())

    def test_bootstrapped_config_is_valid_for_select(self):
        # The config init writes must be readable by the very next command a session runs.
        self.run_command(["init", "--language", "python", "--has-ui", "no"])
        result = self.run_command(["select", "--unit-of-work", "implement-feature",
                                   "--domains-dir", str(SEED_DOMAINS_DIR)])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


class ImportTest(CorpusCommandTestCase):
    """proposals/domain-repo-import.md §3: import is a candidate producer, not a direct write —
    it never touches a domain working file, only appends to corpora/import-candidates.md."""

    def setUp(self):
        super().setUp()
        self.source_dir = self.root / "source-domains"
        self.source_dir.mkdir()
        (self.source_dir / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\n"
            "conventions:\n\n"
            '- id: a-convention\n  rule: "Do X."\n  reason: "Because Y."\n\n'
            "principles:\n\n"
            '- id: a-principle\n  rule: "Do Z."\n  condition: "When W."\n  reason: "Because V."\n\n'
            "killed:\n```\n"
        )
        (self.source_dir / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n"
            "- id: a-principle\n  domain: widgets\n  provenance: \"2026-01-01, some task.\"\n```\n"
        )

    def test_import_list_flags_already_present(self):
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\n"
            'principles:\n\n- id: a-principle\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\nkilled:\n```\n'
        )

        result = self.run_command(["import-list", "--source", str(self.source_dir)])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("widgets/a-convention (convention): Do X.", result.stdout)
        self.assertIn("widgets/a-principle (principle) [already present]: Do Z.", result.stdout)

    def test_import_candidate_proposes_principle_with_provenance(self):
        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-principle",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertIn("id: a-principle", candidates)
        self.assertIn('condition: "When W."', candidates)
        self.assertIn("imported-from:", candidates)
        self.assertIn(f'source: "{self.source_dir}"', candidates)
        self.assertIn("domain: widgets", candidates)
        self.assertIn('originally-ratified: "2026-01-01, some task."', candidates)
        # never writes into a domain working file directly
        self.assertFalse((self.root / "corpora" / "domains" / "widgets.md").exists())

    def test_import_candidate_convention_has_no_condition_field(self):
        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-convention",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        block = candidates.split("id: a-convention", 1)[1]
        self.assertNotIn("condition:", block.split("provenance:")[0])

    def test_import_candidate_can_rename_and_retarget_domain(self):
        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-principle",
            "--as-domain", "other-domain", "--as-id", "renamed-principle",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertIn("id: renamed-principle", candidates)
        self.assertIn("domains: [other-domain]", candidates)
        self.assertIn("id: a-principle", candidates)  # source id preserved in imported-from

    def test_import_candidate_refuses_id_collision(self):
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\n"
            'principles:\n\n- id: a-principle\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\nkilled:\n```\n'
        )

        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-principle",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)

    def test_import_candidate_unknown_id_fails(self):
        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "nonexistent",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("no principle or convention", result.stderr)

    def test_import_candidate_appends_multiple_entries(self):
        self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-principle",
        ])

        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", "a-convention",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertIn("id: a-principle", candidates)
        self.assertIn("id: a-convention", candidates)
        self.assertEqual(candidates.count("extracted:"), 2)

    def test_import_default_pool_matches_project_shape(self):
        self.write_shape = None  # not used; write config directly
        (self.root / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nlanguage: typescript\nhas-ui: no\n"
        )

        result = self.run_command(["import-default-pool", "--source", str(self.source_dir)])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("proposed 2 candidate(s)", result.stdout)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertIn("id: a-principle", candidates)
        self.assertIn("id: a-convention", candidates)


class ImportSyncTest(CorpusCommandTestCase):
    """import-default-pool as a re-sync: beyond proposing new ids, it must surface source-side
    edits (same id, different content) as `change: update` candidates and source-side kills of
    entries still live in the target as `change: kill` candidates — gate-mediated, never written
    live. ratify-import-candidate applies both."""

    def setUp(self):
        super().setUp()
        self.source_dir = self.root / "source-domains"
        self.source_dir.mkdir()
        (self.source_dir / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\n"
            "principles:\n\n"
            '- id: same-one\n  rule: "Unchanged."\n  condition: "Always."\n  reason: "Stable."\n\n'
            '- id: changed-one\n  rule: "Do Z v2."\n  condition: "When W2."\n  reason: "Because V2."\n\n'
            '- id: new-one\n  rule: "Brand new."\n  condition: "When N."\n  reason: "Because N."\n\n'
            "killed:\n\n"
            '- id: dead-one\n  rule: "Old rule."\n  kill_type: container\n'
            '  reason_killed: "Process restated as a principle."\n  killed: 2026-08-07\n'
            "```\n"
        )
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: none\n\n"
            "principles:\n\n"
            '- id: same-one\n  rule: "Unchanged."\n  condition: "Always."\n  reason: "Stable."\n\n'
            '- id: changed-one\n  rule: "Do Z."\n  condition: "When W."\n  reason: "Because V."\n\n'
            '- id: dead-one\n  rule: "Old rule."\n  condition: "When D."\n  reason: "Because D."\n\n'
            "killed:\n```\n"
        )
        (self.root / "corpora" / "domains" / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n- id: same-one\n  domain: widgets\n"
            '  provenance: "2026-01-01, pre-existing."\n```\n\n'
            "<!-- corpus-script:begin -->\n\n```yaml\ncounters: []\nefficacy: []\n"
            "co-occurrence: []\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
        )
        (self.root / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nlanguage: typescript\nhas-ui: no\n"
        )

    def sync(self):
        result = self.run_command(["import-default-pool", "--source", str(self.source_dir)])
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.root / "corpora" / "import-candidates.md").read_text()

    def test_sync_proposes_update_for_changed_entry(self):
        candidates = self.sync()
        block = candidates.split("- id: changed-one", 1)[1].split("- id:")[0]
        self.assertIn("change: update", block)
        self.assertIn('rule: "Do Z v2."', block)
        self.assertNotIn("- id: same-one", candidates)

    def test_sync_proposes_kill_for_source_killed_live_in_target(self):
        candidates = self.sync()
        block = candidates.split("- id: dead-one", 1)[1].split("- id:")[0]
        self.assertIn("change: kill", block)
        self.assertIn("kill-type: container", block)
        self.assertIn('reason: "Process restated as a principle."', block)

    def test_sync_skips_kill_already_applied_in_target(self):
        domain_path = self.root / "corpora" / "domains" / "widgets.md"
        text = domain_path.read_text()
        text = text.replace(
            '- id: dead-one\n  rule: "Old rule."\n  condition: "When D."\n  reason: "Because D."\n\n', "")
        text = text.replace(
            "killed:\n```",
            'killed:\n\n- id: dead-one\n  rule: "Old rule."\n  kill_type: container\n'
            '  reason_killed: "Process restated as a principle."\n```')
        domain_path.write_text(text)

        candidates = self.sync()
        self.assertNotIn("- id: dead-one", candidates)

    def test_sync_does_not_requeue_pending_candidates(self):
        self.sync()
        candidates = self.sync()
        self.assertEqual(candidates.count("- id: changed-one"), 1)
        self.assertEqual(candidates.count("- id: dead-one"), 1)
        self.assertEqual(candidates.count("- id: new-one"), 1)

    def test_sync_proposes_kill_from_source_audit_kill_log(self):
        # Post-relocation source pool: kill record lives in the source audit's kills: fence, the
        # working file's killed: marker is empty.
        (self.source_dir / "widgets.md").write_text(
            (self.source_dir / "widgets.md").read_text().split("killed:", 1)[0] + "killed:\n```\n")
        (self.source_dir / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n```\n\n"
            "<!-- corpus-script:begin -->\n<!-- corpus-script:end -->\n\n"
            "# Kill log\n\n```yaml\nkills:\n\n"
            "- id: dead-one\n  domain: widgets\n"
            '  rule: "Old rule."\n  kill_type: container\n'
            '  reason_killed: "Process restated as a principle."\n  killed: 2026-08-07\n```\n'
        )

        candidates = self.sync()

        block = candidates.split("- id: dead-one", 1)[1].split("- id:")[0]
        self.assertIn("change: kill", block)
        self.assertIn("kill-type: container", block)
        self.assertIn('reason: "Process restated as a principle."', block)

    def test_sync_skips_kill_already_applied_in_target_audit_kill_log(self):
        # Post-relocation target pool: the applied kill sits in the target audit's kills: fence,
        # not the working file's killed: section.
        domain_path = self.root / "corpora" / "domains" / "widgets.md"
        domain_path.write_text(domain_path.read_text().replace(
            '- id: dead-one\n  rule: "Old rule."\n  condition: "When D."\n  reason: "Because D."\n\n', ""))
        audit_path = self.root / "corpora" / "domains" / "audit.md"
        audit_path.write_text(
            audit_path.read_text().rstrip("\n") + "\n\n# Kill log\n\n```yaml\nkills:\n\n"
            "- id: dead-one\n  domain: widgets\n"
            '  rule: "Old rule."\n  kill_type: container\n'
            '  reason_killed: "Process restated as a principle."\n  killed: 2026-08-07\n```\n'
        )

        candidates = self.sync()
        self.assertNotIn("- id: dead-one", candidates)

    def write_source_audit_history(self, entry_id, domain, history_lines):
        (self.source_dir / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n"
            f"- id: {entry_id}\n  domain: {domain}\n"
            '  provenance: "Original."\n'
            "  history:\n" + history_lines + "```\n"
        )

    def test_sync_proposes_move_from_source_history(self):
        # Source reorg: moved-one relocated widgets -> gadgets (audit history records it; the
        # entry's current domain field is the destination). Target still holds it in widgets.
        (self.source_dir / "gadgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: gadgets\n\n```yaml\nprinciples:\n\n"
            '- id: moved-one\n  rule: "Do M."\n  condition: "When M."\n  reason: "Because M."\n\n'
            "killed:\n```\n"
        )
        target_widgets = self.root / "corpora" / "domains" / "widgets.md"
        target_widgets.write_text(target_widgets.read_text().replace(
            "principles:\n\n",
            'principles:\n\n- id: moved-one\n  rule: "Do M."\n  condition: "When M."\n  reason: "Because M."\n\n'))
        self.write_source_audit_history(
            "moved-one", "gadgets",
            "    - date: 2026-08-07\n      type: moved\n"
            '      reason: "widgets -> gadgets."\n')

        candidates = self.sync()

        block = candidates.split("- id: moved-one", 1)[1].split("- id:")[0]
        self.assertIn("change: move", block)
        self.assertIn("from-domain: widgets", block)
        self.assertIn("domains: [gadgets]", block)
        # queued as a move, not double-proposed as a plain new candidate
        self.assertEqual(candidates.count("- id: moved-one"), 1)

    def test_ratify_move_relocates_entry_across_domains(self):
        self.test_sync_proposes_move_from_source_history()
        (self.root / "corpora" / "domains" / "gadgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: gadgets\n\n```yaml\nlast-retrospective: none\n\n"
            "principles:\n\nkilled:\n```\n"
        )

        result = self.run_command(["ratify-import-candidate", "--id", "moved-one"])

        self.assertEqual(result.returncode, 0, result.stderr)
        widgets_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertNotIn("- id: moved-one", widgets_text)
        gadgets_text = (self.root / "corpora" / "domains" / "gadgets.md").read_text()
        self.assertIn("- id: moved-one", gadgets_text)
        self.assertIn('condition: "When M."', gadgets_text)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        # applied move does not re-queue on the next sync
        candidates = self.sync()
        self.assertNotIn("- id: moved-one", candidates)

    def test_sync_proposes_supersede_from_consolidation_history(self):
        # Source consolidated old-merged into same-one (still live); old-merged no longer live in
        # source but still live in the target.
        target_widgets = self.root / "corpora" / "domains" / "widgets.md"
        target_widgets.write_text(target_widgets.read_text().replace(
            "principles:\n\n",
            'principles:\n\n- id: old-merged\n  rule: "Old."\n  condition: "When O."\n  reason: "Because O."\n\n'))
        self.write_source_audit_history(
            "old-merged", "widgets",
            "    - date: 2026-08-07\n      type: consolidated\n"
            "      successor: same-one\n"
            '      reason: "Merged into same-one."\n')

        candidates = self.sync()

        block = candidates.split("- id: old-merged", 1)[1].split("- id:")[0]
        self.assertIn("change: supersede", block)
        self.assertIn("successor: same-one", block)
        self.assertEqual(candidates.count("- id: old-merged"), 1)

    def test_applied_update_with_escapes_does_not_requeue(self):
        # Escaping round-trip regression (found live in FAMOUS): an entry whose text carries
        # embedded quotes/backslash sequences must survive parse -> yaml_quote -> parse without
        # amplification, so an applied update stops being proposed on the next sync.
        source_path = self.source_dir / "widgets.md"
        source_path.write_text(source_path.read_text().replace(
            '- id: changed-one\n  rule: "Do Z v2."',
            '- id: changed-one\n  rule: "Say \\"hi\\" then \\\\n newline v2."'))

        self.sync()
        result = self.run_command(["ratify-import-candidate", "--id", "changed-one"])
        self.assertEqual(result.returncode, 0, result.stderr)

        domain_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertIn('rule: "Say \\"hi\\" then \\\\n newline v2."', domain_text)
        candidates = self.run_command(["import-default-pool", "--source", str(self.source_dir)])
        self.assertEqual(candidates.returncode, 0, candidates.stderr)
        queued = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertNotIn("- id: changed-one", queued)

    def test_sync_skips_source_id_locally_killed_in_target(self):
        # new-one is live in the source but this pool killed it (audit kill log): a settled
        # local rejection — noted once per run, never re-queued as a candidate.
        audit_path = self.root / "corpora" / "domains" / "audit.md"
        audit_path.write_text(
            audit_path.read_text().rstrip("\n") + "\n\n# Kill log\n\n```yaml\nkills:\n\n"
            "- id: new-one\n  domain: widgets\n"
            '  rule: "Brand new."\n  kill_type: quality\n'
            '  reason_killed: "Locally rejected."\n  killed: 2026-08-01\n```\n'
        )

        result = self.run_command(["import-default-pool", "--source", str(self.source_dir)])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped (locally killed): widgets/new-one", result.stdout)
        candidates = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertNotIn("- id: new-one", candidates)
        # updates to still-live ids are unaffected
        self.assertIn("- id: changed-one", candidates)

    def test_ratify_supersede_removes_entry_and_reconciles(self):
        self.test_sync_proposes_supersede_from_consolidation_history()

        result = self.run_command(["ratify-import-candidate", "--id", "old-merged"])

        self.assertEqual(result.returncode, 0, result.stderr)
        widgets_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertNotIn("- id: old-merged", widgets_text)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("superseded by same-one", audit_text)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        candidates = self.sync()
        self.assertNotIn("- id: old-merged", candidates)

    def test_ratify_update_rewrites_entry_in_place(self):
        self.sync()

        result = self.run_command(["ratify-import-candidate", "--id", "changed-one"])

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertIn('rule: "Do Z v2."', domain_text)
        self.assertNotIn('rule: "Do Z."', domain_text)
        self.assertEqual(domain_text.count("- id: changed-one"), 1)
        self.assertNotIn("- id: changed-one",
                         (self.root / "corpora" / "import-candidates.md").read_text())
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_ratify_kill_reconciles_when_domain_already_in_ledger(self):
        # The sequential case: a prior gate registered the domain's baseline (here via the
        # update write-back), then a kill lands — the ledger must still reconcile.
        self.sync()
        self.run_command(["ratify-import-candidate", "--id", "changed-one"])

        result = self.run_command(["ratify-import-candidate", "--id", "dead-one"])

        self.assertEqual(result.returncode, 0, result.stderr)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_ratify_kill_moves_entry_to_audit_kill_log(self):
        self.sync()

        result = self.run_command(["ratify-import-candidate", "--id", "dead-one"])

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        killed_section = domain_text.split("killed:", 1)[1]
        self.assertNotIn("- id:", killed_section)
        principles_section = domain_text.split("principles:", 1)[1].split("killed:")[0]
        self.assertNotIn("- id: dead-one", principles_section)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        kill_log = audit_text.split("kills:", 1)[1]
        self.assertIn("- id: dead-one", kill_log)
        self.assertIn("domain: widgets", kill_log)
        self.assertIn("kill_type: container", kill_log)
        self.assertIn('reason_killed: "Process restated as a principle."', kill_log)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)


class AddPrincipleTest(CorpusCommandTestCase):
    """add-principle: the scripted write-back for a freshly-authored or mined principle — domain
    file + audit.md provenance + record-gate, atomically, no hand edits to either file."""

    def write_domain(self, name="sample", body='- id: existing-one\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\n'):
        (self.root / "corpora" / "domains" / f"{name}.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: sample\n\n```yaml\nlast-retrospective: none\n\n"
            f"principles:\n\n{body}killed:\n```\n"
        )
        (self.root / "corpora" / "domains" / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n- id: existing-one\n  domain: sample\n"
            '  provenance: "2026-01-01, pre-existing."\n```\n\n'
            "<!-- corpus-script:begin -->\n\n```yaml\ncounters: []\nefficacy: []\n"
            "co-occurrence: []\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
        )

    def add(self, **kwargs):
        args = {
            "domain": "sample", "id": "new-one", "rule": "Test rule.",
            "condition": "Test condition.", "reason": "Test reason.",
            "provenance": "2026-08-02, test.",
        }
        args.update(kwargs)
        flags = []
        for k, v in args.items():
            flags += [f"--{k}", v]
        return self.run_command(["add-principle", *flags])

    def test_writes_principle_and_provenance_and_reconciles(self):
        self.write_domain()

        result = self.add()

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "sample.md").read_text()
        self.assertIn("id: new-one", domain_text)
        self.assertIn('condition: "Test condition."', domain_text)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("id: new-one", audit_text)
        self.assertIn('provenance: "2026-08-02, test."', audit_text)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        self.assertIn("reconciled", verify.stdout)

    def test_records_kind_when_given(self):
        self.write_domain()

        result = self.add(kind="judgment")

        self.assertEqual(result.returncode, 0, result.stderr)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("kind: judgment", audit_text)

    def test_see_also_written_when_given(self):
        self.write_domain()

        result = self.add(**{"see-also": "existing-one"})

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "sample.md").read_text()
        self.assertIn("see-also: existing-one", domain_text)

    def test_rejects_duplicate_id(self):
        self.write_domain()

        result = self.add(id="existing-one")

        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)

    def test_rejects_unknown_domain(self):
        self.write_domain()

        result = self.add(domain="nope")

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown domain", result.stderr)

    def test_condition_is_required(self):
        self.write_domain()

        result = self.run_command([
            "add-principle", "--domain", "sample", "--id", "new-one", "--rule", "R",
            "--reason", "Why.", "--provenance", "p",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("--condition", result.stderr)

    def test_brand_new_domain_reconciles_without_manual_retro_done(self):
        self.write_domain()
        self.add()  # register "sample" too, so verify checks every domain in the dir, not just fresh
        (self.root / "corpora" / "domains" / "fresh.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: fresh\n\n```yaml\nlast-retrospective: none\n\n"
            "principles:\n\nkilled:\n```\n"
        )

        result = self.add(domain="fresh", id="first-ever")

        self.assertEqual(result.returncode, 0, result.stderr)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_multiple_additions_to_same_domain_stay_reconciled(self):
        self.write_domain()

        self.add(id="one")
        self.add(id="two")
        result = self.add(id="three")

        self.assertEqual(result.returncode, 0, result.stderr)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        domain_text = (self.root / "corpora" / "domains" / "sample.md").read_text()
        for entry_id in ("one", "two", "three"):
            self.assertIn(f"id: {entry_id}", domain_text)


class RatifyImportCandidateTest(CorpusCommandTestCase):
    """ratify-import-candidate: the scripted counterpart to kernel.md's manual "Write-back
    format" — consumes an entry already queued by import-candidate/import-default-pool."""

    def setUp(self):
        super().setUp()
        self.source_dir = self.root / "source-domains"
        self.source_dir.mkdir()
        (self.source_dir / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\n"
            "conventions:\n\n"
            '- id: a-convention\n  rule: "Do X."\n  reason: "Because Y."\n\n'
            "principles:\n\n"
            '- id: a-principle\n  rule: "Do Z."\n  condition: "When W."\n  reason: "Because V."\n\n'
            "killed:\n```\n"
        )
        (self.source_dir / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n"
            "- id: a-principle\n  domain: widgets\n  provenance: \"2026-01-01, some task.\"\n```\n"
        )
        (self.root / "corpora" / "domains" / "sample.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: sample\n\n```yaml\nlast-retrospective: none\n\n"
            'principles:\n\n- id: existing-one\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\n'
            "killed:\n```\n"
        )
        (self.root / "corpora" / "domains" / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n- id: existing-one\n  domain: sample\n"
            '  provenance: "2026-01-01, pre-existing."\n```\n\n'
            "<!-- corpus-script:begin -->\n\n```yaml\ncounters: []\nefficacy: []\n"
            "co-occurrence: []\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
        )

    def queue(self, entry_id="a-principle"):
        result = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "widgets", "--id", entry_id,
        ])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_writes_back_and_consumes_candidate(self):
        self.queue("a-principle")

        result = self.run_command([
            "ratify-import-candidate", "--id", "a-principle", "--as-domain", "sample",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "sample.md").read_text()
        self.assertIn("id: a-principle", domain_text)
        self.assertIn('condition: "When W."', domain_text)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("imported-from:", audit_text)
        self.assertIn("domain: widgets", audit_text)
        candidates_text = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertNotIn("id: a-principle", candidates_text)
        self.assertIn("candidates: []", candidates_text)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_honors_as_id_rename(self):
        self.queue("a-principle")

        result = self.run_command([
            "ratify-import-candidate", "--id", "a-principle",
            "--as-domain", "sample", "--as-id", "renamed",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_text = (self.root / "corpora" / "domains" / "sample.md").read_text()
        self.assertIn("id: renamed", domain_text)
        self.assertNotIn("id: a-principle\n  rule:", domain_text)

    def test_rejects_convention_shaped_candidate(self):
        self.queue("a-convention")

        result = self.run_command([
            "ratify-import-candidate", "--id", "a-convention", "--as-domain", "sample",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("convention", result.stderr)
        candidates_text = (self.root / "corpora" / "import-candidates.md").read_text()
        self.assertIn("id: a-convention", candidates_text)  # left queued, not consumed

    def test_rejects_unknown_candidate_id(self):
        self.queue("a-principle")

        result = self.run_command([
            "ratify-import-candidate", "--id", "does-not-exist", "--as-domain", "sample",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("no candidate", result.stderr)

    def test_rejects_id_collision_at_destination(self):
        self.queue("a-principle")

        result = self.run_command([
            "ratify-import-candidate", "--id", "a-principle",
            "--as-domain", "sample", "--as-id", "existing-one",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)


class AdoptDomainShellTest(CorpusCommandTestCase):
    """adopt-domain-shell: create a container-only domain (frontmatter copied verbatim + empty
    principles:/killed: body) so a plugin's judgment face can be staged into a project that doesn't
    yet have the domain — the container the ratify gate needs, created without writing any
    principle or audit entry itself."""

    def setUp(self):
        super().setUp()
        self.source_dir = self.root / "source-domains"
        self.source_dir.mkdir()

    def write_source(self, name="newdom", principle_id="a-principle"):
        (self.source_dir / f"{name}.md").write_text(
            "---\nsubject: process\nposture: guardrail\nunits-of-work: [route-work]\n"
            f"universal: false\n---\n\n# Domain: {name}\n\n```yaml\n"
            "conventions:\n\n"
            "principles:\n\n"
            f'- id: {principle_id}\n  rule: "Do Z."\n  condition: "When W."\n  reason: "Because V."\n\n'
            "killed:\n```\n"
        )
        (self.source_dir / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n"
            f"- id: {principle_id}\n  domain: {name}\n  provenance: \"2026-01-01, some task.\"\n```\n"
        )

    def write_project_audit(self):
        (self.root / "corpora" / "domains" / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n```\n\n"
            "<!-- corpus-script:begin -->\n\n```yaml\ncounters: []\nefficacy: []\n"
            "co-occurrence: []\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
        )

    def test_creates_valid_container_from_source(self):
        self.write_source("newdom")

        result = self.run_command(["adopt-domain-shell", "--source", str(self.source_dir / "newdom.md")])

        self.assertEqual(result.returncode, 0, result.stderr)
        shell = self.root / "corpora" / "domains" / "newdom.md"
        self.assertTrue(shell.exists())
        text = shell.read_text()
        # frontmatter copied verbatim
        self.assertIn("subject: process", text)
        self.assertIn("units-of-work: [route-work]", text)
        # container only: named after the stem, empty principles + killed, no source principle
        self.assertIn("# Domain: newdom", text)
        self.assertIn("last-retrospective: none", text)
        self.assertIn("principles:", text)
        self.assertIn("killed:", text)
        self.assertNotIn("a-principle", text)
        # a valid domain per lint-domains
        lint = self.run_command(["lint-domains", "--domains-dir", str(self.root / "corpora" / "domains")])
        self.assertEqual(lint.returncode, 0, lint.stderr)

    def test_writes_no_audit_entry(self):
        self.write_source("newdom")
        self.write_project_audit()
        before = (self.root / "corpora" / "domains" / "audit.md").read_text()

        result = self.run_command(["adopt-domain-shell", "--source", str(self.source_dir / "newdom.md")])

        self.assertEqual(result.returncode, 0, result.stderr)
        after = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertEqual(before, after)  # container creation never touches the audit ledger

    def test_idempotent_does_not_clobber_existing_domain(self):
        # a domain that already holds a ratified principle must survive a second adopt untouched
        existing = self.root / "corpora" / "domains" / "newdom.md"
        existing.write_text(
            "---\nsubject: process\nposture: guardrail\nunits-of-work: [route-work]\n"
            "universal: false\n---\n\n# Domain: newdom\n\n```yaml\nlast-retrospective: none\n\n"
            'principles:\n\n- id: already-ratified\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\n'
            "killed:\n```\n"
        )
        self.write_source("newdom")

        result = self.run_command(["adopt-domain-shell", "--source", str(self.source_dir / "newdom.md")])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped", result.stdout)
        self.assertIn("already-ratified", existing.read_text())  # not overwritten

    def test_shell_is_fillable_by_ratify_import_candidate(self):
        # the key end-to-end: adopt the container, then ratify a candidate that targets it
        self.write_source("newdom", principle_id="a-principle")
        self.write_project_audit()

        adopt = self.run_command(["adopt-domain-shell", "--source", str(self.source_dir / "newdom.md")])
        self.assertEqual(adopt.returncode, 0, adopt.stderr)

        queue = self.run_command([
            "import-candidate", "--source", str(self.source_dir),
            "--domain", "newdom", "--id", "a-principle",
        ])
        self.assertEqual(queue.returncode, 0, queue.stderr)
        # candidate carries domains: [newdom] — ratify resolves the destination from it, no --as-domain
        ratify = self.run_command(["ratify-import-candidate", "--id", "a-principle"])

        self.assertEqual(ratify.returncode, 0, ratify.stderr)
        shell_text = (self.root / "corpora" / "domains" / "newdom.md").read_text()
        self.assertIn("id: a-principle", shell_text)
        self.assertIn('condition: "When W."', shell_text)
        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)


class MigrateDomainsTest(CorpusCommandTestCase):
    """praxis-plugin/phases/domain-repo-migration.md: a one-time materialization of a pre-dissolution
    project's live seed/project merge into its own corpora/domains/ — writes directly (no
    candidate/gate review), since it isn't proposing new judgment, only making already-active
    judgment explicit."""

    def setUp(self):
        super().setUp()
        self.source_dir = self.root / "source-domains"
        self.source_dir.mkdir()
        (self.source_dir / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: 2026-01-01\n\n"
            "conventions:\n\n"
            '- id: seed-convention\n  rule: "Do X."\n  reason: "Because Y."\n\n'
            "principles:\n\n"
            '- id: seed-principle\n  rule: "Do Z."\n  condition: "When W."\n  reason: "Because V."\n\n'
            "killed:\n```\n"
        )
        (self.root / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nlanguage: typescript\nhas-ui: no\n"
        )

    def test_migrates_seed_content_into_project_domain_file(self):
        result = self.run_command(["migrate-domains", "--source", str(self.source_dir),
                                    "--domains", "widgets"])

        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertIn("id: seed-principle", text)
        self.assertIn("id: seed-convention", text)
        self.assertIn("subject: coding", text)  # frontmatter carried over

    def test_preserves_existing_project_content_and_ids(self):
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: none\n\n"
            "conventions:\n\nprinciples:\n\n"
            '- id: project-principle\n  rule: "Project rule."\n  condition: "Project condition."\n  reason: "Project reason."\n\n'
            "killed:\n```\n"
        )

        result = self.run_command(["migrate-domains", "--source", str(self.source_dir),
                                    "--domains", "widgets"])

        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertIn("id: project-principle", text)
        self.assertIn("id: seed-principle", text)

    def test_does_not_duplicate_an_id_already_present_in_project(self):
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: none\n\n"
            "conventions:\n\nprinciples:\n\n"
            '- id: seed-principle\n  rule: "Overridden rule."\n  condition: "Overridden condition."\n  reason: "Overridden reason."\n\n'
            "killed:\n```\n"
        )

        result = self.run_command(["migrate-domains", "--source", str(self.source_dir),
                                    "--domains", "widgets"])

        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertEqual(text.count("id: seed-principle"), 1)
        self.assertIn("Overridden rule.", text)  # project's own version wins, not seed's

    def test_records_migration_provenance_in_project_audit(self):
        result = self.run_command(["migrate-domains", "--source", str(self.source_dir),
                                    "--domains", "widgets"])

        self.assertEqual(result.returncode, 0, result.stderr)
        audit = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("id: seed-principle", audit)
        self.assertIn("type: migrated-from-seed", audit)

    def test_measure_and_verify_are_clean_immediately_after_migration(self):
        self.run_command(["migrate-domains", "--source", str(self.source_dir), "--domains", "widgets"])
        self.run_command(["measure"])

        result = self.run_command(["verify"])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reconciled", result.stdout)

    def test_lint_domains_passes_on_migrated_output(self):
        self.run_command(["migrate-domains", "--source", str(self.source_dir), "--domains", "widgets"])

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-domains", "--domains-dir",
             str(self.root / "corpora" / "domains")],
            text=True, capture_output=True, check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_domains_selects_by_project_shape(self):
        (self.source_dir / "coding-nextjs-like.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "applies-when:\n  - framework: nextjs\nuniversal: false\n---\n\n"
            "# Domain: coding-nextjs-like\n\n```yaml\nlast-retrospective: none\n\n"
            "conventions:\n\nprinciples:\n\n"
            '- id: nextjs-only\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\nkilled:\n```\n'
        )
        # project shape has no framework: nextjs, so coding-nextjs-like should not be pulled in,
        # while widgets (no applies-when) always matches
        result = self.run_command(["migrate-domains", "--source", str(self.source_dir)])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "corpora" / "domains" / "widgets.md").exists())
        self.assertFalse((self.root / "corpora" / "domains" / "coding-nextjs-like.md").exists())

class MigrateChainTest(CorpusCommandTestCase):
    """`migrate`: the ordered, stamped schema-migration chain — kill-log relocation is 001."""

    def write_pool(self, schema_line=""):
        (self.root / "corpora" / "config.md").write_text(
            f"# Config\n{schema_line}\n## project-shape\nlanguage: typescript\nhas-ui: no\n")
        (self.root / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nprinciples:\n\n"
            '- id: live-one\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\n'
            "killed:\n\n"
            '- id: old-kill\n  rule: "Old."\n  kill_type: quality\n'
            '  reason_killed: "Wrong."\n  killed: 2026-07-01\n```\n'
        )
        (self.root / "corpora" / "domains" / "audit.md").write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n- id: live-one\n  domain: widgets\n"
            '  provenance: "Pre-existing."\n```\n\n'
            "<!-- corpus-script:begin -->\n<!-- corpus-script:end -->\n"
        )

    def run_command(self, command):
        return subprocess.run([sys.executable, str(SCRIPT), *command],
                              cwd=str(self.root), text=True, capture_output=True, check=False)

    def test_verify_refuses_stale_pool_then_migrate_fixes_it(self):
        self.write_pool()

        verify = self.run_command(["verify"])
        self.assertEqual(verify.returncode, 1)
        self.assertIn("POOL SCHEMA STALE", verify.stdout)

        result = self.run_command(["migrate"])
        self.assertEqual(result.returncode, 0, result.stderr)
        config_text = (self.root / "corpora" / "config.md").read_text()
        self.assertIn("schema-version: 1", config_text)
        widgets_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertNotIn("- id: old-kill", widgets_text)
        audit_text = (self.root / "corpora" / "domains" / "audit.md").read_text()
        self.assertIn("- id: old-kill", audit_text.split("kills:", 1)[1])

    def test_migrate_is_a_noop_when_current(self):
        self.write_pool(schema_line="\nschema-version: 1\n")

        result = self.run_command(["migrate"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already current", result.stdout)
        widgets_text = (self.root / "corpora" / "domains" / "widgets.md").read_text()
        self.assertIn("- id: old-kill", widgets_text)


class MigrateKillLogTest(unittest.TestCase):
    """migrate-kill-log: the one-time per-pool relocation of working-file killed: entries into
    the audit file's kill log (kills live in audit.md since 2026-08-07)."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.domains_dir = self.root / "domains"
        self.domains_dir.mkdir()
        self.audit_path = self.root / "audit.md"
        self.audit_path.write_text(
            "# Audit\n\n```yaml\nprovenance:\n\n- id: active-one\n  domain: test-domain\n"
            '  provenance: "Some provenance."\n```\n\n'
            "<!-- corpus-script:begin -->\n\n```yaml\ncounters: []\nefficacy: []\n"
            "co-occurrence: []\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def write_domain(self, name, killed_ids):
        killed_block = "\n\n".join(
            f'- id: {kid}\n  rule: "Some rejected rule."\n  kill_type: quality\n  reason_killed: "Reason."'
            for kid in killed_ids
        )
        section = f"killed:\n\n{killed_block}\n```\n" if killed_ids else "killed:\n```\n"
        (self.domains_dir / f"{name}.md").write_text(
            f"# Domain: {name}\n\n```yaml\nprinciples:\n\n"
            '- id: active-one\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n\n' + section
        )

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *command],
            text=True, capture_output=True, check=False,
        )

    def migrate(self):
        return self.run_command([
            "migrate-kill-log", "--domains-dir", str(self.domains_dir), "--audit", str(self.audit_path),
        ])

    def test_moves_kills_to_audit_log_and_empties_working_files(self):
        self.write_domain("alpha", ["dead-a", "dead-b"])
        self.write_domain("beta", ["dead-c"])

        result = self.migrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("alpha", "beta"):
            text = (self.domains_dir / f"{name}.md").read_text()
            self.assertNotIn("dead-", text.split("killed:", 1)[1])
            self.assertIn("- id: active-one", text)  # live entries untouched
        audit_text = self.audit_path.read_text()
        kill_log = audit_text.split("kills:", 1)[1]
        for kid, domain in (("dead-a", "alpha"), ("dead-b", "alpha"), ("dead-c", "beta")):
            self.assertIn(f"- id: {kid}", kill_log)
        self.assertIn("domain: alpha", kill_log)
        self.assertIn("domain: beta", kill_log)
        self.assertIn('reason_killed: "Reason."', kill_log)
        # provenance fence untouched, still ahead of the script block
        self.assertIn("provenance:", audit_text.split("<!-- corpus-script:begin", 1)[0])

    def test_noop_when_no_working_file_carries_kills(self):
        self.write_domain("alpha", [])

        result = self.migrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing to migrate", result.stdout)
        self.assertNotIn("kills:", self.audit_path.read_text())

    def test_second_run_is_a_noop(self):
        self.write_domain("alpha", ["dead-a"])
        self.migrate()

        result = self.migrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing to migrate", result.stdout)
        self.assertEqual(self.audit_path.read_text().split("kills:", 1)[1].count("- id: dead-a"), 1)

    def test_tolerates_working_file_with_no_closing_fence(self):
        # Seen in the wild (FAMOUS): a domain file whose yaml fence never closes after killed:.
        self.write_domain("alpha", ["dead-a"])
        path = self.domains_dir / "alpha.md"
        path.write_text(path.read_text().rsplit("```", 1)[0].rstrip("\n") + "\n")

        result = self.migrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        alpha_text = path.read_text()
        self.assertNotIn("dead-a", alpha_text)
        self.assertTrue(alpha_text.rstrip().endswith("killed:"))
        self.assertIn("- id: dead-a", self.audit_path.read_text().split("kills:", 1)[1])

    def test_partial_run_recovery_does_not_duplicate_audit_entries(self):
        # Simulate the failure mode the two-phase order guards against: kills already in the
        # audit log AND still present in a working file (a strip that never landed). A re-run
        # must strip without re-appending.
        self.write_domain("alpha", ["dead-a"])
        self.migrate()
        self.write_domain("alpha", ["dead-a"])  # restore the working-file copy

        result = self.migrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("dead-a", (self.domains_dir / "alpha.md").read_text())
        self.assertEqual(self.audit_path.read_text().split("kills:", 1)[1].count("- id: dead-a"), 1)

    def test_malformed_pool_aborts_before_any_write(self):
        # A file with killed entries but an unparseable id line must not strand the pool
        # half-migrated: phase 1 is read-only, so every other file stays untouched on abort.
        # (No such abort path currently exists for content this parser accepts — this guards the
        # ordering property with the one input that still fails: an unreadable file.)
        self.write_domain("alpha", ["dead-a"])
        self.write_domain("beta", ["dead-b"])
        (self.domains_dir / "beta.md").chmod(0o000)
        try:
            result = self.migrate()
            self.assertNotEqual(result.returncode, 0)
            alpha_text = (self.domains_dir / "alpha.md").read_text()
            self.assertIn("dead-a", alpha_text)  # untouched — nothing wrote before the abort
            self.assertNotIn("kills:", self.audit_path.read_text())
        finally:
            (self.domains_dir / "beta.md").chmod(0o644)


class RootBoundaryTest(unittest.TestCase):
    """proposals/domain-repo-import.md, monorepo section: nearest-ancestor resolution finds which
    corpora/config.md governs a file, the same model tsconfig.json/package.json resolution uses;
    check-root-boundary is the mechanical split signal for a task spanning two roots."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "corpora").mkdir(parents=True)
        (self.root / "corpora" / "config.md").write_text("# Config\n")
        (self.root / "admin" / "corpora").mkdir(parents=True)
        (self.root / "admin" / "corpora" / "config.md").write_text("# Config\n")
        (self.root / "src").mkdir()
        (self.root / "admin" / "pages").mkdir(parents=True)
        (self.root / "src" / "foo.ts").write_text("")
        (self.root / "admin" / "pages" / "bar.tsx").write_text("")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *command],
            text=True, capture_output=True, check=False,
        )

    def test_resolve_root_finds_outer_root(self):
        result = self.run_command(["resolve-root", "--file", str(self.root / "src" / "foo.ts")])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root))

    def test_resolve_root_prefers_nearest_ancestor_over_outer_root(self):
        result = self.run_command(["resolve-root", "--file", str(self.root / "admin" / "pages" / "bar.tsx")])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root / "admin"))

    def test_resolve_root_reports_none_above_a_file_with_no_corpora_root(self):
        with tempfile.TemporaryDirectory() as outside:
            result = self.run_command(["resolve-root", "--file", str(Path(outside) / "f.ts")])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no corpora root found", result.stdout)

    def test_check_root_boundary_passes_for_single_root(self):
        result = self.run_command(["check-root-boundary", "--files",
                                    f"{self.root / 'src' / 'foo.ts'}"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_check_root_boundary_fails_when_files_span_two_roots(self):
        result = self.run_command(["check-root-boundary", "--files",
                                    f"{self.root / 'src' / 'foo.ts'},{self.root / 'admin' / 'pages' / 'bar.tsx'}"])

        self.assertEqual(result.returncode, 2)
        self.assertIn("spans multiple corpora roots", result.stderr)
        self.assertIn(str(self.root), result.stderr)
        self.assertIn(str(self.root / "admin"), result.stderr)


class NamedRootDiscoveryTest(unittest.TestCase):
    """list-roots / resolve-root --name / --root-name: the downward-discovery counterpart to
    resolve-root --file's upward walk — dispatching deliberately into a formalized section of the
    same project (kernel.md, 'Monorepo root resolution'), not just resolving from a touched file."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "corpora").mkdir(parents=True)
        (self.root / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nlanguage: typescript\n"
        )
        (self.root / "admin" / "corpora").mkdir(parents=True)
        (self.root / "admin" / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nname: admin\nlanguage: typescript\n"
        )
        (self.root / "node_modules" / "some-pkg" / "corpora").mkdir(parents=True)
        (self.root / "node_modules" / "some-pkg" / "corpora" / "config.md").write_text("# Config\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *command],
            text=True, capture_output=True, check=False,
        )

    def test_list_roots_finds_both_and_skips_node_modules(self):
        result = self.run_command(["list-roots", "--search-from", str(self.root)])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"admin: {self.root / 'admin'}", result.stdout)
        self.assertIn(f"{self.root.name}: {self.root}", result.stdout)
        self.assertNotIn("node_modules", result.stdout)

    def test_resolve_root_by_declared_name(self):
        result = self.run_command([
            "resolve-root", "--name", "admin", "--search-from", str(self.root),
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root / "admin"))

    def test_resolve_root_by_directory_basename_when_no_declared_name(self):
        result = self.run_command([
            "resolve-root", "--name", self.root.name, "--search-from", str(self.root),
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root))

    def test_resolve_root_unknown_name_lists_available(self):
        result = self.run_command([
            "resolve-root", "--name", "nonexistent", "--search-from", str(self.root),
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("no corpora root named 'nonexistent'", result.stderr)
        self.assertIn("admin", result.stderr)

    def test_resolve_root_requires_file_or_name(self):
        result = self.run_command(["resolve-root"])

        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --file", result.stderr)

    def test_top_level_root_name_dispatches_into_named_root(self):
        (self.root / "admin" / "corpora" / "domains").mkdir(parents=True)
        (self.root / "admin" / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: none\n\n"
            "conventions:\n\nprinciples:\n\nkilled:\n```\n"
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root-name", "admin", "manifest"],
            text=True, capture_output=True, check=False, cwd=str(self.root),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("widgets", result.stdout)

    def test_root_name_and_for_file_are_mutually_exclusive(self):
        result = self.run_command([
            "--for-file", str(self.root / "corpora" / "config.md"),
            "--root-name", "admin", "verify",
        ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("mutually exclusive", result.stderr)


class ForFileRootResolutionTest(unittest.TestCase):
    """--for-file resolves --root automatically (kernel.md, 'Monorepo root resolution') so no
    session has to work out which corpora root governs a task before invoking corpus.py."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "corpora" / "domains").mkdir(parents=True)
        (self.root / "corpora" / "config.md").write_text("# Config\n\nschema-version: 1\n\n## project-shape\nhas-ui: no\n")
        (self.root / "admin" / "corpora" / "domains").mkdir(parents=True)
        (self.root / "admin" / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nhas-ui: yes\n"
        )
        (self.root / "admin" / "corpora" / "domains" / "widgets.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\n"
            "universal: false\n---\n\n# Domain: widgets\n\n```yaml\nlast-retrospective: none\n\n"
            "conventions:\n\nprinciples:\n\nkilled:\n```\n"
        )
        (self.root / "admin" / "src").mkdir(parents=True)
        (self.root / "admin" / "src" / "foo.ts").write_text("")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *command],
            text=True, capture_output=True, check=False,
        )

    def test_for_file_resolves_to_nested_root(self):
        result = self.run_command([
            "--for-file", str(self.root / "admin" / "src" / "foo.ts"), "manifest",
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("widgets", result.stdout)

    def test_plain_root_does_not_see_nested_root_domains(self):
        result = self.run_command(["--root", str(self.root), "manifest"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("widgets", result.stdout)

    def test_for_file_outside_any_root_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as outside:
            result = self.run_command([
                "--for-file", str(Path(outside) / "f.ts"), "verify",
            ])

        self.assertEqual(result.returncode, 2)
        self.assertIn("no corpora root found above", result.stderr)


class DomainFrontmatterTest(unittest.TestCase):
    """kernel.md, 'Spawns: stance + composition' — lint-domains works on any --domains-dir, same
    as kill-report, so a process layer's data source is validated independent of any one project."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.domains_dir = Path(self.tempdir.name) / "domains"
        self.domains_dir.mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def write_domain(self, name, frontmatter, body='principles:\n\n- id: r\n  rule: "R"\n  condition: "C"\n  reason: "Why."\n'):
        (self.domains_dir / f"{name}.md").write_text(
            frontmatter + f"\n# Domain: {name}\n\n```yaml\n{body}```\n"
        )

    def run_lint(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "lint-domains", "--domains-dir", str(self.domains_dir)],
            text=True, capture_output=True, check=False,
        )

    def test_valid_frontmatter_passes(self):
        self.write_domain("coding-general", "---\nsubject: coding\nposture: guardrail\n"
                           "units-of-work: [implement-feature]\nuniversal: false\n---\n\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_frontmatter_fails(self):
        (self.domains_dir / "no-frontmatter.md").write_text("# Domain: no-frontmatter\n\n```yaml\nprinciples:\n```\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2)
        self.assertIn("no frontmatter", result.stderr)

    def test_invalid_subject_fails(self):
        self.write_domain("bad-subject", "---\nsubject: backend\nposture: guardrail\n"
                           "units-of-work: [implement-feature]\nuniversal: false\n---\n\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2)
        self.assertIn("subject", result.stderr)

    def test_empty_units_of_work_without_universal_fails(self):
        self.write_domain("empty-uow", "---\nsubject: coding\nposture: guardrail\nuniversal: false\n---\n\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2)
        self.assertIn("units-of-work", result.stderr)

    def test_universal_domain_without_units_of_work_passes(self):
        self.write_domain("interviewing", "---\nsubject: process\nposture: guardrail\nuniversal: true\n---\n\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_applies_when_field_fails(self):
        self.write_domain("bad-condition", "---\nsubject: coding\nposture: guardrail\n"
                           "applies-when:\n  - editor: [vim]\nunits-of-work: [implement-feature]\nuniversal: false\n---\n\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2)
        self.assertIn("applies-when", result.stderr)


class SelectionTest(CorpusCommandTestCase):
    """`select` evaluates real seed-domain frontmatter (scripts/corpus.py's skill_root() resolves
    to this repo) against a project's corpora/config.md — the deterministic call a process layer
    makes instead of reading domain preambles."""

    def write_shape(self, **fields):
        lines = ["# Config", "", "## project-shape"]
        lines += [f"{k}: {v}" for k, v in fields.items()]
        (self.root / "corpora" / "config.md").write_text("\n".join(lines) + "\n")

    def test_select_implement_feature_for_nextjs_typescript_project(self):
        self.write_shape(language="typescript", framework="next.js", **{"has-ui": "yes"}, styling="tailwind")

        result = self.run_command(["select", "--unit-of-work", "implement-feature", "--json",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        # css stays in corpora-core (a coding/styling-engine domain, not a design one).
        for expected in ("coding-general", "coding-ts", "coding-nextjs", "coding-react", "css"):
            self.assertIn(expected, domains)
        # task-shape separation (kernel.md): implement-feature never pulls in dependency-management
        self.assertNotIn("dependency-management", domains)
        # subject separation: a coding unit-of-work never pulls in a design domain
        self.assertNotIn("color", domains)
        # universal domains always ride along: prose-craft stays in corpora-core; interviewing moved
        # to plugins/routing/. MERGED (seed ∪ plugins) supplies both, as a plugged-in project sees them.
        self.assertIn("interviewing", domains)
        self.assertIn("prose-craft", domains)

    def test_select_migrate_dependencies_excludes_coding_general(self):
        self.write_shape(language="typescript", framework="next.js", **{"has-ui": "yes"}, styling="tailwind")

        result = self.run_command(["select", "--unit-of-work", "migrate-dependencies", "--json",
                                    "--domains-dir", str(SEED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        self.assertIn("dependency-management", domains)
        self.assertNotIn("coding-general", domains)

    def test_select_design_ui_surface_for_has_ui_project(self):
        self.write_shape(language="typescript", framework="next.js", **{"has-ui": "yes"}, styling="tailwind")

        result = self.run_command(["select", "--unit-of-work", "design-ui-surface", "--json",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        # color/design-method now ship from the uiux plugin; present here because MERGED models a
        # UI project that imported it. recoverability is the design domain that stayed in core.
        self.assertIn("color", domains)
        self.assertIn("design-method", domains)
        self.assertIn("recoverability", domains)
        self.assertNotIn("coding-general", domains)

    def test_select_returns_empty_set_for_unmatched_unit_of_work(self):
        self.write_shape(**{"has-ui": "no"})

        result = self.run_command(["select", "--unit-of-work", "design-ui-surface", "--json",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        self.assertNotIn("color", domains)
        # universal domains still ride along even when nothing else matches
        self.assertIn("interviewing", domains)

    def test_select_bootstrap_ui_surface_is_narrower_than_ongoing_ui_design(self):
        self.write_shape(language="typescript", framework="next.js", **{"has-ui": "yes"}, styling="tailwind")

        result = self.run_command(["select", "--unit-of-work", "bootstrap-ui-surface", "--json",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        for expected in ("color", "surfaces-elevation", "visual-hierarchy", "motion", "design-method"):
            self.assertIn(expected, domains)
        # the design plugin's `library-init` phase's stated composition excludes these — only ongoing design-ui-surface pulls them in
        for excluded in ("forms-inputs", "lists-selection", "recoverability", "validation-feedback"):
            self.assertNotIn(excluded, domains)

    def test_select_bootstrap_ux_surface_is_narrower_than_ongoing_ux_design(self):
        self.write_shape(language="typescript", framework="next.js", **{"has-ui": "yes"}, styling="tailwind")

        result = self.run_command(["select", "--unit-of-work", "bootstrap-ux-surface", "--json",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        domains = json.loads(result.stdout)["domains"]
        for expected in ("recoverability", "validation-feedback", "lists-selection", "forms-inputs", "design-method"):
            self.assertIn(expected, domains)
        # the design plugin's `library-init` phase's stated composition excludes these — only ongoing design-ux-flow pulls them in
        for excluded in ("ranking-evaluation", "wizards-flows", "color"):
            self.assertNotIn(excluded, domains)


class MissingDomainsDirTest(unittest.TestCase):
    """A freshly-bootstrapped project has no corpora/domains/ yet — only ratified project
    principles ever live there. Read commands must tolerate that; write commands must create it
    lazily instead of requiring an operator workaround (found by literally running the
    bootstrap-then-first-spawn path against a real fresh project, twice)."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "corpora").mkdir(parents=True)
        (self.root / "corpora" / "config.md").write_text(
            "# Config\n\nschema-version: 1\n\n## project-shape\nlanguage: typescript\nframework: next.js\n"
            "has-ui: yes\nstyling: tailwind\n"
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, command):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *command],
            text=True, capture_output=True, check=False,
        )

    def test_select_does_not_require_domains_dir_to_exist(self):
        self.assertFalse((self.root / "corpora" / "domains").exists())

        result = self.run_command(["select", "--unit-of-work", "plan-work",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        # planning relocated to plugins/routing/ and the universal interviewing to plugins/prose/;
        # MERGED (seed ∪ plugins) supplies both, proving select produced output for a unit-of-work
        # without the project's own domains-dir existing.
        self.assertIn("interviewing", result.stdout)
        # read-only: must not have created the directory as a side effect
        self.assertFalse((self.root / "corpora" / "domains").exists())

    def test_verify_does_not_require_domains_dir_to_exist(self):
        result = self.run_command(["verify"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reconciled", result.stdout)

    def test_record_gate_creates_domains_dir_lazily_when_the_domain_file_already_exists(self):
        # Mimics real ordering: write-back creates the working file before record-gate runs.
        domains_dir = self.root / "corpora" / "domains"
        domains_dir.mkdir(parents=True)
        (domains_dir / "example.md").write_text(
            "last-retrospective: none\n\nprinciples:\n\n"
            "- id: example\n  rule: x\n  condition: x\n  reason: x\n\nkilled:\n"
        )

        result = self.run_command(
            ["record-gate", "--domain", "example", "--ratified", "1", "--killed", "0", "--violations", "0"]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((domains_dir / "audit.md").exists())

    def test_add_principle_scaffolds_audit_when_absent(self):
        # The real gap found dogfooding a plugin's judgment face into a fresh project: adopt-domain-shell
        # creates the container but no audit.md, and ratify/add-principle must not fail for want of it.
        domains_dir = self.root / "corpora" / "domains"
        domains_dir.mkdir(parents=True)
        (domains_dir / "example.md").write_text(
            "---\nsubject: process\nposture: guardrail\nuniversal: true\n---\n\n# Domain: example\n\n"
            "```yaml\nprinciples:\nkilled:\n```\n"
        )
        self.assertFalse((domains_dir / "audit.md").exists())

        result = self.run_command([
            "add-principle", "--domain", "example", "--id", "p1",
            "--rule", "r", "--condition", "c", "--reason", "why",
            "--provenance", "2026-08-05, lazy-audit test", "--kind", "judgment",
        ])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        audit = domains_dir / "audit.md"
        self.assertTrue(audit.exists())
        text = audit.read_text()
        self.assertIn("id: p1", text)                     # provenance landed
        self.assertIn("<!-- corpus-script:begin", text)   # scaffold has the counter region too


class CheckCompositionTest(CorpusCommandTestCase):
    def test_mixed_subjects_fail(self):
        # color ships from the uiux plugin now; MERGED models a project that imported it, so the
        # coding+design subject clash is still detectable.
        result = self.run_command(["check-composition", "--domains", "coding-general,color",
                                    "--domains-dir", str(MERGED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 2)
        self.assertIn("mixed subjects", result.stderr)

    def test_universal_domain_alongside_coding_passes(self):
        result = self.run_command(["check-composition", "--domains", "coding-general,interviewing",
                                    "--domains-dir", str(SEED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_emit_spawn_parts_reports_mixed_subject_as_a_problem(self):
        # After the process/judgment split corpora REPORTS composition problems as data (exit 0);
        # praxis gates on them (a praxis-side spawn_prompt test asserts the gate). Corpora only judges.
        import json
        result = self.run_command([
            "emit-spawn-parts", "--domains", "coding-general,color",
            "--domains-dir", str(MERGED_DOMAINS_DIR),
        ])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        problems = json.loads(result.stdout)["problems"]
        self.assertTrue(any("mixed subjects" in p for p in problems))


class ManifestTest(CorpusCommandTestCase):
    def test_manifest_never_leaks_rule_or_reason(self):
        result = self.run_command(["manifest", "--json", "--domains-dir", str(SEED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        payload = json.loads(result.stdout)
        self.assertGreater(len(payload["domains"]), 0)
        for domain in payload["domains"]:
            self.assertNotIn("rule", domain)
            self.assertNotIn("reason", domain)
            for condition in domain["conditions"]:
                self.assertEqual(set(condition), {"id", "condition"})

    def test_manifest_includes_recoverability_conditions(self):
        result = self.run_command(["manifest", "--json", "--domains-dir", str(SEED_DOMAINS_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        payload = json.loads(result.stdout)
        recoverability = next(d for d in payload["domains"] if d["name"] == "recoverability")
        ids = {c["id"] for c in recoverability["conditions"]}
        self.assertIn("recovery-path-replaces-confirmation", ids)


class QueueCommandsTest(CorpusCommandTestCase):
    """The planning domain's queue schema (now in plugins/routing/) states the orchestrator updates
    status/resolved in-place — these queue commands stay in corpora-core and are the mechanical half
    of that rule — closing the same hand-edited-bookkeeping failure the praxis chunk ledger closes for
    unit-of-work accounting (that ledger is now a praxis primitive, chunk_ledger.py)."""

    def write_queue(self, tasks="", questions=""):
        (self.root / "corpora" / "queue.md").write_text(f"""```yaml
capability: "Test capability"
area: "test"
status: active
created: 2026-07-29
updated: 2026-07-29

tasks:
{textwrap.dedent(tasks)}
open-questions:
{textwrap.dedent(questions)}
```
""")

    def default_queue(self):
        self.write_queue(
            tasks="""
              - id: t-01
                title: "First"
                description: "d"
                context: ""
                status: pending
                blocked-by: []
                parallel-ok: false
                concern: implementation
                judgment: settled
                notes: ""

              - id: t-02
                title: "Second"
                description: "d"
                context: ""
                status: pending
                blocked-by: [t-01]
                parallel-ok: false
                concern: implementation
                judgment: settled
                notes: ""
            """,
            questions="""
              - id: q-01
                question: "q"
                blocks: [t-02]
                resolved: false
                answer: ""
            """,
        )

    def test_lint_queue_passes_on_valid_queue(self):
        self.default_queue()

        result = self.run_command(["lint-queue"])

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lint_queue_no_queue_is_a_pass(self):
        result = self.run_command(["lint-queue"])

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lint_queue_catches_unknown_blocked_by_reference(self):
        self.write_queue(
            tasks="""
              - id: t-01
                title: "First"
                description: "d"
                context: ""
                status: pending
                blocked-by: [t-nonexistent]
                parallel-ok: false
                concern: implementation
                judgment: settled
                notes: ""
            """,
            questions="",
        )

        result = self.run_command(["lint-queue"])

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown task id", result.stderr)

    def test_lint_queue_parses_multi_element_blocked_by(self):
        # Edge net for parse_queue's inline list fields: a two-element `blocked-by` must parse
        # into two ids, so a lint over [known, unknown] flags exactly the unknown one.
        self.write_queue(
            tasks="""
              - id: t-01
                title: "First"
                description: "d"
                context: ""
                status: pending
                blocked-by: []
                parallel-ok: false
                concern: implementation
                judgment: settled
                notes: ""

              - id: t-02
                title: "Second"
                description: "d"
                context: ""
                status: pending
                blocked-by: [t-01, t-missing]
                parallel-ok: false
                concern: implementation
                judgment: settled
                notes: ""
            """,
            questions="",
        )

        result = self.run_command(["lint-queue"])

        self.assertEqual(result.returncode, 2)
        self.assertIn("t-missing", result.stderr)
        self.assertNotIn("t-01", result.stderr)

    def test_queue_status_reports_blocked_and_startable(self):
        self.default_queue()

        result = self.run_command(["queue-status"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("t-01: pending — startable now", result.stdout)
        self.assertIn("t-02: pending — blocked by:", result.stdout)
        self.assertIn("q-01: unresolved", result.stdout)

    def test_queue_set_status_updates_in_place_and_reports_unblocked(self):
        self.default_queue()
        self.run_command(["queue-set-status", "--id", "t-01", "--status", "complete"])

        result = self.run_command(["queue-resolve-question", "--id", "q-01", "--answer", "because x"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("now startable: t-02", result.stdout)
        text = (self.root / "corpora" / "queue.md").read_text()
        self.assertIn("resolved: true", text)
        self.assertIn("answer: because x", text)

    def test_queue_set_status_rejects_unknown_task(self):
        self.default_queue()

        result = self.run_command(["queue-set-status", "--id", "t-nope", "--status", "complete"])

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown task id", result.stderr)

    def test_all_tasks_complete_and_questions_resolved_flips_top_level_status(self):
        self.default_queue()
        self.run_command(["queue-set-status", "--id", "t-01", "--status", "complete"])
        self.run_command(["queue-resolve-question", "--id", "q-01", "--answer", "a"])

        self.run_command(["queue-set-status", "--id", "t-02", "--status", "complete"])

        text = (self.root / "corpora" / "queue.md").read_text()
        self.assertIn("status: complete", text.split("tasks:")[0])

    def test_top_level_status_stays_active_while_a_question_is_unresolved(self):
        self.default_queue()
        self.run_command(["queue-set-status", "--id", "t-01", "--status", "complete"])

        self.run_command(["queue-set-status", "--id", "t-02", "--status", "complete"])

        text = (self.root / "corpora" / "queue.md").read_text()
        self.assertIn("status: active", text.split("tasks:")[0])


class RelocateDomainTest(unittest.TestCase):
    """`relocate-domain` moves a domain's working file AND its audit trail (provenance + counter +
    efficacy) between domains-dirs — the scripted form of a plugin extraction's hand-done audit
    surgery. Pure mechanics; the deterministic shortcut that replaces the by-hand splitter."""

    AUDIT = (
        "# Audit — from\n\n```yaml\nprovenance:\n\n"
        "# ---- domain: demo ----\n"
        "- id: demo-one\n  domain: demo\n  provenance: \"origin.\"\n"
        "  history:\n    - date: 2026-01-02\n      type: clarified\n      reason: \"kept verbatim.\"\n\n"
        "# ---- domain: other ----\n"
        "- id: other-one\n  domain: other\n  provenance: \"keep me.\"\n```\n\n"
        "<!-- corpus-script:begin — maintained by scripts/corpus.py; do not edit by hand -->\n\n"
        "## counters (script-maintained)\n\n```yaml\ncounters:\n"
        "  - domain: demo\n    since: 2026-01-01\n    ratified: 3\n"
        "  - domain: other\n    since: 2026-01-02\n    ratified: 1\n"
        "efficacy:\n  - id: demo-one\n    fired: 5\n    violated: 0\n    idle: 0\n"
        "  - id: other-one\n    fired: 2\n    violated: 0\n    idle: 0\n"
        "co-occurrence:\nlibrary-drift:\n  since-last-sync: 0\n```\n\n<!-- corpus-script:end -->\n"
    )
    DOMAIN = ("---\nsubject: design\nuniversal: false\n---\n\n# Domain: demo\n\n"
              "```yaml\nprinciples:\n- id: demo-one\n  rule: r\nkilled:\n```\n")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.from_dir = self.root / "from"
        self.to_dir = self.root / "to"
        self.from_dir.mkdir()
        (self.from_dir / "demo.md").write_text(self.DOMAIN)
        (self.from_dir / "audit.md").write_text(self.AUDIT)

    def tearDown(self):
        self.tmp.cleanup()

    def run_relocate(self, extra=()):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), "relocate-domain",
             "--domain", "demo", "--from-dir", str(self.from_dir), "--to-dir", str(self.to_dir), *extra],
            text=True, capture_output=True, check=False,
        )

    def test_moves_working_file_and_scaffolds_destination_audit(self):
        r = self.run_relocate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.from_dir / "demo.md").exists())
        self.assertTrue((self.to_dir / "demo.md").exists())
        self.assertTrue((self.to_dir / "audit.md").exists())          # created from nothing

    def test_source_audit_loses_only_the_moved_domain(self):
        self.run_relocate()
        src = (self.from_dir / "audit.md").read_text()
        self.assertNotIn("id: demo-one", src)
        self.assertNotIn("domain: demo", src)
        self.assertIn("id: other-one", src)                            # sibling untouched
        self.assertIn("domain: other", src)

    def test_destination_receives_provenance_counter_and_efficacy(self):
        self.run_relocate()
        dst = (self.to_dir / "audit.md").read_text()
        self.assertIn("id: demo-one", dst)
        self.assertIn("# ---- domain: demo ----", dst)                 # section header travels
        self.assertIn("kept verbatim.", dst)                           # history stanza travels verbatim
        self.assertIn("ratified: 3", dst)                              # counter preserved
        # efficacy row for the domain's principle moved; sibling's did not
        self.assertRegex(dst, r"id: demo-one\n\s+fired: 5")
        self.assertNotIn("other-one", dst)

    def test_both_audits_stay_machine_parseable(self):
        self.run_relocate()
        for audit, dir_ in ((self.from_dir / "audit.md", self.from_dir),
                            (self.to_dir / "audit.md", self.to_dir)):
            m = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(self.root), "measure",
                 "--domains-dir", str(dir_), "--audit", str(audit)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(m.returncode, 0, m.stderr)

    def test_refuses_to_overwrite_existing_destination(self):
        self.to_dir.mkdir()
        (self.to_dir / "demo.md").write_text("already here\n")
        r = self.run_relocate()
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((self.from_dir / "demo.md").exists())          # source left intact on refusal

    def test_missing_source_domain_fails(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), "relocate-domain",
             "--domain", "nope", "--from-dir", str(self.from_dir), "--to-dir", str(self.to_dir)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()


class DottedCorporaDirTest(unittest.TestCase):
    """`.corpora/` is the standard project-state dir; bare `corpora/` stays recognized, and a
    `domains-dir:` config key can point the pool elsewhere (the self-hosting repo's shape)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("corpus_mod", SCRIPT)
        cls.corpus = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.corpus)

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_dotted_config_wins_and_scopes_state_paths(self):
        (self.root / ".corpora").mkdir()
        (self.root / ".corpora" / "config.md").write_text("## project-shape\nlanguage: python\n")
        p = self.corpus.Project(str(self.root))
        self.assertEqual(p.config_path, str(self.root / ".corpora" / "config.md"))
        self.assertEqual(p.domains_dir, str(self.root / ".corpora" / "domains"))
        self.assertEqual(p.queue_path, str(self.root / ".corpora" / "queue.md"))

    def test_legacy_config_still_resolves(self):
        (self.root / "corpora").mkdir()
        (self.root / "corpora" / "config.md").write_text("## project-shape\nlanguage: python\n")
        p = self.corpus.Project(str(self.root))
        self.assertEqual(p.config_path, str(self.root / "corpora" / "config.md"))
        self.assertEqual(p.domains_dir, str(self.root / "corpora" / "domains"))

    def test_domains_dir_config_key_redirects_pool(self):
        (self.root / ".corpora").mkdir()
        (self.root / ".corpora" / "config.md").write_text(
            "## project-shape\nlanguage: python\ndomains-dir: corpora/domains\n")
        (self.root / "corpora" / "domains").mkdir(parents=True)
        (self.root / "corpora" / "domains" / "d.md").write_text(
            "---\nsubject: coding\nposture: guardrail\nuniversal: true\n---\n# Domain: d\n"
            "```yaml\nprinciples:\nkilled:\n```\n")
        p = self.corpus.Project(str(self.root))
        self.assertEqual(p.domains_dir, str(self.root / "corpora" / "domains"))
        self.assertIn("d", p.domain_files())
        # audit rides the redirected pool, not the state dir
        self.assertEqual(p.audit_path, str(self.root / "corpora" / "domains" / "audit.md"))

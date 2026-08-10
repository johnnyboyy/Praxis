"""Tests for chunk_ledger — praxis-NATIVE unit-of-work accounting. Praxis reads/writes the ledger
itself; the only engine touch is `compose` (driven against the generic stub). Covers: the native
ledger round-trip, the load-bearing chunk-done-before-handoff-close ordering gate, the handoff-exists
precondition, and both reconciliation failures.
Run: python3 -m unittest discover -s praxis/tests"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chunk_ledger  # noqa: E402
from _stub_engine import write_stub, stub_manifest  # noqa: E402


class LedgerFormatTests(unittest.TestCase):
    """Native serialization round-trip."""

    def test_render_then_parse_round_trips(self):
        entries = [{
            "unit-of-work": "implement-feature", "domains-composed": ["coding-general", "security"],
            "stance": "convergent", "handoff": "h.md", "completed": "2026-08-04", "next": "next-uow",
        }]
        text = chunk_ledger.render_chunks("ws-1", entries)
        tmp = Path(tempfile.mkdtemp())
        try:
            p = tmp / "ws-1.md"
            p.write_text(text)
            workstream, got = chunk_ledger.parse_chunks(p)
            self.assertEqual(workstream, "ws-1")
            self.assertEqual(got[0]["domains-composed"], ["coding-general", "security"])
            self.assertEqual(got[0]["stance"], "convergent")
            self.assertEqual(got[0]["next"], "next-uow")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_tier_and_verification_round_trip(self):
        entries = [{
            "unit-of-work": "implement-feature", "domains-composed": ["coding-general"],
            "stance": "convergent", "handoff": "h.md", "completed": "2026-08-07", "next": None,
            "tier": "sonnet", "verification": "clean",
        }]
        text = chunk_ledger.render_chunks("ws-1", entries)
        self.assertIn("    tier: sonnet", text)
        self.assertIn("    verification: clean", text)
        tmp = Path(tempfile.mkdtemp())
        try:
            p = tmp / "ws-1.md"
            p.write_text(text)
            _, got = chunk_ledger.parse_chunks(p)
            self.assertEqual(got[0]["tier"], "sonnet")
            self.assertEqual(got[0]["verification"], "clean")
            # re-render from the parsed entry stays stable
            self.assertEqual(chunk_ledger.render_chunks("ws-1", got), text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_absent_tier_and_verification_write_no_lines(self):
        entries = [{
            "unit-of-work": "implement-feature", "domains-composed": ["coding-general"],
            "stance": "convergent", "handoff": "h.md", "completed": "2026-08-07", "next": None,
        }]
        text = chunk_ledger.render_chunks("ws-1", entries)
        self.assertNotIn("tier:", text)
        self.assertNotIn("verification:", text)

    def test_reads_a_handwritten_ledger(self):
        sample = (
            "# Chunks\n\nworkstream: legacy\n\n```yaml\nchunks:\n\n"
            "  - unit-of-work: fix-bug\n"
            "    domains-composed: [coding-general, debugging]\n"
            "    stance: convergent\n"
            "    handoff: .praxis/handoffs/fix-bug.md\n"
            "    completed: 2026-07-30\n\n"
            "```\n"
        )
        tmp = Path(tempfile.mkdtemp())
        try:
            p = tmp / "legacy.md"
            p.write_text(sample)
            workstream, entries = chunk_ledger.parse_chunks(p)
            self.assertEqual(workstream, "legacy")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["unit-of-work"], "fix-bug")
            self.assertEqual(entries[0]["domains-composed"], ["coding-general", "debugging"])
            self.assertEqual(chunk_ledger.render_chunks(workstream, entries), sample)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CloseSequenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "proj"
        self.handoffs = self.root / ".praxis" / "handoffs"
        self.handoffs.mkdir(parents=True)
        (self.root / ".praxis" / "chunks").mkdir(parents=True)
        self.stub = write_stub(self.tmp)
        self.manifest = stub_manifest(self.stub)
        self.log = self.tmp / "log.txt"
        os.environ["STUB_LOG"] = str(self.log)
        os.environ.pop("STUB_FAIL", None)
        os.environ.pop("STUB_DOMAINS", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        for k in ("STUB_LOG", "STUB_FAIL", "STUB_DOMAINS"):
            os.environ.pop(k, None)

    def _handoff(self, body: str = "workstream: w\n") -> Path:
        h = self.handoffs / "h.md"
        h.write_text(f"---\n{body}---\n")
        return h

    def _ledger(self) -> Path:
        return self.root / ".praxis" / "chunks" / "w.md"

    def test_close_writes_ledger_then_removes_handoff(self):
        h = self._handoff()  # no domains-loaded → reconciliation (b) skipped
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)
        self.assertEqual(rc, 0)
        self.assertTrue(self._ledger().is_file())
        _, entries = chunk_ledger.parse_chunks(self._ledger())
        self.assertEqual(entries[0]["unit-of-work"], "u")
        self.assertFalse(h.exists())  # handoff closed (debug off → deleted)

    def test_missing_handoff_is_a_precondition_stop_before_anything(self):
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent",
                                str(self.handoffs / "nope.md"), None)
        self.assertEqual(rc, 1)
        self.assertFalse(self._ledger().exists())  # nothing written

    def test_handoff_survives_when_chunk_done_fails_workstream_mismatch(self):
        h = self._handoff("workstream: other\n")  # (a) mismatch → chunk-done fails
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self._ledger().exists())  # ledger never written
        self.assertTrue(h.exists())                # gate held: handoff NOT closed

    def test_domains_loaded_mismatch_fails_and_leaves_handoff(self):
        os.environ["STUB_DOMAINS"] = "coding-general"       # compose returns [coding-general]
        h = self._handoff("workstream: w\ndomains-loaded: [coding-general, security]\n")
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self._ledger().exists())
        self.assertTrue(h.exists())

    def test_domains_loaded_match_closes_cleanly(self):
        os.environ["STUB_DOMAINS"] = "coding-general,security"
        h = self._handoff("workstream: w\ndomains-loaded: [coding-general, security]\n")
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)
        self.assertEqual(rc, 0)
        _, entries = chunk_ledger.parse_chunks(self._ledger())
        self.assertEqual(entries[0]["domains-composed"], ["coding-general", "security"])
        self.assertFalse(h.exists())

    def test_close_with_tier_and_verification_appear_in_ledger(self):
        h = self._handoff()
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None,
                                tier="sonnet", verification="clean")
        self.assertEqual(rc, 0)
        _, entries = chunk_ledger.parse_chunks(self._ledger())
        self.assertEqual(entries[0]["tier"], "sonnet")
        self.assertEqual(entries[0]["verification"], "clean")

    def test_close_without_tier_and_verification_matches_todays_shape(self):
        h = self._handoff()
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)
        self.assertEqual(rc, 0)
        _, entries = chunk_ledger.parse_chunks(self._ledger())
        self.assertNotIn("tier", entries[0])
        self.assertNotIn("verification", entries[0])
        self.assertNotIn("tier:", self._ledger().read_text())
        self.assertNotIn("verification:", self._ledger().read_text())

    def test_close_rejects_invalid_verification_value(self):
        h = self._handoff()
        rc = chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None,
                                verification="bogus")
        self.assertNotEqual(rc, 0)
        self.assertFalse(self._ledger().exists())  # nothing written — rejected before chunk-done ran
        self.assertTrue(h.exists())

    def test_chunk_done_records_composed_domains_from_compose(self):
        os.environ["STUB_DOMAINS"] = "a,b,c"
        h = self._handoff()  # no domains-loaded, so compose result is recorded unreconciled
        chunk_ledger.close(self.manifest, str(self.root), "w", "u", "divergent", str(h), "nxt")
        _, entries = chunk_ledger.parse_chunks(self._ledger())
        self.assertEqual(entries[0]["domains-composed"], ["a", "b", "c"])
        self.assertEqual(entries[0]["next"], "nxt")


class SummaryTests(unittest.TestCase):
    def test_summary_displays_tier_and_verification_when_present(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cdir = tmp / ".praxis" / "chunks"
            cdir.mkdir(parents=True)
            entries = [{"unit-of-work": "u", "domains-composed": ["d1"], "stance": "convergent",
                        "handoff": "h.md", "completed": "2026-08-07", "next": None,
                        "tier": "sonnet", "verification": "clean"}]
            (cdir / "w.md").write_text(chunk_ledger.render_chunks("w", entries))

            class A:
                root = str(tmp)
                workstream = "w"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = chunk_ledger.cmd_summary(A())
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("tier: sonnet", out)
            self.assertIn("verification: clean", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summary_reads_native_ledger(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cdir = tmp / ".praxis" / "chunks"
            cdir.mkdir(parents=True)
            entries = [{"unit-of-work": "u", "domains-composed": ["d1"], "stance": "convergent",
                        "handoff": "h.md", "completed": "2026-08-04", "next": None}]
            (cdir / "w.md").write_text(chunk_ledger.render_chunks("w", entries))

            class A:
                root = str(tmp)
                workstream = "w"
            self.assertEqual(chunk_ledger.cmd_summary(A()), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summary_missing_ledger_returns_1(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            class A:
                root = str(tmp)
                workstream = "nope"
            self.assertEqual(chunk_ledger.cmd_summary(A()), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class NextTests(unittest.TestCase):
    """`next`: the session loop's deterministic next-pointer — native ledger read, no engine touch."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cdir = self.tmp / ".praxis" / "chunks"
        self.cdir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_ledger(self, entries):
        (self.cdir / "w.md").write_text(chunk_ledger.render_chunks("w", entries))

    def _entry(self, uow, nxt):
        return {"unit-of-work": uow, "domains-composed": ["d1"], "stance": "convergent",
                "handoff": "h.md", "completed": "2026-08-05", "next": nxt}

    def test_next_reads_last_entrys_pointer(self):
        self._write_ledger([self._entry("first", "second"), self._entry("second", "third")])
        nxt, note = chunk_ledger.next_unit(str(self.tmp), "w")
        self.assertEqual(nxt, "third")
        self.assertEqual(note, "ok")

    def test_last_entry_without_next_is_at_rest(self):
        self._write_ledger([self._entry("only", None)])
        nxt, note = chunk_ledger.next_unit(str(self.tmp), "w")
        self.assertIsNone(nxt)
        self.assertIn("at rest", note)

    def test_absent_ledger_defers_to_task_source(self):
        nxt, note = chunk_ledger.next_unit(str(self.tmp), "unwritten")
        self.assertIsNone(nxt)
        self.assertIn("task source", note)

    def test_cmd_next_exit_codes(self):
        self._write_ledger([self._entry("first", "second")])

        class Found:
            root = str(self.tmp)
            workstream = "w"

        class Missing:
            root = str(self.tmp)
            workstream = "nope"
        self.assertEqual(chunk_ledger.cmd_next(Found()), 0)
        self.assertEqual(chunk_ledger.cmd_next(Missing()), 1)


class VerifyTests(unittest.TestCase):
    """verify-chunks: recompute compose() for every recorded chunk and flag composition drift a config
    or domain change silently introduced. Rebuilt in praxis (was corpora's verify-chunks) since the
    ledger is a praxis primitive; the only engine touch is the compose hook, driven by the stub."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "proj"
        (self.root / ".praxis" / "handoffs").mkdir(parents=True)
        (self.root / ".praxis" / "chunks").mkdir(parents=True)
        self.stub = write_stub(self.tmp)
        self.manifest = stub_manifest(self.stub)
        os.environ.pop("STUB_LOG", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_DOMAINS", None)

    def _record_chunk(self, domains: str):
        os.environ["STUB_DOMAINS"] = domains
        h = self.root / ".praxis" / "handoffs" / "h.md"
        h.write_text("---\nworkstream: w\n---\n")
        chunk_ledger.close(self.manifest, str(self.root), "w", "u", "convergent", str(h), None)

    def test_reconciled_when_composition_unchanged(self):
        self._record_chunk("a,b")
        rc, problems = chunk_ledger.verify(self.manifest, str(self.root))  # same compose result
        self.assertEqual(rc, 0)
        self.assertEqual(problems, [])

    def test_flags_drift_after_composition_change(self):
        self._record_chunk("a,b")
        os.environ["STUB_DOMAINS"] = "a"  # config/domain change: compose now differs from recorded
        rc, problems = chunk_ledger.verify(self.manifest, str(self.root))
        self.assertEqual(rc, 1)
        self.assertTrue(any("no longer matches" in p for p in problems))

    def test_no_chunks_dir_is_a_pass(self):
        rc, problems = chunk_ledger.verify(self.manifest, str(self.tmp / "empty"))
        self.assertEqual(rc, 0)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gate  # noqa: E402
import journal  # noqa: E402

class TempRoot:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / ".praxis").mkdir()
        return self.root

    def __exit__(self, *a):
        self._tmp.cleanup()

def _frame(root, unit_of_work, *, surface=None, delivery=None, unit="u1"):
    journal.append(root, "unit.proposed", unit=unit, unit_of_work=unit_of_work)
    journal.append(root, "unit.framed", unit=unit, unit_of_work=unit_of_work,
                   surface=surface, delivery=delivery)

class NoUnitTest(unittest.TestCase):
    def test_no_open_unit_is_no_unit(self):
        with TempRoot() as root:
            self.assertEqual(gate.gate_decision(root, str(root / "src" / "x.py")), ("no_unit", None))

    def test_concluded_unit_is_no_unit(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=["src/*"])
            journal.append(root, "unit.done", unit="u1", outcome="result", status="complete")
            self.assertEqual(gate.gate_decision(root, str(root / "src" / "x.py")), ("no_unit", None))

class LeaseSurfaceTest(unittest.TestCase):
    def test_in_surface_edit_is_allowed(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=["src/*"])
            self.assertEqual(gate.gate_decision(root, str(root / "src" / "deep" / "x.py")),
                             ("allow", None))

    def test_out_of_surface_edit_is_denied(self):
        with TempRoot() as root:
            _frame(root, "design-ux-flow", surface=["docs/*", "*.md"])
            verdict, reason = gate.gate_decision(root, str(root / "src" / "app.py"))
            self.assertEqual(verdict, "deny")
            self.assertIn("lease surface", reason)

    def test_none_surface_is_unrestricted(self):
        with TempRoot() as root:
            _frame(root, "debug-issue", surface=None)
            self.assertEqual(gate.gate_decision(root, str(root / "anywhere" / "y.py")),
                             ("allow", None))

    def test_praxis_bookkeeping_allowed_even_out_of_surface(self):
        with TempRoot() as root:
            _frame(root, "design-ux-flow", surface=["docs/*"])
            self.assertEqual(gate.gate_decision(root, str(root / ".praxis" / "chunks" / "w.md")),
                             ("allow", None))

class PayloadReadPreconditionTest(unittest.TestCase):
    def test_spawn_payload_unread_denies_then_allows_after_read(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=None, delivery="spawn")
            target = str(root / "src" / "x.py")
            verdict, reason = gate.gate_decision(root, target)
            self.assertEqual(verdict, "deny")
            self.assertIn("payload", reason.lower())

            self.assertTrue(gate.mark_payload_read(root))
            self.assertEqual(gate.gate_decision(root, target), ("allow", None))

    def test_file_delivery_payload_unread_denies(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=None, delivery="file")
            verdict, reason = gate.gate_decision(root, str(root / "src" / "x.py"))
            self.assertEqual(verdict, "deny")
            self.assertIn("read", reason.lower())

    def test_inline_delivery_needs_no_payload_read(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=None, delivery="inline")
            self.assertEqual(gate.gate_decision(root, str(root / "src" / "x.py")), ("allow", None))

    def test_surface_deny_precedes_payload_check(self):
        with TempRoot() as root:
            _frame(root, "design-ux-flow", surface=["docs/*"], delivery="spawn")
            verdict, reason = gate.gate_decision(root, str(root / "src" / "app.py"))
            self.assertEqual(verdict, "deny")
            self.assertIn("lease surface", reason)

class FailOpenTest(unittest.TestCase):
    def test_garbage_journal_fails_open_to_no_unit(self):
        with TempRoot() as root:
            journal.journal_path(root).write_text("NOT JSON\n{also bad\n\x00\x01\n")
            verdict, _ = gate.gate_decision(root, str(root / "src" / "x.py"))
            self.assertEqual(verdict, "no_unit")

    def test_open_unit_raising_fails_open_not_deny(self):
        with TempRoot() as root:
            _frame(root, "design-ux-flow", surface=["docs/*"])
            original = journal.open_unit
            journal.open_unit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            try:
                verdict, reason = gate.gate_decision(root, str(root / "src" / "app.py"))
            finally:
                journal.open_unit = original
            self.assertEqual((verdict, reason), ("no_unit", None))

class MarkPayloadReadTest(unittest.TestCase):
    def test_mark_without_open_unit_is_noop_false(self):
        with TempRoot() as root:
            self.assertFalse(gate.mark_payload_read(root))
            self.assertEqual([e for e in journal.read(root) if e["event"] == "unit.note"], [])

    def test_mark_with_open_unit_records_and_returns_true(self):
        with TempRoot() as root:
            _frame(root, "implement-feature", surface=None, delivery="spawn")
            self.assertTrue(gate.mark_payload_read(root))
            notes = [e for e in journal.read(root)
                     if e["event"] == "unit.note" and e.get("payload_read")]
            self.assertEqual(len(notes), 1)

if __name__ == "__main__":
    unittest.main()

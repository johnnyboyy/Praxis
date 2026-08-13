import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conduct  # noqa: E402
import config  # noqa: E402
import contributors as cb  # noqa: E402
import journal  # noqa: E402
from situation import Situation  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)

class _ContributeOnly:
    def contribute(self, situation):
        return [cb.Contribution(source="plain", title="t", body="b")]

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

class LedgerTest(Base):
    def test_note_and_notes_roundtrip_with_filter(self):
        journal.note(self.root, unit="u1", source="s", body="first", kind="x")
        journal.note(self.root, unit="u2", source="s", body="second")
        journal.note(self.root, source="s", body="run-wide")
        alln = journal.notes(self.root)
        self.assertEqual([n["body"] for n in alln], ["first", "second", "run-wide"])
        self.assertEqual(alln[0]["kind"], "x")
        u1 = journal.notes(self.root, unit="u1")
        self.assertEqual([n["body"] for n in u1], ["first"])
        self.assertEqual(journal.notes(self.root, unit="u2")[0]["body"], "second")

    def test_note_uses_distinct_event_name(self):
        journal.note(self.root, unit="u1", source="s", body="b")
        events = {e["event"] for e in journal.read(self.root)}
        self.assertIn("note", events)
        self.assertNotIn("unit.note", events)

_PLUGIN_SRC = '''
class _Rec:
    source = "uc"
    def contribute(self, situation):
        return []
    def hooks(self):
        return {"unit-close": self._on_unit_close}
    def _on_unit_close(self, ctx):
        ctx.add_note("uc", "closed", uid=getattr(ctx.unit, "id", None),
                     outcome=(ctx.receipt or {}).get("outcome"))

def make(root):
    return _Rec()
'''

class UnitCloseHookTest(Base):
    """unit-close fires on the inline path: close_unit and record_receipt."""

    def setUp(self):
        super().setUp()
        modroot = self.root / "mod"
        modroot.mkdir()
        (modroot / "uc_plugin.py").write_text(_PLUGIN_SRC)
        config.write(self.root, "contributors", {"uc": "uc_plugin:make"})
        sys.path.insert(0, str(modroot))
        self._modroot = modroot
        conduct.register_plan(self.root, [
            {"intent": "one", "id": "u1"},
            {"intent": "two", "id": "u2", "depends_on": ["u1"]},
        ])

    def tearDown(self):
        sys.path.remove(str(self._modroot))
        sys.modules.pop("uc_plugin", None)
        super().tearDown()

    def _hook_notes(self):
        return [n for n in journal.notes(self.root) if n.get("source") == "uc"]

    def test_close_unit_fires_unit_close_with_unit_and_receipt(self):
        conduct.next_handoff(self.root)
        out = conduct.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "closed")
        notes = self._hook_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["uid"], "u1")
        self.assertEqual(notes[0]["outcome"], "result")

    def test_record_receipt_result_fires_unit_close(self):
        conduct.record_receipt(self.root, "u1", outcome="result")
        notes = self._hook_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["outcome"], "result")

    def test_record_receipt_stall_fires_unit_close_with_stall(self):
        conduct.record_receipt(self.root, "u1", outcome="stall", note="blocked on X")
        notes = self._hook_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["outcome"], "stall")

    def test_blocked_close_does_not_fire(self):
        conduct.escalate_unit(self.root, "u1", reason="needs human")
        out = conduct.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(self._hook_notes(), [])

    def test_fires_once_per_unit(self):
        conduct.record_receipt(self.root, "u1", outcome="result")
        conduct.record_receipt(self.root, "u2", outcome="result")
        uids = [n["uid"] for n in self._hook_notes()]
        self.assertEqual(sorted(uids), ["u1", "u2"])

class FireNoOpTest(Base):
    def test_empty_contributors_is_noop(self):
        ctx = cb.HookContext(root=self.root, step="verify",
                             unit=None)
        cb.fire([], "verify", ctx)

    def test_contribute_only_contributor_is_noop(self):
        ctx = cb.HookContext(root=self.root, step="verify")
        cb.fire([_ContributeOnly()], "verify", ctx)
        cb.fire([_ContributeOnly()], "close", ctx)

if __name__ == "__main__":
    unittest.main()

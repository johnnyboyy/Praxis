"""Tests for interop_handoff — delivering a handoff across roots via praxis/inbox/.

Covers the bidirectional round-trip as file moves: an interop root's brief (addressed-to a child,
return-to the interop root) delivers into the child's inbox; the child's completion (addressed-to the
interop root) delivers back into the interop root's inbox, where it composes. Plus the guards: a
handoff with no addressed-to, and an addressed-to that resolves to no (or ambiguous) root.
Run: python3 -m unittest discover -s praxis/tests
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_handoff as ih  # noqa: E402


def mkroot(base: Path, rel: str, name: str) -> Path:
    d = base / rel if rel else base
    (d / "praxis").mkdir(parents=True, exist_ok=True)
    (d / "praxis" / "config.md").write_text(f"# praxis root: {name}\nname: {name}\ndebug: no\n")
    return d


def handoff(addressed_to: str = "", return_to: str = "", status: str = "complete") -> str:
    return (f"---\nunit-of-work: implement-feature\nworkstream: ws\nstance: convergent\n"
            f"agent-continuity: new\nstatus: {status}\n"
            + (f"addressed-to: {addressed_to}\n" if addressed_to else "")
            + (f"return-to: {return_to}\n" if return_to else "")
            + "---\n\n## Artifact\n\nx\n\n## Surfaced\n\n")


class InteropRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.platform = mkroot(self.tmp, "", "platform")   # interop root at the top
        self.app = mkroot(self.tmp, "app", "app")
        self.admin = mkroot(self.tmp, "admin", "admin")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, where: Path, text: str, name: str = "h.md") -> Path:
        p = where / name
        p.write_text(text)
        return p

    def test_brief_delivers_into_addressed_child_inbox(self):
        brief = self._write(self.tmp, handoff(addressed_to="app", return_to="platform"), "brief.md")
        rc, msg = ih.deliver(str(brief), self.tmp)
        self.assertEqual(rc, 0, msg)
        self.assertFalse(brief.exists())                                  # moved, not copied
        self.assertTrue((self.app / "praxis" / "inbox" / "brief.md").is_file())

    def test_child_completion_returns_to_interop_root_inbox(self):
        done = self._write(self.app, handoff(addressed_to="platform", return_to="platform"), "done.md")
        rc, msg = ih.deliver(str(done), self.tmp)
        self.assertEqual(rc, 0, msg)
        self.assertTrue((self.platform / "praxis" / "inbox" / "done.md").is_file())

    def test_full_round_trip_lands_child_result_at_interop_root(self):
        # interop -> app, then app -> interop; the interop root ends holding the returned result.
        brief = self._write(self.tmp, handoff(addressed_to="app", return_to="platform"), "brief.md")
        ih.deliver(str(brief), self.tmp)
        delivered = self.app / "praxis" / "inbox" / "brief.md"
        # child works and addresses its completion back to the brief's return-to
        completion = self._write(self.app, handoff(addressed_to="platform", return_to="platform"), "r.md")
        ih.deliver(str(completion), self.tmp)
        inbox = self.platform / "praxis" / "inbox"
        self.assertTrue((inbox / "r.md").is_file())
        self.assertTrue(delivered.is_file())  # the brief still sits in the child's inbox (its record)

    def test_missing_addressed_to_is_rejected(self):
        h = self._write(self.tmp, handoff(), "plain.md")   # an ordinary, non-interop handoff
        rc, msg = ih.deliver(str(h), self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("no `addressed-to:`", msg)
        self.assertTrue(h.exists())                        # not moved

    def test_unresolvable_root_is_rejected(self):
        h = self._write(self.tmp, handoff(addressed_to="does-not-exist"), "x.md")
        rc, msg = ih.deliver(str(h), self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("did not resolve", msg)
        self.assertTrue(h.exists())

    def test_inbox_lists_pending_cross_root_handoffs(self):
        ih.deliver(str(self._write(self.tmp, handoff(addressed_to="app", return_to="platform"), "a.md")), self.tmp)
        ih.deliver(str(self._write(self.tmp, handoff(addressed_to="app", return_to="admin"), "b.md")), self.tmp)
        rc = ih.cmd_inbox(type("A", (), {"root": "app", "frm": str(self.tmp)}))
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

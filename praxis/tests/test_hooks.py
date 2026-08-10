"""The enforcement hooks — the system's only DENY mechanism — get a test harness.

P2 (docs/CONDUCTOR-PLAN.md) repointed the gate at the conductor journal: an edit is authorized by
an OPEN unit of work in `<root>/.praxis/journal.jsonl` (conductor/journal.open_unit), not by a tmp
session-stamp file with a freshness window. These tests drive the REAL hook scripts in praxis/hooks/
(the ~/.claude/hooks/* symlinks resolve here), each fed the PreToolUse/PostToolUse JSON the harness
sends on stdin, and seed state through the journal — never past the hooks' real entry point.

Covers:
  - GateMatrix          — the allow/deny matrix, journal-seeded.
  - GateLibFailOpen      — a missing/unreadable shared lib must fail OPEN (finding 11).
  - CloseUnitDeauthorizes — closing a unit (unit.closed) flips the gate from allow to deny.
  - PayloadReadHook       — Reading the payload file records the read on the open unit (journal
                            note), which the gate then honors for file/spawn delivery.

Run: python3 -m unittest discover -s praxis/tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
GATE = HOOKS / "praxis-frame-gate.sh"
READ_STAMP = HOOKS / "praxis-payload-read-stamp.sh"

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "conductor"))
import journal  # noqa: E402

_HAVE_JQ = shutil.which("jq") is not None


def _run(hook: Path, payload: dict, extra_env: dict | None = None):
    env = dict(os.environ)
    env.pop("PRAXIS_HOOK_BYPASS", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run([str(hook)], input=json.dumps(payload), capture_output=True,
                          text=True, env=env)


@unittest.skipUnless(_HAVE_JQ, "jq required for the praxis hooks")
class GateMatrix(unittest.TestCase):
    """The allow/deny matrix, authorized by the journal's open unit."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("name: app\n")
        (self.root / "src").mkdir()
        self.editfile = self.root / "src" / "x.ts"
        self.editfile.write_text("// x\n")
        (self.root / "docs").mkdir()
        self.docfile = self.root / "docs" / "y.md"
        self.docfile.write_text("# y\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _frame(self, **payload):
        """Seed an open unit for this root."""
        journal.append(self.root, "unit.framed", unit=payload.pop("unit", "u1"), **payload)

    def _gate(self, file_path: Path | None = None):
        payload = {"session_id": "sess-A",
                   "tool_input": {"file_path": str(file_path or self.editfile)}}
        return _run(GATE, payload)

    def assertDeny(self, res, needle: str | None = None):
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('"deny"', res.stdout, f"expected a deny, got: {res.stdout!r}")
        if needle:
            self.assertIn(needle, res.stdout)

    def assertAllow(self, res):
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn('"deny"', res.stdout, f"expected an allow, got: {res.stdout!r}")

    def test_no_open_unit_denies(self):
        self.assertDeny(self._gate(), "No open unit")

    def test_open_unit_unrestricted_allows(self):
        self._frame(unit_of_work="implement-feature", delivery="none")
        self.assertAllow(self._gate())

    def test_closed_unit_denies(self):
        self._frame(unit_of_work="implement-feature", delivery="none")
        journal.append(self.root, "unit.closed", unit="u1")
        self.assertDeny(self._gate(), "No open unit")

    def test_delivery_file_without_read_denies(self):
        self._frame(unit_of_work="implement-feature", delivery="file",
                    payload="/x/.frame-payload.md")
        self.assertDeny(self._gate(), "has not been read")

    def test_delivery_spawn_without_read_denies(self):
        self._frame(unit_of_work="implement-feature", delivery="spawn")
        self.assertDeny(self._gate(), "framed for a SPAWN")

    def test_delivery_file_with_read_allows(self):
        self._frame(unit_of_work="implement-feature", delivery="file",
                    payload="/x/.frame-payload.md")
        journal.append(self.root, "unit.note", unit="u1", payload_read=True)
        self.assertAllow(self._gate())

    def test_out_of_surface_denies(self):
        self._frame(unit_of_work="scan-architecture", delivery="none",
                    surface=["docs/*", "*.md"])
        # src/x.ts is outside docs/* and *.md
        self.assertDeny(self._gate(file_path=self.editfile), "Out of lease surface")

    def test_in_surface_allows(self):
        self._frame(unit_of_work="scan-architecture", delivery="none",
                    surface=["docs/*", "*.md"])
        self.assertAllow(self._gate(file_path=self.docfile))

    def test_bookkeeping_always_in_surface(self):
        self._frame(unit_of_work="scan-architecture", delivery="none", surface=["docs/*"])
        bookkeeping = self.root / ".praxis" / "handoffs" / "h.md"
        bookkeeping.parent.mkdir(parents=True, exist_ok=True)
        bookkeeping.write_text("x")
        self.assertAllow(self._gate(file_path=bookkeeping))

    def test_most_recent_open_unit_authorizes(self):
        # A superseding frame (new open unit) is what the gate reads — open_unit takes the latest.
        self._frame(unit="u1", unit_of_work="scan-architecture", delivery="none",
                    surface=["docs/*"])
        self._frame(unit="u2", unit_of_work="implement-feature", delivery="none",
                    surface=["src/*"])
        self.assertAllow(self._gate(file_path=self.editfile))


@unittest.skipUnless(_HAVE_JQ, "jq required for the praxis hooks")
class GateLibFailOpen(unittest.TestCase):
    """Finding 11: a missing/unreadable shared lib must fail OPEN (allow), never hard-deny."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        # A hook copy in an isolated dir with NO lib beside it → source block degrades to exit 0.
        self.hookdir = self.tmp / "hooks"
        self.hookdir.mkdir()
        self.hook = self.hookdir / "praxis-frame-gate.sh"
        self.hook.write_text(GATE.read_text())
        self.hook.chmod(0o755)
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("name: app\n")
        (self.root / "src").mkdir()
        self.editfile = self.root / "src" / "x.ts"
        self.editfile.write_text("// x\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_lib_fails_open(self):
        payload = {"session_id": "s", "tool_input": {"file_path": str(self.editfile)}}
        res = _run(self.hook, payload)
        self.assertEqual(res.returncode, 0)
        # No lib to source ⇒ exit 0 before any walk/deny — an unframed edit that would otherwise deny.
        self.assertNotIn('"deny"', res.stdout)


@unittest.skipUnless(_HAVE_JQ, "jq required for the praxis hooks")
class CloseUnitDeauthorizes(unittest.TestCase):
    """The end-to-end claim, restated for the journal: a fresh open unit allows the gate; recording
    its close (unit.closed) flips the same gate to deny. Drives the REAL gate hook before and after
    a real close_work call (via the CLI transport), the journal being the single source of truth."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("name: app\n")
        (self.root / "src").mkdir()
        self.editfile = self.root / "src" / "x.ts"
        self.editfile.write_text("// x\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _gate(self):
        payload = {"session_id": "sess-close", "tool_input": {"file_path": str(self.editfile)}}
        return _run(GATE, payload)

    def test_close_work_deauthorizes_the_open_unit(self):
        journal.append(self.root, "unit.framed", unit="u1", unit_of_work="implement-feature",
                       delivery="none")
        allow_before = self._gate()
        self.assertNotIn('"deny"', allow_before.stdout,
                         f"expected allow before close, got: {allow_before.stdout!r}")

        cli = Path(__file__).resolve().parent.parent / "front-door" / "cli.py"
        proc = subprocess.run(
            [sys.executable, str(cli), "close-work", "--search-base", str(self.root)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        deny_after = self._gate()
        self.assertIn('"deny"', deny_after.stdout,
                      f"expected deny after close, got: {deny_after.stdout!r}")


@unittest.skipUnless(_HAVE_JQ, "jq required for the praxis hooks")
class PayloadReadHook(unittest.TestCase):
    """The payload-read hook records the read on the open unit (a journal note), and only fires on
    the payload path — replacing the old `.read` tmp stamp file."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("name: app\n")
        self.payload = self.root / ".praxis" / ".frame-payload.md"
        self.payload.write_text("# payload\n")
        journal.append(self.root, "unit.framed", unit="u1", unit_of_work="implement-feature",
                       delivery="file", payload=str(self.payload))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self, file_path: Path):
        return _run(READ_STAMP, {"session_id": "sess-C",
                                 "tool_input": {"file_path": str(file_path)}})

    def test_payload_path_records_read_on_open_unit(self):
        self._read(self.payload)
        self.assertTrue(journal.open_unit(self.root)["last"].get("payload_read"),
                        "reading the payload should mark the open unit's payload read")

    def test_other_path_records_nothing(self):
        other = self.root / "src.txt"
        other.write_text("x")
        self._read(other)
        self.assertNotIn("payload_read", journal.open_unit(self.root)["last"])


if __name__ == "__main__":
    unittest.main()

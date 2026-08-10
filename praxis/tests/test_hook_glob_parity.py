"""Finding 11 (updated for P2): the surface-glob semantics used to be implemented twice — units.py's
fnmatch (surface_allows) and the gate hook's bash `case` — and their agreement was asserted only in
comments. P2 collapsed the two: the gate hook now delegates its whole decision to gate.py, which
applies units.surface_allows directly, so there is a SINGLE Python implementation and no bash `case`
to drift from it. This test still drives the REAL praxis-frame-gate.sh end-to-end (seeding a journal
open unit carrying the surface, then piping a synthetic PreToolUse payload) and asserts it honors the
same pinned allow/deny per case — proving the gate surface still reaches units.surface_allows.

Key cases: `src/*` crossing slashes, `*.md` top-level vs nested `a/b.md` (fnmatch `*` DOES cross `/`),
the bookkeeping carve-out, multiple patterns, and a no-surface (unrestricted) unit.

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

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "conductor"))
import units as un  # noqa: E402
import journal  # noqa: E402

GATE = Path(__file__).resolve().parent.parent / "hooks" / "praxis-frame-gate.sh"
_HAVE_JQ = shutil.which("jq") is not None

# (surface, rel_path, expected_allow). None surface = unrestricted unit.
CASES = [
    (["src/*"], "src/a.ts", True),          # single component
    (["src/*"], "src/a/b.ts", True),        # `*` crosses `/`
    (["src/*"], "lib/a.ts", False),         # different top dir
    (["*.md"], "a.md", True),               # top-level
    (["*.md"], "a/b.md", True),             # nested — fnmatch `*` crosses `/`
    (["*.md"], "src/x.ts", False),          # non-.md
    (["docs/*"], ".praxis/handoffs/h.md", True),   # bookkeeping carve-out beats a non-matching surface
    (["docs/*", "*.md"], "notes.md", True),        # multiple patterns, 2nd matches
    (["docs/*", "*.md"], "src/x.ts", False),       # multiple patterns, none match
    (None, "anything/deep/x.ts", True),            # no-surface unit ⇒ unrestricted
]


def _python_verdict(surface, rel) -> bool:
    return un.surface_allows(surface, rel)


@unittest.skipUnless(_HAVE_JQ, "jq required for the praxis gate hook")
class GlobParity(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("name: app\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bash_verdict(self, surface, rel) -> bool:
        """Run the real gate hook: seed a journal open unit with this surface (delivery none, so no
        payload read is required), editing root/rel. Returns True (allow) when the gate emits no
        deny, False (deny) otherwise. Each case gets a fresh journal so open units don't stack."""
        (self.root / ".praxis" / journal.JOURNAL_NAME).unlink(missing_ok=True)
        journal.append(self.root, "unit.framed", unit="u", unit_of_work="scan-architecture",
                       surface=surface, delivery="none")
        editfile = self.root / rel
        editfile.parent.mkdir(parents=True, exist_ok=True)
        editfile.write_text("x")
        env = dict(os.environ)
        env.pop("PRAXIS_HOOK_BYPASS", None)
        payload = {"session_id": "sess-parity", "tool_input": {"file_path": str(editfile)}}
        res = subprocess.run([str(GATE)], input=json.dumps(payload), capture_output=True,
                             text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        return '"deny"' not in res.stdout

    def test_gate_honors_surface_allows_per_case(self):
        for surface, rel, expected in CASES:
            with self.subTest(surface=surface, rel=rel):
                py = _python_verdict(surface, rel)
                bash = self._bash_verdict(surface, rel)
                self.assertEqual(py, expected,
                                 f"python surface_allows disagreed with the pinned semantics")
                self.assertEqual(bash, expected,
                                 f"gate hook disagreed with the pinned semantics")
                self.assertEqual(py, bash,
                                 f"gate/units drift: python={py} gate={bash} for {surface} / {rel}")


if __name__ == "__main__":
    unittest.main()

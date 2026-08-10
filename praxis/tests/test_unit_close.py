"""Tests for unit_close — the one-shot close ceremony chaining handoff validate -> chunk ledger
close -> frame marker close, stopping at the first failure. Fixture idiom follows
test_chunk_ledger.py's CloseSequenceTests (a temp root with .praxis/{handoffs,chunks}, the generic
stub engine registered for `compose`). A valid handoff is built as a minimal literal matching
handoff/base.json's required fields (unit-of-work, workstream, stance, agent-continuity, status,
plus the Artifact/Surfaced sections) rather than via handoff.py's own template renderer, since the
template's placeholder values (e.g. `<unit-of-work>`) would themselves fail validation.

Run: python3 -m unittest discover -s praxis/tests
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import unit_close  # noqa: E402
import frame  # noqa: E402
import root_tree  # noqa: E402
from _stub_engine import write_stub, write_plugin_slot  # noqa: E402


VALID_HANDOFF = """---
unit-of-work: {uow}
workstream: {workstream}
stance: {stance}
agent-continuity: new
status: complete
---

## Artifact

Built the thing.

## Surfaced

"""


class UnitCloseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "proj"
        self.handoffs = self.root / ".praxis" / "handoffs"
        self.handoffs.mkdir(parents=True)
        (self.root / ".praxis" / "chunks").mkdir(parents=True)
        stub = write_stub(self.tmp)
        self.slot = write_plugin_slot(self.tmp / "engine", stub)
        self.log = self.tmp / "log.txt"
        os.environ["STUB_LOG"] = str(self.log)
        os.environ.pop("STUB_FAIL", None)
        os.environ.pop("STUB_DOMAINS", None)
        # No domains-loaded field on the handoff, so chunk_ledger's reconciliation (b) is skipped —
        # only checks (a) workstream-match and the handoff-exists precondition apply, matching
        # test_chunk_ledger.py's own baseline fixture.

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        for k in ("STUB_LOG", "STUB_FAIL", "STUB_DOMAINS"):
            os.environ.pop(k, None)

    def _handoff(self, uow="implement-feature", workstream="w", stance="convergent") -> Path:
        h = self.handoffs / "h.md"
        h.write_text(VALID_HANDOFF.format(uow=uow, workstream=workstream, stance=stance))
        return h

    def _marker(self):
        return root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME

    def _payload(self):
        return root_tree.praxis_dir(self.root) / frame.FRAME_PAYLOAD_NAME

    def _ledger(self):
        return self.root / ".praxis" / "chunks" / "w.md"


class HappyPathTests(UnitCloseTestCase):
    def test_all_three_steps_run_and_close_cleanly(self):
        h = self._handoff()
        self._marker().write_text(json.dumps({"timestamp": 1.0, "unit_of_work": "implement-feature"}))
        self._payload().write_text("payload body")

        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))

        self.assertTrue(result["ok"])
        self.assertEqual([s["step"] for s in result["steps"]],
                         ["validate", "chunk-close", "marker-close"])
        self.assertTrue(all(s["ok"] for s in result["steps"]))

        # chunk recorded
        self.assertTrue(self._ledger().is_file())
        # handoff closed (deleted, debug off)
        self.assertFalse(h.exists())
        # marker closed
        marker = json.loads(self._marker().read_text())
        self.assertTrue(marker["closed"])
        self.assertEqual(marker["prior_unit_of_work"], "implement-feature")
        # payload deleted
        self.assertFalse(self._payload().exists())


class TierVerificationPassThroughTests(UnitCloseTestCase):
    def test_tier_and_verification_pass_through_to_ledger(self):
        h = self._handoff()
        self._marker().write_text(json.dumps({"timestamp": 1.0, "unit_of_work": "implement-feature"}))
        self._payload().write_text("payload body")

        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS),
                                tier="sonnet", verification="clean")

        self.assertTrue(result["ok"])
        _, entries = unit_close.cl.parse_chunks(self._ledger())
        self.assertEqual(entries[0]["tier"], "sonnet")
        self.assertEqual(entries[0]["verification"], "clean")


class ValidateFailureTests(UnitCloseTestCase):
    def test_missing_required_field_stops_before_ledger(self):
        h = self.handoffs / "h.md"
        h.write_text("---\nworkstream: w\n---\n\n## Artifact\n\n## Surfaced\n\n")  # missing several required fields
        self._marker().write_text(json.dumps({"timestamp": 1.0, "unit_of_work": "prior"}))

        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_at"], "validate")
        self.assertEqual([s["step"] for s in result["steps"]], ["validate"])
        self.assertTrue(h.exists())
        self.assertFalse(self._ledger().exists())
        # marker untouched
        marker = json.loads(self._marker().read_text())
        self.assertNotIn("closed", marker)

    def test_nonexistent_handoff_stops_before_ledger(self):
        result = unit_close.run(str(self.root), "w", "u", "convergent",
                                str(self.handoffs / "nope.md"), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_at"], "validate")
        self.assertFalse(self._ledger().exists())


class LedgerFailureTests(UnitCloseTestCase):
    def test_workstream_mismatch_stops_before_marker_close(self):
        h = self._handoff(workstream="other")  # valid schema, but chunk_done's (a) check fails
        self._marker().write_text(json.dumps({"timestamp": 1.0, "unit_of_work": "prior"}))

        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_at"], "chunk-close")
        self.assertEqual([s["step"] for s in result["steps"]], ["validate", "chunk-close"])
        self.assertTrue(result["steps"][0]["ok"])
        self.assertFalse(result["steps"][1]["ok"])
        self.assertFalse(self._ledger().exists())
        self.assertTrue(h.exists())  # gate held: handoff not closed
        # marker untouched: still the prior JSON, no `closed` field
        marker = json.loads(self._marker().read_text())
        self.assertNotIn("closed", marker)
        self.assertEqual(marker["unit_of_work"], "prior")


class BareFloatMarkerTests(UnitCloseTestCase):
    def test_bare_float_marker_tolerated_at_marker_close_step(self):
        h = self._handoff()
        self._marker().write_text("1234567890.0")

        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))

        self.assertTrue(result["ok"])
        self.assertIsNone(result["marker"]["prior_unit_of_work"])
        marker = json.loads(self._marker().read_text())
        self.assertTrue(marker["closed"])
        self.assertIsNone(marker["prior_unit_of_work"])


class JsonOutputShapeTests(UnitCloseTestCase):
    def test_json_output_has_expected_shape(self):
        h = self._handoff()
        rc = unit_close.main([
            "--root", str(self.root), "--workstream", "w", "--unit-of-work", "u",
            "--stance", "convergent", "--handoff", str(h),
            "--engine-plugins", str(self.slot),
            "--plugins-dir", str(unit_close.ho.DEFAULT_PLUGINS),
            "--json",
        ])
        self.assertEqual(rc, 0)

    def test_run_result_is_json_serializable(self):
        h = self._handoff()
        result = unit_close.run(str(self.root), "w", "u", "convergent", str(h), None,
                                str(self.slot), str(unit_close.ho.DEFAULT_PLUGINS))
        # The whole report must round-trip through json.dumps for --json output.
        text = json.dumps(result)
        reparsed = json.loads(text)
        self.assertTrue(reparsed["ok"])
        self.assertEqual(reparsed["marker"]["closed"], True)


if __name__ == "__main__":
    unittest.main()

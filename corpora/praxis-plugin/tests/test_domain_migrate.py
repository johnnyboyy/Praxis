"""Tests for domain_migrate — the verification gate. Run: python3 -m unittest discover -s praxis/tests"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import domain_migrate  # noqa: E402
from _stub_engine import write_stub, read_log  # noqa: E402


class DomainMigrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.stub = write_stub(self.tmp)
        self.log = self.tmp / "log.txt"
        os.environ["STUB_LOG"] = str(self.log)
        os.environ.pop("STUB_FAIL", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_LOG", None)
        os.environ.pop("STUB_FAIL", None)

    def test_clean_run_does_all_four_steps_in_order(self):
        rc = domain_migrate.run(self.stub, None, str(self.tmp))
        self.assertEqual(rc, 0)
        calls = [c[0] for c in read_log(self.log)]
        self.assertEqual(calls, ["migrate-domains", "measure", "verify", "lint-domains"])

    def test_bad_verify_is_a_hard_stop_lint_not_run(self):
        os.environ["STUB_FAIL"] = "verify"
        rc = domain_migrate.run(self.stub, None, str(self.tmp))
        self.assertNotEqual(rc, 0)
        calls = [c[0] for c in read_log(self.log)]
        self.assertEqual(calls, ["migrate-domains", "measure", "verify"])  # lint-domains gated out

    def test_failed_migrate_stops_before_verify(self):
        os.environ["STUB_FAIL"] = "migrate-domains"
        rc = domain_migrate.run(self.stub, None, str(self.tmp))
        self.assertNotEqual(rc, 0)
        calls = [c[0] for c in read_log(self.log)]
        self.assertEqual(calls, ["migrate-domains"])  # nothing measured or verified

    def test_source_is_passed_through(self):
        domain_migrate.run(self.stub, "/some/seed/domains", str(self.tmp))
        first = read_log(self.log)[0]
        self.assertIn("--source", first)
        self.assertIn("/some/seed/domains", first)


if __name__ == "__main__":
    unittest.main()

"""Tests for the principle-lifecycle sequence scripts: domain_import,
ratify_writeback. They own ordering/discipline; corpora owns the verbs. Driven against the stub
engine. Run: python3 -m unittest discover -s praxis/tests"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import domain_import  # noqa: E402
import ratify_writeback  # noqa: E402
from _stub_engine import write_stub, read_log  # noqa: E402


class SequenceBase(unittest.TestCase):
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

    def run_cli(self, module, argv):
        return module.main(["--corpus-py", str(self.stub)] + argv)


class DomainImportTests(SequenceBase):
    def test_browse_is_read_only(self):
        self.run_cli(domain_import, ["browse", "--source", "/seed/domains"])
        calls = [c[0] for c in read_log(self.log)]
        self.assertEqual(calls, ["import-list"])  # browse files nothing

    def test_file_then_ratify_are_distinct_steps(self):
        self.run_cli(domain_import, ["file", "--source", "/seed", "--domain", "d", "--id", "p1"])
        self.run_cli(domain_import, ["ratify", "--id", "p1", "--as-domain", "coding-general"])
        calls = [c[0] for c in read_log(self.log)]
        self.assertEqual(calls, ["import-candidate", "ratify-import-candidate"])
        self.assertIn("coding-general", read_log(self.log)[1])


class RatifyWritebackTests(SequenceBase):
    def test_add_invokes_add_principle(self):
        rc = self.run_cli(ratify_writeback, ["add", "--domain", "d", "--id", "p1", "--rule", "r",
                                             "--condition", "c", "--reason", "y", "--provenance", "prov"])
        self.assertEqual(rc, 0)
        self.assertEqual(read_log(self.log)[0][0], "add-principle")

    def test_reject_is_manual_and_invokes_no_engine(self):
        rc = self.run_cli(ratify_writeback, ["reject"])
        self.assertEqual(rc, 0)
        self.assertEqual(read_log(self.log), [])  # manual path: nothing was run

    def test_graduate_convention_is_manual(self):
        rc = self.run_cli(ratify_writeback, ["graduate-convention"])
        self.assertEqual(rc, 0)
        self.assertEqual(read_log(self.log), [])


if __name__ == "__main__":
    unittest.main()

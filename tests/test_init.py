import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import conduct  # noqa: E402
import config as C  # noqa: E402
import root_tree as rt  # noqa: E402


def git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)


class InitRootTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        git_init(self.tmp)
        self.sub = self.tmp / "src" / "pkg"
        self.sub.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marks_git_root_from_subdir_with_clean_config(self):
        self.assertIsNone(rt.resolve_root(self.sub))
        out = conduct.init_root(root=self.sub)
        self.assertEqual(out["status"], "initialized")
        self.assertEqual(Path(out["root"]), self.tmp)
        self.assertTrue(out["created"])
        self.assertEqual(rt.resolve_root(self.sub), self.tmp)
        self.assertEqual(C.read(self.tmp), {})
        self.assertEqual(C.path(self.tmp).read_text(), "{}\n")

    def test_idempotent_created_flag(self):
        self.assertTrue(conduct.init_root(root=self.tmp)["created"])
        self.assertFalse(conduct.init_root(root=self.tmp)["created"])

    def test_no_git_marks_start_dir(self):
        plain = Path(tempfile.mkdtemp()).resolve()
        try:
            out = conduct.init_root(root=plain)
            self.assertEqual(Path(out["root"]), plain)
            self.assertEqual(C.read(plain), {})
        finally:
            shutil.rmtree(plain, ignore_errors=True)


class ManagedHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        git_init(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_managed_false_before_true_after(self):
        import mcp_server
        self.assertFalse(mcp_server._managed(str(self.tmp)))
        conduct.init_root(root=self.tmp)
        self.assertTrue(mcp_server._managed(str(self.tmp)))


if __name__ == "__main__":
    unittest.main()

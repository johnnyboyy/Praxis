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

    def test_writes_shape_to_git_root_from_subdir(self):
        self.assertIsNone(rt.resolve_root(self.sub))
        out = conduct.init_root(root=self.sub, language="python", framework="none",
                                has_ui="no", styling="none", package_manager="uv")
        self.assertEqual(out["status"], "initialized")
        self.assertEqual(Path(out["root"]), self.tmp)
        self.assertEqual(rt.resolve_root(self.sub), self.tmp)
        self.assertEqual(C.read(self.tmp), {
            "language": "python", "framework": "none", "has-ui": "no",
            "styling": "none", "package-manager": "uv"})

    def test_only_non_none_values_written(self):
        conduct.init_root(root=self.tmp, language="node", framework="next")
        self.assertEqual(C.read(self.tmp), {"language": "node", "framework": "next"})

    def test_no_git_writes_to_start_dir(self):
        plain = Path(tempfile.mkdtemp()).resolve()
        try:
            out = conduct.init_root(root=plain, language="python")
            self.assertEqual(Path(out["root"]), plain)
            self.assertEqual(C.read(plain), {"language": "python"})
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
        conduct.init_root(root=self.tmp, language="python")
        self.assertTrue(mcp_server._managed(str(self.tmp)))


if __name__ == "__main__":
    unittest.main()

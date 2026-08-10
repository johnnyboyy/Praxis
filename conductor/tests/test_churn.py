"""Tests for churn — recent-churn scoping over a real temp git repo. Run: python3 -m unittest discover -s praxis/tests"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import churn  # noqa: E402


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def commit(repo: Path, path: str, content: str) -> None:
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    git(repo, "add", path)
    git(repo, "commit", "-m", f"touch {path}")


class ChurnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        git(self.tmp, "init")
        git(self.tmp, "config", "user.email", "t@example.com")
        git(self.tmp, "config", "user.name", "t")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hottest_file_ranks_first(self):
        for i in range(4):
            commit(self.tmp, "hot.py", f"v{i}\n")
        commit(self.tmp, "cold.py", "x\n")
        r = churn.churn_files(self.tmp, None, None, 10)
        self.assertTrue(r["available"])
        self.assertEqual(r["hot"][0]["path"], "hot.py")
        self.assertEqual(r["hot"][0]["changes"], 4)

    def test_dirs_roll_up_paths(self):
        commit(self.tmp, "src/a/one.py", "1\n")
        commit(self.tmp, "src/a/two.py", "2\n")
        commit(self.tmp, "docs/x.md", "d\n")
        r = churn.churn_dirs(self.tmp, None, None, 10, depth=2)
        top = r["hot"][0]
        self.assertEqual(top["dir"], "src/a")
        self.assertEqual(top["changes"], 2)

    def test_non_git_dir_degrades_gracefully(self):
        plain = Path(tempfile.mkdtemp())
        try:
            r = churn.churn_files(plain, None, None, 10)
            self.assertFalse(r["available"])
            self.assertEqual(r["hot"], [])
        finally:
            shutil.rmtree(plain, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

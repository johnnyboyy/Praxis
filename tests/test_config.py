import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_path(self):
        self.assertEqual(C.path(self.root), self.root / ".praxis" / "config.json")

    def test_read_absent_file(self):
        self.assertEqual(C.read(self.root), {})
        self.assertEqual(C.read(self.root, "plugin"), {})

    def test_write_creates_file_dir_and_section(self):
        self.assertFalse(C.path(self.root).exists())
        C.write(self.root, "plugin", {"token": "abc"})
        self.assertTrue(C.path(self.root).exists())
        self.assertEqual(C.read(self.root, "plugin"), {"token": "abc"})

    def test_roundtrip_top_level(self):
        C.write(self.root, None, {"language": "python", "framework": "none"})
        self.assertEqual(C.read(self.root),
                         {"language": "python", "framework": "none"})

    def test_roundtrip_namespace(self):
        C.write(self.root, "plugin", {"mode": "fast", "level": "3"})
        self.assertEqual(C.read(self.root, "plugin"), {"mode": "fast", "level": "3"})

    def test_stores_raw_typed_values(self):
        C.write(self.root, "plugin", {"strict": True, "n": 3, "exclude": ["a", "b"]})
        self.assertEqual(C.read(self.root, "plugin"),
                         {"strict": True, "n": 3, "exclude": ["a", "b"]})

    def test_read_absent_section_when_file_exists(self):
        C.write(self.root, None, {"language": "python"})
        self.assertEqual(C.read(self.root, "nope"), {})

    def test_write_merges_into_scope(self):
        C.write(self.root, "plugin", {"a": "1", "b": "2"})
        C.write(self.root, "plugin", {"b": "9", "c": "3"})
        self.assertEqual(C.read(self.root, "plugin"),
                         {"a": "1", "b": "9", "c": "3"})

    def test_namespace_write_preserves_other_namespace_and_top_level(self):
        C.write(self.root, None, {"language": "python", "has-ui": "no"})
        C.write(self.root, "A", {"x": "1"})
        C.write(self.root, "B", {"y": "2"})
        self.assertEqual(C.read(self.root, "A"), {"x": "1"})
        self.assertEqual(C.read(self.root, "B"), {"y": "2"})
        self.assertEqual(C.read(self.root),
                         {"language": "python", "has-ui": "no"})

    def test_ensure_creates_empty_clean_root(self):
        self.assertTrue(C.ensure(self.root))
        self.assertEqual(C.path(self.root).read_text(), "{}\n")
        self.assertEqual(C.read(self.root), {})
        self.assertFalse(C.ensure(self.root))  # idempotent

    def test_malformed_file_reads_as_empty(self):
        C.path(self.root).parent.mkdir(parents=True)
        C.path(self.root).write_text("not json {")
        self.assertEqual(C.read(self.root), {})
        self.assertEqual(C.read(self.root, "plugin"), {})


if __name__ == "__main__":
    unittest.main()

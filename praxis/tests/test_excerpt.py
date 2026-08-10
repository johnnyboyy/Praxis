"""excerpt.py — byte-for-byte markdown section extraction."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import excerpt  # noqa: E402

DOC = """# Library

Intro prose.

## Buttons

Primary uses `--accent`.

### States

Hover darkens 8%.

## Color tokens

`--accent: teal-600`.

```md
## Not a heading (fenced)
```

## Empty section
"""


class TestParseHeadings(unittest.TestCase):
    def test_levels_titles_and_spans(self):
        heads = excerpt.parse_headings(DOC)
        titles = [h["title"] for h in heads]
        self.assertEqual(titles, ["Library", "Buttons", "States", "Color tokens", "Empty section"])
        buttons = next(h for h in heads if h["title"] == "Buttons")
        # Buttons runs through its subsection, ending at the next same-level heading.
        self.assertEqual(DOC.split("\n")[buttons["end"]], "## Color tokens")

    def test_fenced_headings_ignored(self):
        titles = [h["title"] for h in excerpt.parse_headings(DOC)]
        self.assertNotIn("Not a heading (fenced)", titles)


class TestExtract(unittest.TestCase):
    def test_byte_for_byte_including_subsections(self):
        body, missing = excerpt.extract(DOC, ["Buttons"])
        self.assertEqual(missing, [])
        self.assertIn("## Buttons", body)
        self.assertIn("### States", body)
        self.assertIn("Hover darkens 8%.", body)
        self.assertNotIn("Color tokens", body)

    def test_multiple_sections_in_asked_order(self):
        body, missing = excerpt.extract(DOC, ["Color tokens", "Buttons"])
        self.assertEqual(missing, [])
        self.assertLess(body.index("Color tokens"), body.index("Buttons"))

    def test_case_insensitive_match(self):
        body, missing = excerpt.extract(DOC, ["buttons"])
        self.assertEqual(missing, [])
        self.assertIn("## Buttons", body)

    def test_missing_section_reported_not_silent(self):
        body, missing = excerpt.extract(DOC, ["Buttons", "Nope"])
        self.assertEqual(missing, ["Nope"])
        self.assertIn("## Buttons", body)  # what exists is still returned

    def test_empty_trailing_section(self):
        body, missing = excerpt.extract(DOC, ["Empty section"])
        self.assertEqual(missing, [])
        self.assertEqual(body, "## Empty section")


if __name__ == "__main__":
    unittest.main()

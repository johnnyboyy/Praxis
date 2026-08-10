"""Integration: corpora registered into praxis = a working composition.

This is the bridge test — it lives on the CORPORA side because it exercises corpora-plugged-into-
praxis (praxis-core itself names nothing here). It simulates "moving corpora in": it takes corpora's
capabilities manifest, points its `cli` at the real `corpus.py`, drops it into a praxis engine plugin
SLOT, then drives praxis-core's `frame` against a fixture project and asserts REAL domains come back.

Pure praxis (empty slot) degrades; praxis + corpora registered composes. That is the whole contract.

Requires corpora's own `corpus.py` to be present beside this contribution; skips if absent.
Run: python3 -m unittest discover -s corpora/praxis-plugin/tests
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PLUGIN = HERE.parents[1]                       # skills/corpora/praxis-plugin
CORPUS_PY = PLUGIN.parents[0] / "scripts" / "corpus.py"   # skills/corpora/scripts/corpus.py
CORPORA_MANIFEST = PLUGIN / "engine" / "plugins" / "corpora.json"
PRAXIS_SCRIPTS = PLUGIN.parents[1] / "praxis" / "scripts"

sys.path.insert(0, str(PRAXIS_SCRIPTS))
import engine  # noqa: E402  praxis-core generic resolver
import frame  # noqa: E402  praxis-core framing


def make_project(base: Path) -> Path:
    """A project 'using both': a praxis/config.md root marker AND a corpora domain set for the engine."""
    root = base / "proj"
    (root / "praxis").mkdir(parents=True)
    (root / "praxis" / "config.md").write_text("## project-shape\nname: proj\n")
    (root / "corpora").mkdir(parents=True)
    (root / "corpora" / "config.md").write_text("## project-shape\nname: proj\nlanguage: typescript\n")
    dom = root / "corpora" / "domains"
    dom.mkdir(parents=True)
    (dom / "coding-general.md").write_text(
        "---\nsubject: coding\nposture: guardrail\nunits-of-work: [implement-feature]\nuniversal: true\n---\n"
        "# Domain: coding-general\n\n```yaml\nprinciples:\n- id: p\n  rule: r\n  condition: c\n  reason: y\nkilled:\n```\n")
    return root


def move_corpora_into_slot(slot: Path) -> None:
    """The 'import corpora into praxis's engine slot' step: copy corpora's manifest into the slot,
    with its cli.entry rewritten to the (absolute) real corpus.py — exactly what a snapshot-import of
    this contribution into a project's praxis slot would record."""
    slot.mkdir(parents=True, exist_ok=True)
    data = json.loads(CORPORA_MANIFEST.read_text())
    data["cli"] = {"command": "python3", "entry": str(CORPUS_PY.resolve())}
    (slot / "corpora.json").write_text(json.dumps(data))


class CorporaPluggedIn(unittest.TestCase):
    def setUp(self):
        if not CORPUS_PY.is_file():
            self.skipTest("corpora's corpus.py not present")
        self.tmp = Path(tempfile.mkdtemp())
        self.root = make_project(self.tmp)
        self.slot = self.tmp / "engine" / "plugins"
        move_corpora_into_slot(self.slot)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_slot_has_no_engine_but_registered_corpora_composes(self):
        # 1. Pure praxis: an empty slot registers no engine → composition unavailable (degrades).
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertIsNone(engine.load_registered(empty))
        f0 = frame.build_frame(self.tmp, "proj/src/x.ts", [], "implement-feature", None)
        self.assertEqual(f0["roots"][0]["name"], "proj")     # root fact still stands
        self.assertIsNone(f0["composition"])

        # 2. Corpora moved in: the slot resolves to a manifest whose cli is the real corpus.py.
        manifest = engine.load_registered(self.slot)
        self.assertEqual(manifest["plugin"], "corpora")
        self.assertEqual(Path(manifest["cli"][-1]), CORPUS_PY.resolve())

        # 3. frame → compose against the real engine returns the REAL composed domain set.
        f = frame.build_frame(self.tmp, "proj/src/x.ts", [], "implement-feature", manifest)
        self.assertEqual(f["verdict"], "single-root")
        self.assertEqual(f["composition_note"], "ok")
        self.assertIn("coding-general", f["composition"])


if __name__ == "__main__":
    unittest.main()

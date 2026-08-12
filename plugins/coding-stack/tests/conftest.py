"""Shared test setup for the coding-stack suite.

Puts the corpora package dir and this plugin's dir on sys.path so that
`from corpora.parser import parse_domain_file` and `import coding_stack_plugin`
both resolve (the same sys.path a consuming root would provide).
"""

import sys
from pathlib import Path

CORPORA_PATH = str(Path(__file__).resolve().parents[2] / "corpora")
PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)

for p in (CORPORA_PATH, PLUGIN_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

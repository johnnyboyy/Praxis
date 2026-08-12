"""Shared test setup for the corpora suite.

Puts both the praxis skill dir and this repo root on sys.path so that
`import config`, `from contributors import ...`, `from situation import ...`,
and `import corpora...` all resolve.
"""

import sys
from pathlib import Path

PRAXIS_PATH = str(Path(__file__).resolve().parents[3])
REPO_ROOT = str(Path(__file__).resolve().parent.parent)

for p in (PRAXIS_PATH, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

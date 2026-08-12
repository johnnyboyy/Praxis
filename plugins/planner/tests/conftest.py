"""Shared test setup for the planner suite.

Puts the praxis skill dir and this plugin's dir on sys.path so that
`from workflow import ...`, `import registry`, `import run`, `from situation import ...`,
and the plugin's own `import planner_plugin` all resolve (the same way the uiux /
writing suites bootstrap).
"""

import sys
from pathlib import Path

PRAXIS_PATH = str(Path(__file__).resolve().parents[3])
PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)

for p in (PRAXIS_PATH, PLUGIN_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

"""Shared test setup for the writing suite.

Puts both the praxis skill dir and this plugin's dir on sys.path so that
`from workflow import ...`, `from contributors import ...`, `import registry`,
`import situation`, and the plugin's own `import writing_plugin` all resolve
(the same way the uiux suite bootstraps).
"""

import sys
from pathlib import Path

PRAXIS_PATH = str(Path(__file__).resolve().parents[3])
PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)

for p in (PRAXIS_PATH, PLUGIN_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

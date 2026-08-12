"""Shared test setup for the general suite.

Puts this plugin's dir on sys.path so `import general_plugin` resolves
(the same sys.path a consuming root would provide).
"""

import sys
from pathlib import Path

PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)

if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

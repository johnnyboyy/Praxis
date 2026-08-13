
import sys
from pathlib import Path

PRAXIS_PATH = str(Path(__file__).resolve().parents[3])
PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)

for p in (PRAXIS_PATH, PLUGIN_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

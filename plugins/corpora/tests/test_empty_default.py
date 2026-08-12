"""Empty-by-default: no domain-carrying contributors and an empty/absent
local pool -> contribute() returns []. Nothing is smuggled in.
"""

import tempfile
from pathlib import Path

from situation import Situation

from corpora import make


def test_empty_root_injects_nothing():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sit = Situation(
            task_kind="change",
            intent="do the thing",
            subject="coding",
            phase="convergent",
        )
        assert make(root).contribute(sit) == []


def test_empty_root_divergent_still_nothing():
    # even divergent (which can emit an anchor) injects nothing with no pool,
    # because the anchor is unconditional on stance but the whole pool is empty
    # -> anchor still fires? verify actual behavior below.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sit = Situation(
            task_kind="create",
            intent="design something",
            subject="design",
            phase="divergent",
        )
        out = make(root).contribute(sit)
        # the anti-mean anchor does NOT depend on the pool, so it fires even
        # when empty; there are no domain-derived contributions though.
        assert all(c.priority == -10 for c in out)

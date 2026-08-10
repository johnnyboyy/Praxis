"""Shared test helper: a stub corpora engine.

The sequence scripts (chunk_ledger, ratify_writeback, kill_graduation, domain_import, domain_migrate)
own ordering, preconditions, and guards; the engine verbs themselves are corpora's. To test the
orchestration without corpora present, we point each script's `--corpus-py` at a generated stub that
(1) appends its full argv to a log file so a test can assert *which verbs ran, in what order*, and
(2) exits non-zero for verbs a test names as failing, so the guard/stop logic can be exercised.
"""
from __future__ import annotations

import stat
from pathlib import Path

_STUB = '''#!/usr/bin/env python3
import sys, os
log = os.environ.get("STUB_LOG", "")
fail = set(x for x in os.environ.get("STUB_FAIL", "").split(",") if x)
argv = sys.argv[1:]
# corpus.py takes a global --root VALUE before the subcommand; skip it to find the verb.
scan = argv[:]
while scan and scan[0] == "--root":
    scan = scan[2:]
subcmd = scan[0] if scan else ""
if log:
    # First token is the resolved verb (so a test can read call[0]); the full argv follows.
    with open(log, "a") as f:
        f.write(subcmd + " " + " ".join(argv) + "\\n")
if subcmd in fail:
    sys.stderr.write(f"stub: {subcmd} configured to fail\\n")
    sys.exit(3)
if subcmd == "select":
    # compose: emit the JSON shape corpus.py's `select --json` returns. STUB_DOMAINS (comma-list)
    # is the composed domain set a test wants back; empty by default.
    import json
    doms = [d for d in os.environ.get("STUB_DOMAINS", "").split(",") if d]
    sys.stdout.write(json.dumps({"unit-of-work": "", "domains": doms}) + "\\n")
    sys.exit(0)
sys.stdout.write(f"stub-ok {subcmd}\\n")
sys.exit(0)
'''


def write_stub(dirpath: Path) -> Path:
    """Create the stub engine under dirpath, return its path (executable)."""
    p = Path(dirpath) / "stub_corpus.py"
    p.write_text(_STUB)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def read_log(log: Path) -> list[list[str]]:
    """Parse the invocation log into a list of argv lists (verbs in call order)."""
    if not Path(log).is_file():
        return []
    return [line.split() for line in Path(log).read_text().splitlines() if line.strip()]

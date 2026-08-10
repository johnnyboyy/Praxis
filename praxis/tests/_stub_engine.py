"""Shared praxis-core test helper: a GENERIC judgment-engine stub — it knows nothing of any real
engine (its compose verb is literally `compose`, its plugin name is just "stub").

Praxis-core tests must pass with ZERO real engine present. So they register this stub in praxis's
engine plugin slot: a tiny CLI that (1) logs its full argv so a test can assert which verbs ran in
what order, (2) exits non-zero for verbs named in STUB_FAIL so guard/stop logic can be exercised, and
(3) answers the `compose` verb with a JSON domain set (STUB_DOMAINS). A generic manifest maps praxis's
`compose` capability to this stub's `compose` verb and points `cli` at the stub.
"""
from __future__ import annotations

import json
import stat
from pathlib import Path

_STUB = '''#!/usr/bin/env python3
import sys, os
log = os.environ.get("STUB_LOG", "")
fail = set(x for x in os.environ.get("STUB_FAIL", "").split(",") if x)
argv = sys.argv[1:]
# A global --root VALUE may precede the verb; skip it to find the verb (mirrors a real engine's shape).
scan = argv[:]
while scan and scan[0] == "--root":
    scan = scan[2:]
subcmd = scan[0] if scan else ""
if log:
    with open(log, "a") as f:
        f.write(subcmd + " " + " ".join(argv) + "\\n")
if subcmd in fail:
    sys.stderr.write(f"stub: {subcmd} configured to fail\\n")
    sys.exit(3)
if subcmd == "compose":
    import json
    doms = [d for d in os.environ.get("STUB_DOMAINS", "").split(",") if d]
    sys.stdout.write(json.dumps({"unit-of-work": "", "domains": doms}) + "\\n")
    sys.exit(0)
if subcmd == "emit-parts":
    import json
    probs = [p for p in os.environ.get("STUB_PROBLEMS", "").split(",") if p]
    parts = [{"slot": "stance-frame", "body": "STANCE FRAME"},
             {"slot": "domains", "body": "## Domains\\n\\n### Domain: d1\\n\\nBODY-D1"},
             {"slot": "handoff-schema", "body": "HANDOFF SCHEMA"}]
    sys.stdout.write(json.dumps({"problems": probs, "parts": parts}) + "\\n")
    sys.exit(0)
sys.stdout.write(f"stub-ok {subcmd}\\n")
sys.exit(0)
'''

# The `compose` capability every praxis-core caller resolves (compose → the stub's `compose` verb).
COMPOSE_CAP = {
    "capability": "compose", "verb": "compose", "read_only": True,
    "args": [
        {"param": "root", "flag": "--root", "global": True},
        {"param": "unit_of_work", "flag": "--unit-of-work", "required": True},
        {"param": "json", "flag": "--json", "boolean": True},
    ],
}

# The judgment-import capability plugin_import resolves to stage a plugin's judgment face (through the
# engine's gate). Maps praxis's generic `import-file-pool` to the stub's `import-pool` verb.
IMPORT_POOL_CAP = {
    "capability": "import-file-pool", "verb": "import-pool",
    "args": [
        {"param": "root", "flag": "--root", "global": True},
        {"param": "source", "flag": "--source"},
    ],
}

# The spawn-parts capability spawn_prompt resolves: the engine injects its prompt parts + composition
# problems, praxis composes them. Maps praxis's generic `spawn-parts` → the stub's `emit-parts` verb.
SPAWN_PARTS_CAP = {
    "capability": "spawn-parts", "verb": "emit-parts", "read_only": True,
    "args": [
        {"param": "root", "flag": "--root", "global": True},
        {"param": "domains", "flag": "--domains", "required": True},
        {"param": "domains_dir", "flag": "--domains-dir"},
        {"param": "json", "flag": "--json", "boolean": True},
    ],
}

# The container-adoption capability plugin_import resolves (once per plugin domain) before staging, so
# a brand-new domain has an empty container to ratify into. Maps generic `adopt-domain` → `adopt-shell`.
ADOPT_CAP = {
    "capability": "adopt-domain", "verb": "adopt-shell",
    "args": [
        {"param": "root", "flag": "--root", "global": True},
        {"param": "source", "flag": "--source"},
    ],
}


def write_stub(dirpath: Path) -> Path:
    """Create the generic stub engine under dirpath, return its path (executable)."""
    p = Path(dirpath) / "stub_engine.py"
    p.write_text(_STUB)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def stub_manifest(stub_path: Path) -> dict:
    """A loaded-manifest dict (as `engine.load_manifest` returns) wired to the stub — for direct calls
    like `chunk_ledger.close(manifest, ...)` and `route.build_route(..., manifest)`."""
    return {"plugin": "stub", "capabilities": {"compose": COMPOSE_CAP},
            "cli": ["python3", str(stub_path)]}


def write_plugin_slot(dirpath: Path, stub_path: Path, extra_caps: list | None = None) -> Path:
    """Write a generic engine manifest into a fresh `plugins/` slot pointing at the stub (absolute
    entry), and return the slot dir — for subprocess tests that pass `--engine-plugins`. `extra_caps`
    adds further capabilities (e.g. IMPORT_POOL_CAP) beyond the default `compose`."""
    slot = Path(dirpath) / "plugins"
    slot.mkdir(parents=True, exist_ok=True)
    (slot / "stub.json").write_text(json.dumps({
        "plugin": "stub",
        "cli": {"command": "python3", "entry": str(Path(stub_path).resolve())},
        "capabilities": [COMPOSE_CAP, *(extra_caps or [])],
    }))
    return slot


def read_log(log: Path) -> list[list[str]]:
    """Parse the invocation log into a list of argv lists (verbs in call order)."""
    if not Path(log).is_file():
        return []
    return [line.split() for line in Path(log).read_text().splitlines() if line.strip()]

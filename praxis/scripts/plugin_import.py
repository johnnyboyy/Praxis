#!/usr/bin/env python3
"""plugin_import — snapshot-import a plugin's praxis-facing contribution into a project's praxis slots.

Part of praxis-core. This is the mechanism that "moves an engine (or any concern) in": it takes a
plugin *contribution* — a directory declaring, in its own `plugin.json`, which of its subdirs feed
which of praxis's slots — and copies those into a PROJECT's own `praxis/` slots. The project then
loads them as its own (root_tree/frame/handoff already read `<root>/praxis/...`), rather than
consuming the plugin live. That is the live-merge-retirement principle one level up: inheritance is an
explicit, auditable, deterministic *snapshot*, recorded in a lockfile so it can be re-synced but never
silently drifts.

Praxis-core names no engine here. It only reads the generic `provides` map (slot name → source subdir)
and moves files. The single slot-specific rule is still generic: a manifest imported into the ENGINE
slot that carries a `cli.entry` has that entry frozen to an absolute path — resolved relative to the
manifest's ORIGINAL location — so the engine CLI location travels with the import instead of depending
on where the contribution sits. (An engine's integration test does this same rewrite inline to simulate
"moving in"; here it is the real, tested, reusable step.)

Project slot layout (all under `<root>/praxis/`, beside the root marker `praxis/config.md`):
  engine   → praxis/engine/plugins/     handoff → praxis/handoff/plugins/
  phases   → praxis/phases/             scripts → praxis/scripts/

Provenance: `<root>/praxis/plugins.lock.json` records, per plugin, the absolute source it was imported
from, when, and exactly which files landed in each slot — so `sync` can re-pull from source and prune
files the plugin no longer provides, and `list` can report the project's imported surface.

Commands:
  import  --contribution DIR --root ROOT     snapshot-import a contribution into the project's slots
  list    --root ROOT [--json]               show what plugins are imported, from where
  sync    --root ROOT [--plugin NAME]        re-import each recorded plugin from its recorded source
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402  praxis-core's generic engine resolver (for the judgment-face staging)

import root_tree as rt  # noqa: E402  for praxis_dir — a root's marker dir (.praxis or legacy praxis)

# Slot name (as declared by a contribution's `provides`) → its home under a project's praxis dir
# (`.praxis/`, or legacy `praxis/` — resolved per root via `slot_path`). Generic: these are
# praxis's slots, named without reference to any engine.
SLOT_TARGETS = {
    "engine": Path("engine") / "plugins",
    "handoff": Path("handoff") / "plugins",
    "phases": Path("phases"),
    "scripts": Path("scripts"),
}

LOCKFILE_NAME = "plugins.lock.json"


def slot_path(root: Path, slot: str) -> Path:
    return rt.praxis_dir(root) / SLOT_TARGETS[slot]


def lock_path(root: Path) -> Path:
    return rt.praxis_dir(root) / LOCKFILE_NAME


class ImportError_(Exception):
    """A contribution or project shape problem — surfaced before any file is written."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def load_contribution(contribution: Path) -> dict:
    """Read a contribution's self-manifest (`plugin.json`): its name + `provides` (slot → subdir)."""
    cdir = Path(contribution).resolve()
    manifest = cdir / "plugin.json"
    if not manifest.is_file():
        raise ImportError_(f"no plugin.json in contribution {cdir} — not a praxis plugin contribution")
    data = json.loads(manifest.read_text())
    name = data.get("name")
    if not name:
        raise ImportError_(f"{manifest} declares no plugin name")
    provides = data.get("provides", {})
    unknown = [s for s in provides if s not in SLOT_TARGETS]
    if unknown:
        raise ImportError_(f"contribution declares unknown slot(s) {unknown}; "
                           f"praxis slots are {sorted(SLOT_TARGETS)}")
    return {"dir": cdir, "name": name, "provides": provides,
            "judgment_face": data.get("judgment_face")}


def _snapshot_engine_manifest(src: Path, dest: Path) -> None:
    """Copy an engine-slot manifest, freezing its `cli.entry` to an absolute path.

    The entry is resolved relative to the manifest's ORIGINAL directory (the same rule praxis's engine
    resolver uses at load time), then written back absolute. After this, the manifest points at its
    engine CLI regardless of where the copied manifest lives — the snapshot. A manifest without a
    `cli.entry` (e.g. a handoff-only plugin manifest that somehow lands here) is copied byte-for-byte.
    """
    data = json.loads(src.read_text())
    cli = data.get("cli")
    if isinstance(cli, dict) and cli.get("entry"):
        entry = Path(cli["entry"])
        if not entry.is_absolute():
            entry = (src.parent / entry).resolve()
        data["cli"] = {**cli, "entry": str(entry)}
        dest.write_text(json.dumps(data, indent=2) + "\n")
    else:
        shutil.copy2(src, dest)


def _import_slot(slot: str, src_dir: Path, target_dir: Path) -> list[str]:
    """Copy every file in a contribution's slot subdir into the project's slot. Returns the basenames
    landed (relative to the slot), so provenance can track and later prune exactly these."""
    if not src_dir.is_dir():
        raise ImportError_(f"contribution slot '{slot}' points at {src_dir}, which is not a directory")
    target_dir.mkdir(parents=True, exist_ok=True)
    landed: list[str] = []
    for src in sorted(src_dir.iterdir()):
        if src.name.startswith(".") or not src.is_file():
            continue
        dest = target_dir / src.name
        if slot == "engine" and src.suffix == ".json":
            _snapshot_engine_manifest(src, dest)
        else:
            shutil.copy2(src, dest)
        landed.append(src.name)
    return landed


def read_lock(root: Path) -> dict:
    lock = lock_path(root)
    if lock.is_file():
        return json.loads(lock.read_text())
    return {"plugins": {}}


def write_lock(root: Path, data: dict) -> None:
    lock_path(root).write_text(json.dumps(data, indent=2) + "\n")


def _prune_removed(root: Path, prev_slots: dict, new_slots: dict) -> list[str]:
    """Remove files this plugin imported previously that it no longer provides — keeping the project's
    slots a faithful snapshot of the current source, and touching ONLY this plugin's own files."""
    pruned: list[str] = []
    for slot, prev_files in prev_slots.items():
        keep = set(new_slots.get(slot, []))
        target_dir = slot_path(root, slot)
        for name in prev_files:
            if name not in keep:
                f = target_dir / name
                if f.is_file():
                    f.unlink()
                    pruned.append(str((target_dir / name).relative_to(root)))
    return pruned


def _adopt_domain_containers(manifest: dict, root: Path, source_dir: Path) -> list[str] | None:
    """Ask the engine to create an empty CONTAINER for each of the plugin's domains before principles
    are staged, so brand-new domains have something to ratify into. An empty container carries the
    domain's frontmatter only — no principles — so this is not a "write-directly" of judgment; the
    gate still owns every principle. Idempotent on the engine's side (an existing domain is left
    untouched). Returns the domain names adopted, or None if the engine declares no `adopt-domain`
    capability (older engine → leave container creation to the gate)."""
    adopted: list[str] = []
    for dom in sorted(source_dir.glob("*.md")):
        if dom.name == "audit.md":
            continue
        try:
            r = engine.resolve(manifest, "adopt-domain", {"root": str(root), "source": str(dom)})
        except engine.CapabilityError:
            return None
        if r.ok:
            adopted.append(dom.stem)
    return adopted


def _stage_judgment_face(root: Path, source_dir: Path) -> dict:
    """Stage a plugin's JUDGMENT face into the project — through the engine's gate, not a raw copy.

    A plugin's judgment face is a domains-dir (judgment content). Unlike a praxis slot (a plain file
    snapshot), judgment content enters a project through the registered judgment engine: praxis first
    asks the engine to adopt an empty container for each of the plugin's domains
    (`_adopt_domain_containers`), then stages the plugin's principles into them as *candidates for the
    engine's ratify gate* rather than writing them live — the "never write-directly" discipline held
    one level up. Praxis stays generic: it names the `adopt-domain` and `import-file-pool` capabilities
    and the source paths; the registered engine's manifest maps them to its verbs, and praxis never
    learns what a domain or a candidate is.

    Degrades: no engine registered, or an engine that doesn't declare the import capability, means the
    judgment face can't be staged yet — reported, never fatal (praxis owns no gate of its own)."""
    if not source_dir.is_dir():
        raise ImportError_(f"judgment_face points at {source_dir}, which is not a directory")
    manifest = engine.load_registered(slot_path(root, "engine"))
    if manifest is None:
        return {"source": str(source_dir), "staged": False,
                "note": "no judgment engine registered in the project — judgment face not staged; "
                        "import an engine first, then re-import this plugin"}
    adopted = _adopt_domain_containers(manifest, root, source_dir)
    try:
        res = engine.resolve(manifest, "import-file-pool",
                             {"root": str(root), "source": str(source_dir)}, timeout=60)
    except engine.CapabilityError:
        return {"source": str(source_dir), "staged": False,
                "note": f"engine '{manifest.get('plugin','?')}' declares no judgment-import capability"}
    if not res.ok:
        return {"source": str(source_dir), "staged": False, "note": res.note()}
    return {"source": str(source_dir), "staged": True, "note": "ok",
            "engine": manifest.get("plugin", "?"), "adopted": adopted, "output": res.stdout.strip()}


def import_contribution(contribution: Path, root: Path) -> dict:
    """Snapshot-import a contribution into a project's praxis slots and record it in the lockfile.

    Two faces: the PRAXIS face (manifests/phases/scripts) is a deterministic file snapshot into the
    project's praxis slots; the JUDGMENT face (a domains-dir) is staged through the registered engine's
    gate (see `_stage_judgment_face`). A judgment-only plugin declares no `provides` and just a
    `judgment_face`; a full-stack plugin declares both.

    Idempotent: re-importing the same plugin overwrites its files and prunes any it no longer provides.
    """
    root = Path(root).resolve()
    if not (rt.praxis_dir(root) / "config.md").is_file():
        raise ImportError_(f"{root} is not a praxis root (no .praxis/config.md or praxis/config.md) — "
                           f"cannot import into it")
    info = load_contribution(contribution)

    new_slots: dict[str, list[str]] = {}
    for slot, subdir in info["provides"].items():
        landed = _import_slot(slot, info["dir"] / subdir, slot_path(root, slot))
        new_slots[slot] = landed

    lock = read_lock(root)
    prev = lock["plugins"].get(info["name"], {})
    pruned = _prune_removed(root, prev.get("slots", {}), new_slots)

    record = {"source": str(info["dir"]), "imported_at": _now(), "slots": new_slots}
    judgment = None
    if info["judgment_face"]:
        judgment = _stage_judgment_face(root, info["dir"] / info["judgment_face"])
        record["judgment_face"] = {"path": info["judgment_face"], "staged": judgment["staged"],
                                   "note": judgment["note"]}
    lock["plugins"][info["name"]] = record
    write_lock(root, lock)
    return {"plugin": info["name"], "source": str(info["dir"]), "slots": new_slots,
            "pruned": pruned, "judgment": judgment}


def sync(root: Path, plugin: str | None) -> list[dict]:
    """Re-import each recorded plugin from its recorded source (snapshot-import-WITH-sync). Naming a
    plugin syncs only it. Re-reads source, so it re-freezes cli entries and prunes removed files."""
    root = Path(root).resolve()
    lock = read_lock(root)
    names = [plugin] if plugin else list(lock["plugins"])
    if plugin and plugin not in lock["plugins"]:
        raise ImportError_(f"no imported plugin '{plugin}' in {lock_path(root)}")
    results = []
    for name in names:
        source = Path(lock["plugins"][name]["source"])
        if not (source / "plugin.json").is_file():
            raise ImportError_(f"recorded source for '{name}' is gone: {source}")
        results.append(import_contribution(source, root))
    return results


def cmd_import(args) -> int:
    try:
        r = import_contribution(Path(args.contribution), Path(args.root))
    except ImportError_ as e:
        print(f"import failed: {e}", file=sys.stderr)
        return 1
    total = sum(len(v) for v in r["slots"].values())
    print(f"imported plugin '{r['plugin']}' → {total} praxis-face file(s) into {Path(args.root).resolve()}/praxis")
    for slot, files in r["slots"].items():
        if files:
            print(f"  {slot:<8} {', '.join(files)}")
    for p in r["pruned"]:
        print(f"  pruned   {p}")
    if r["judgment"] is not None:
        j = r["judgment"]
        if j["staged"]:
            adopted = j.get("adopted")
            containers = f", containers adopted: {', '.join(adopted)}" if adopted else ""
            status = f"staged as candidates at the engine's ratify gate{containers}"
        else:
            status = f"NOT staged ({j['note']})"
        print(f"  judgment {j['source']} → {status}")
    return 0


def cmd_list(args) -> int:
    lock = read_lock(Path(args.root))
    if args.json:
        print(json.dumps(lock, indent=2))
        return 0
    plugins = lock["plugins"]
    if not plugins:
        print(f"no plugins imported into {Path(args.root).resolve()}/praxis")
        return 0
    print(f"plugins imported into {Path(args.root).resolve()}/praxis:\n")
    for name, rec in plugins.items():
        total = sum(len(v) for v in rec["slots"].values())
        print(f"  {name}  ({total} files, from {rec['source']}, at {rec['imported_at']})")
        for slot, files in rec["slots"].items():
            if files:
                print(f"    {slot:<8} {', '.join(files)}")
    return 0


def cmd_sync(args) -> int:
    try:
        results = sync(Path(args.root), args.plugin)
    except ImportError_ as e:
        print(f"sync failed: {e}", file=sys.stderr)
        return 1
    for r in results:
        total = sum(len(v) for v in r["slots"].values())
        pr = f", pruned {len(r['pruned'])}" if r["pruned"] else ""
        print(f"synced '{r['plugin']}' from {r['source']} ({total} files{pr})")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="plugin_import", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    im = sub.add_parser("import", help="snapshot-import a contribution into a project's praxis slots")
    im.add_argument("--contribution", required=True, help="the plugin contribution dir (has plugin.json)")
    im.add_argument("--root", required=True, help="the project root (carries praxis/config.md)")
    im.set_defaults(func=cmd_import)

    ls = sub.add_parser("list", help="show plugins imported into a project")
    ls.add_argument("--root", required=True)
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=cmd_list)

    sy = sub.add_parser("sync", help="re-import recorded plugins from their recorded sources")
    sy.add_argument("--root", required=True)
    sy.add_argument("--plugin", default=None, help="sync only this plugin (default: all)")
    sy.set_defaults(func=cmd_sync)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

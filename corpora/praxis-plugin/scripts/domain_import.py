#!/usr/bin/env python3
# corpora-plugin script — corpora-specific orchestration (verbs resolved through the corpora engine
# manifest), distinct from praxis-core (root_tree, frame, handoff, engine).
"""domain_import — capability indirection for the browse -> file -> ratify import sequence.

Migrated from corpora `praxis-plugin/phases/domain-import.md`. No composition of its own; the one judgment
point (which destination domain a picked entry belongs to) is the ratify gate's existing
`domain-assignment-at-ratify-gate` judgment, reused. Each command is an independent dispatch through
the engine manifest (`_engine_link`) to corpora's own verbs — `browse` (`import-list`, read-only,
proposes nothing), `file`/`file-pool` (`import-candidate`/`import-default-pool`), and `ratify`
(`ratify-import-candidate`). No ordering between them is enforced here; a caller invoking `file`
before `browse` is not stopped by this script.

Commands:
  browse     --source DIR                                   import-list (read-only, proposes nothing)
  file       --source DIR --domain X --id ID [--as-domain D2] [--as-id ID2]   one candidate
  file-pool  [--source DIR]                                 import-default-pool (shape-matched batch)
  ratify     --id ID [--as-domain D2] [--as-id ID2]         ratify-import-candidate (per entry)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _engine_link as link  # noqa: E402
engine = link.engine


def _resolve(args, capability, params):
    return engine.resolve(link.manifest(), capability, params, cli=link.cli_override(args.corpus_py))


def cmd_browse(args) -> int:
    r = _resolve(args, "domain-import-list", {"source": args.source})
    engine.echo(r, "import-list")
    return 0 if r.ok else (r.returncode or 1)


def cmd_file(args) -> int:
    r = _resolve(args, "import-file", {
        "source": args.source, "domain": args.domain, "id": args.id,
        "as_domain": args.as_domain, "as_id": args.as_id})
    engine.echo(r, "import-candidate")
    return 0 if r.ok else (r.returncode or 1)


def cmd_file_pool(args) -> int:
    r = _resolve(args, "import-file-pool", {"source": args.source})
    engine.echo(r, "import-default-pool")
    return 0 if r.ok else (r.returncode or 1)


def cmd_ratify(args) -> int:
    r = _resolve(args, "import-ratify",
                 {"id": args.id, "as_domain": args.as_domain, "as_id": args.as_id})
    engine.echo(r, "ratify-import-candidate")
    return 0 if r.ok else (r.returncode or 1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="domain_import", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-py", default="",
                    help="override the corpora CLI (default: the manifest's declared corpus.py; tests override)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("browse", help="import-list: read-only, proposes nothing")
    b.add_argument("--source", required=True)
    b.set_defaults(func=cmd_browse)

    f = sub.add_parser("file", help="import-candidate: file one entry as a candidate")
    f.add_argument("--source", required=True)
    f.add_argument("--domain", required=True)
    f.add_argument("--id", required=True)
    f.add_argument("--as-domain", default="")
    f.add_argument("--as-id", default="")
    f.set_defaults(func=cmd_file)

    fp = sub.add_parser("file-pool", help="import-default-pool: shape-matched bulk candidate file")
    fp.add_argument("--source", default="")
    fp.set_defaults(func=cmd_file_pool)

    r = sub.add_parser("ratify", help="ratify-import-candidate: write one ratified entry back")
    r.add_argument("--id", required=True)
    r.add_argument("--as-domain", default="")
    r.add_argument("--as-id", default="")
    r.set_defaults(func=cmd_ratify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

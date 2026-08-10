#!/usr/bin/env python3
# corpora-plugin script — corpora-specific orchestration (verbs resolved through the corpora engine
# manifest), distinct from praxis-core (root_tree, frame, handoff, engine).
"""domain_migrate — the one-time domain-repo migration sequence, with its verification gate.

Migrated from corpora `praxis-plugin/phases/domain-repo-migration.md`. Composition is none (the process says so
outright: "mechanical `corpus.py` step plus a verification read"). Its deterministic content is a
sequence with a **hard verification gate**: materialize the effective domain set (`migrate-domains`),
then `measure`, then `verify` — and *do not proceed* if `verify` reports a discrepancy — then
`lint-domains`. Praxis owns "run these in order and STOP on a bad verify"; corpora owns every verb's
meaning (what gets materialized, the id-collision rule, the provenance stamping).

The gate is the whole point of scripting this rather than leaving it as prose: a human reading four
commands in a doc can run `lint-domains` even after `verify` failed; the script cannot.

Commands:
  run [--source PATH] [--root DIR]     migrate-domains -> measure -> verify (GATE) -> lint-domains
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _engine_link as link  # noqa: E402
engine = link.engine


def run(corpus_py, source: str | None, root: str | None) -> int:
    """`corpus_py` overrides the engine CLI (a path, e.g. a test stub) or None to use the manifest's."""
    manifest = link.manifest()
    cli = link.cli_override(corpus_py) if corpus_py else None

    def resolve(cap, params):
        return engine.resolve(manifest, cap, params, cli=cli)

    r = resolve("domain-migrate", {"root": root, "source": source})
    engine.echo(r, "migrate-domains")
    if not r.ok:
        sys.stdout.write("[stop] migration did not materialize cleanly; nothing verified.\n")
        return r.returncode or 1

    engine.echo(resolve("measure", {"root": root}), "measure")

    verify = resolve("domain-verify", {"root": root})
    engine.echo(verify, "verify")
    if not verify.ok:
        # The gate: a bad verify is a hard stop — the migration did not complete cleanly and the
        # project must NOT be trusted or advanced. lint-domains is deliberately not run.
        sys.stdout.write("[stop] verify reported a discrepancy — do not proceed. The materialized "
                         "files are recoverable via git (see the process's Rollback section); "
                         "lint-domains was not run.\n")
        return verify.returncode or 1

    lint = resolve("lint-domains",
                   {"domains_dir": str(Path(root or ".") /
                                       (".corpora" if (Path(root or ".") / ".corpora" / "config.md").is_file()
                                        else "corpora") / "domains")})
    engine.echo(lint, "lint-domains")
    return 0 if lint.ok else (lint.returncode or 1)


def cmd_run(args) -> int:
    return run(args.corpus_py or None, args.source or None, args.root or None)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="domain_migrate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-py", default="",
                    help="override the corpora CLI (default: the manifest's declared corpus.py; tests override)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="the gated migration sequence")
    r.add_argument("--source", default="", help="source domains-dir (defaults to the skill's own domains/)")
    r.add_argument("--root", default="", help="project root the engine operates on")
    r.set_defaults(func=cmd_run)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

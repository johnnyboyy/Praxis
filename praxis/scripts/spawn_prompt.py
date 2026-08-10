#!/usr/bin/env python3
"""spawn_prompt — compose a spawn-ready prompt from pluggable engine parts. Part of praxis-core.

One unit of work produces one spawn; this assembles that spawn's prompt. praxis owns the *skeleton*
(a `stance:` line on top, the engine's contributed parts in the middle, the `## Task` from the task
file on the bottom) and the *save lifecycle* (where the prompt lands, honoring the root's `debug:`
opt-in). The engine owns the *content*: it injects its parts through the `spawn-parts` capability —
the stance frame, the domain bodies, the handoff-read schema — and judges composition validity. praxis
composes whatever parts come back **without knowing what a part means** (each is just a slot + a body),
exactly as `handoff.py` composes a schema from base + plugin contributions. A different engine returns
different parts; nothing here names an engine or its prompt format.

Deterministic + decoupling:
  - The skeleton and the save policy are praxis's, read from praxis's own marker (`debug:`), never an
    engine's config.
  - The parts and the composition-validity judgment are the engine's, obtained by resolving the
    `spawn-parts` capability against whatever manifest is registered in the root's engine slot (auto-
    resolved, like frame/route). No engine registered → nothing to compose → praxis reports that and
    stops, rather than inventing a prompt.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import root_tree as rt  # noqa: E402
import engine  # noqa: E402
import handoff as ho  # noqa: E402  the praxis-owned debug/lifecycle reader


def governing_root(base: Path) -> Path | None:
    """The root this spawn belongs to: the nearest root at or above `base` (root_tree's upward walk).
    A spawn prompt is composed at a project root, so the root is where its engine slot and its save
    policy live."""
    return rt.governing_root_above(base)


def engine_spawn_parts(root: Path, domains: str, domains_dir: str | None,
                       manifest: dict | None) -> tuple[dict | None, str]:
    """Invoke the registered engine's `spawn-parts` hook: the engine-contributed prompt parts plus any
    composition problems. Returns (payload, note); payload is None when no engine is registered, it is
    unavailable, or it errored — praxis then has nothing to compose and stops."""
    payload, note = engine.call_json(
        manifest, "spawn-parts", {"root": str(root), "domains": domains, "domains_dir": domains_dir or "",
                                  "json": True},
        timeout=30, none_note="no engine registered — nothing to compose a spawn prompt from")
    if payload is None:
        return None, note
    try:
        payload["parts"]  # presence check
    except KeyError as e:
        return None, f"engine output not understood: {e}"
    return payload, "ok"


def assemble(stance: str, parts: list[dict], task_body: str) -> str:
    """praxis's prompt skeleton: the stance line, then each engine-contributed part in the order the
    engine returned it, then the task. praxis owns only the frame (stance header + task footer) and the
    ordering of the outer blocks; the engine owns each part's own content and internal structure.

    The ordering is also a caching contract: everything above the task footer is invariant for a
    given composition, so spawns of the same composition share a byte-identical prompt prefix and a
    multi-spawn batch hits the provider's prompt cache. Task-specific content goes in the footer
    only — inserting it earlier breaks the shared prefix for every spawn after the first."""
    blocks = [f"stance: {stance}"]
    blocks.extend(part["body"].strip("\n") for part in parts)
    blocks.append("## Task\n\n" + task_body.strip("\n"))
    return "\n\n".join(b for b in blocks if b) + "\n"


def build(base: Path, stance: str, domains: str, task_file: str, domains_dir: str | None,
          manifest: dict | None) -> tuple[str | None, dict]:
    """Compose the prompt. Returns (prompt|None, meta). prompt is None (and meta carries the reason)
    when there is no engine to compose from or the engine reports composition problems — praxis never
    emits a prompt past a failed composition gate."""
    root = governing_root(base)
    if root is None:
        return None, {"error": f"no governing root for {base} — cannot resolve an engine or save policy"}
    task_path = Path(task_file)
    if not task_path.is_file():
        return None, {"error": f"no such task file: {task_file}"}

    payload, note = engine_spawn_parts(root, domains, domains_dir, manifest)
    if payload is None:
        return None, {"error": note, "root": str(root)}
    problems = payload.get("problems") or []
    if problems:
        return None, {"error": "composition gate failed", "problems": problems, "root": str(root)}

    prompt = assemble(stance, payload["parts"], task_path.read_text())
    return prompt, {"root": str(root), "debug": ho.project_debug(root)}


def save_path(root: Path, composition: str, domains: str, output: str | None, debug: bool) -> str:
    """Where the prompt lands — a praxis-owned decision. Explicit `--output` wins; otherwise, when the
    root opted into `debug:`, a dated file under the praxis-owned `spawn-prompts/` dir; otherwise it is
    not saved (printed only)."""
    if output:
        return output
    if debug:
        slug = composition or domains.replace(",", "-")
        return str(rt.praxis_dir(root) / "spawn-prompts" / f"{datetime.date.today().isoformat()}-{slug}.md")
    return ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="spawn_prompt", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stance", required=True, help="the spawn's stance (a routing concept praxis owns)")
    ap.add_argument("--domains", required=True, help="comma-separated domain names for the composition")
    ap.add_argument("--task-file", required=True, help="path to a file holding the task description")
    ap.add_argument("--composition", default="", help="descriptive label, for the saved filename only")
    ap.add_argument("--output", default="", help="output path; overrides the debug-default save location")
    ap.add_argument("--domains-dir", default="", help="engine domains-dir override, passed through to the hook")
    ap.add_argument("--from", dest="frm", default=".", help="the project root to compose at (default cwd)")
    ap.add_argument("--engine-plugins", default=None,
                    help="the engine plugin slot to resolve from. Omit to auto-resolve the root's own slot.")
    args = ap.parse_args(argv)

    base = Path(args.frm).resolve()
    root = governing_root(base)
    slot = Path(args.engine_plugins) if args.engine_plugins is not None \
        else (engine.slot_for_root(root) if root else None)
    manifest = engine.load_registered(slot) if slot else None

    prompt, meta = build(base, args.stance, args.domains, args.task_file, args.domains_dir or None, manifest)
    if prompt is None:
        print(f"cannot compose spawn prompt: {meta['error']}", file=sys.stderr)
        for p in meta.get("problems", []):
            print(f"  • {p}", file=sys.stderr)
        return 2

    print(prompt)
    out = save_path(Path(meta["root"]), args.composition, args.domains, args.output or None, meta["debug"])
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(prompt)
        print(f"--- wrote {out} ---", file=sys.stderr)
    else:
        print("--- debug not enabled (praxis/config.md) — spawn prompt not saved; pass --output to "
              "save explicitly ---", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

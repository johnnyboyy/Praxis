#!/usr/bin/env python3
"""cascade — the DETACHED background worker that runs a plan's DAG independently of the MCP server,
so a big tasklist can be handed off and left to run across client/server restarts ("come back
later").

Where the thread variant died with the MCP server process, this launches a worker in its OWN session
(`start_new_session`), writes its progress to the journal (the shared source of truth), and is
guarded against double-runs by an flock + a pidfile in `.praxis/`. A re-invocation while a worker is
live is refused; after an interruption the next launch resumes from the journal (`run_dag(resume=
True)`), never re-spawning finished units. Observe progress with `conduct.plan_status` / the
`plan_status` tool — a new MCP server instance reads the same journal + pidfile, so it reattaches.

Layout: `run_cascade` is the core (reconstruct the plan → `run_dag(resume=True)`), testable
in-process with an injected executor; `main` is the worker CLI that holds the lock, records its pid,
and builds the real executor; `launch_detached` records the plan then spawns the worker detached.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal  # noqa: E402
import providers  # noqa: E402
from run import Plan, verifier_from_test_cmd  # noqa: E402
from schedule import run_dag  # noqa: E402


def _state_dir(root: Path) -> Path:
    for m in (".praxis", "praxis"):
        if (root / m).is_dir():
            return root / m
    return root / ".praxis"


def _pidfile(root: Path) -> Path:
    return _state_dir(root) / "cascade.pid"


def _lockpath(root: Path) -> Path:
    return _state_dir(root) / "cascade.lock"


def _logpath(root: Path) -> Path:
    return _state_dir(root) / "cascade.log"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_running(root: str | Path) -> dict | None:
    root = Path(root).resolve()
    pf = _pidfile(root)
    try:
        data = json.loads(pf.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data.get("pid"), int) and _pid_alive(data["pid"]):
        return data
    try:
        pf.unlink()
    except OSError:
        pass
    return None


def run_cascade(root: str | Path, *, executor, provider=None, test_cmd: str | None = None,
                concurrency: int | None = None, max_retries: int | None = None) -> dict:
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan"}
    prov = provider if provider is not None else providers.provider_for(root)
    verifier = verifier_from_test_cmd(test_cmd)
    result = run_dag(Plan(units=units), prov, executor, root, verifier=verifier,
                     concurrency=concurrency, max_retries=max_retries, resume=True)
    return {"status": "complete", **result}


def launch_detached(root: str | Path, tasks: list[dict], *, test_cmd: str | None = None,
                    model: str | None = None, max_retries: int | None = None,
                    concurrency: int | None = None, allow_edits: bool = False) -> dict:
    from conduct import _specs_for
    import plan as plan_mod
    root = Path(root).resolve()

    live = is_running(root)
    if live is not None:
        return {"status": "already-running", "since": live.get("started"), "pid": live.get("pid"),
                "note": "a detached cascade is already in flight for this root; poll plan_status"}

    units = plan_mod.plan_tasks(root, _specs_for(root, tasks))

    argv = [sys.executable, str(Path(__file__).resolve()), "run", "--root", str(root)]
    if test_cmd:
        argv += ["--test-cmd", test_cmd]
    if model:
        argv += ["--model", model]
    if concurrency is not None:
        argv += ["--concurrency", str(concurrency)]
    if max_retries is not None:
        argv += ["--max-retries", str(max_retries)]
    if allow_edits:
        argv += ["--allow-edits"]

    _spawn_daemon(argv, _logpath(root))
    return {"status": "running", "detached": True,
            "plan": {"units": [u.id for u in units],
                     "edges": [[d, u.id] for u in units for d in u.depends_on]},
            "note": "the cascade runs in a detached process — poll plan_status to watch units "
                    "complete; it survives an MCP-server restart, and re-launching resumes it"}


def _spawn_daemon(argv: list[str], logpath: Path) -> None:
    pid = os.fork()
    if pid > 0:
        os.waitpid(pid, 0)
        return
    try:
        os.setsid()
        if os.fork() > 0:
            os._exit(0)
        os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
        logfd = os.open(str(logpath), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(logfd, 1)
        os.dup2(logfd, 2)
        os.execv(argv[0], argv)
    except BaseException:
        os._exit(127)


def _build_executor(root: Path, *, model: str | None, allow_edits: bool):
    if os.environ.get("PRAXIS_CASCADE_FAKE"):
        from run import InlineExecutor, Receipt
        return InlineExecutor(lambda u, c: Receipt(outcome="result")), _fake_provider()
    from conduct import ClaudeExecutor
    return ClaudeExecutor(model=model, cwd=str(root), allow_edits=allow_edits), None


def _fake_provider():
    from providers import NullProvider
    return NullProvider()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cascade", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the registered plan's DAG to completion (the worker)")
    r.add_argument("--root", required=True)
    r.add_argument("--test-cmd", default=None)
    r.add_argument("--model", default=None)
    r.add_argument("--concurrency", type=int, default=None)
    r.add_argument("--max-retries", type=int, default=None)
    r.add_argument("--allow-edits", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()

    lock = open(_lockpath(root), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0

    _pidfile(root).write_text(json.dumps({"pid": os.getpid(), "started": time.time()}))
    executor, provider = _build_executor(root, model=a.model, allow_edits=a.allow_edits)
    try:
        run_cascade(root, executor=executor, provider=provider, test_cmd=a.test_cmd,
                    concurrency=a.concurrency, max_retries=a.max_retries)
    except Exception as e:
        journal.append(root, "conductor.plan", status="error", note=f"detached cascade failed: {e}")
    finally:
        try:
            _pidfile(root).unlink()
        except OSError:
            pass
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Isolated per-file parsing (spec Phase 3, D3.2).

Each file parses in a child process (spawn) with a size cap and timeout
enforced in the parent. Crash/timeout/oversize marks the file
`parse_failed`; the indexer continues. No shell use; repo code is read as
data and never executed or eval'd.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from pathlib import Path

from mentor import config as C
from mentor.parse import treesitter as T
from mentor.ingest import filters as F


def _child_target(box, func, func_args):
    """Module-level spawn target (must be picklable). Contained: exceptions
    are reported through the queue, never raised in the parent."""
    try:
        box.put({"ok": func(*func_args)})
    except Exception as exc:  # crash is contained, reported, never raised
        box.put({"ok": None, "reason": f"crash: {type(exc).__name__}"})


def _pool_target(inbox, outbox):
    """Serve loop for a persistent worker child (must be picklable).

    One job at a time; each job reuses `_child_target` so per-job crash
    containment is identical to `run_isolated`. `None` is the shutdown
    sentinel. A native crash kills this loop; the supervisor respawns.
    """
    while True:
        try:
            job = inbox.get()
        except Exception:
            return
        if job is None:
            return
        func, func_args = job
        _child_target(outbox, func, func_args)


class WorkerPool:
    """One persistent spawned child serving sequential isolated calls.

    Same per-call contract as `run_isolated` (timeout/crash shapes, caller
    retries, drain-while-join on every call), but the ~0.3s spawn tax is
    paid once per pool instead of once per file. The supervisor respawns on
    any crash/timeout response with FRESH queues before the next call, so a
    poisoned worker (or stale pipe bytes) can never affect a later file.
    Children are daemonized so no orphan survives the parent. Either reuse
    via `with WorkerPool(...) as pool` or call `close()` explicitly.
    """

    def __init__(self, timeout_s: float = C.PARSE_TIMEOUT_S):
        self.timeout_s = timeout_s
        self._ctx = mp.get_context("spawn")
        self._proc = None
        self._inbox = None
        self._outbox = None
        self.jobs = 0
        self.respawns = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _spawn(self):
        self._inbox = self._ctx.Queue()
        self._outbox = self._ctx.Queue()
        self._proc = self._ctx.Process(
            target=_pool_target, args=(self._inbox, self._outbox), daemon=True)
        self._proc.start()

    def _discard(self):
        proc, inbox = self._proc, self._inbox
        self._proc = None
        self._inbox = None
        self._outbox = None
        try:
            if proc is not None:
                if proc.is_alive():
                    proc.terminate()
                proc.join(_TEARDOWN_JOIN_S)
        finally:
            try:
                if inbox is not None:
                    inbox.put(None)
            except Exception:
                pass

    def _ensure(self):
        if self._proc is None:
            if self.jobs > 0 or self.respawns > 0:
                self.respawns += 1
            self._spawn()
        elif not self._proc.is_alive():
            self._discard()
            self.respawns += 1
            self._spawn()

    def run(self, fn, args: tuple, timeout_s: float | None = None) -> dict:
        """Serve one isolated call. Same return shapes as `run_isolated`."""
        limit = self.timeout_s if timeout_s is None else timeout_s
        self._ensure()
        self.jobs += 1
        try:
            self._inbox.put((fn, args))
        except Exception as exc:
            self._discard()
            return {"ok": None, "reason": f"crash: put-{type(exc).__name__}"}
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            try:
                return self._outbox.get_nowait()
            except queue.Empty:
                pass
            if not self._proc.is_alive():
                break
            self._proc.join(min(_POLL_INTERVAL_S,
                                max(0.0, deadline - time.monotonic())))
        if not self._proc.is_alive():
            try:
                return self._outbox.get(timeout=_EXIT_DRAIN_S)
            except queue.Empty:
                pass
        was_alive = self._proc.is_alive()
        self._discard()
        if was_alive:
            return {"ok": None, "reason": "timeout"}
        return {"ok": None, "reason": "crash: no-result"}

    def close(self):
        self._discard()


_MISSING = object()

_POLL_INTERVAL_S = 0.1
_EXIT_DRAIN_S = 5.0
_TEARDOWN_JOIN_S = 10.0


def _take(outbox) -> dict | object:
    """One non-blocking take from the result queue."""
    try:
        return outbox.get_nowait()
    except queue.Empty:
        return _MISSING


def run_isolated(fn, args: tuple, timeout_s: float) -> dict:
    """Run `fn(*args)` in a child process. Returns {'ok': result} or
    {'ok': None, 'reason': 'timeout'|'crash'}.

    Rendezvous rule (perf fix): the result queue is drained WHILE joining,
    never only after. Draining unblocks the child's feeder on results larger
    than the OS pipe buffer (~64KB measured); join-then-read deadlocks on
    those (parent waits for exit, exit waits for drain, drain waits for a
    read that never comes). Timeout semantics are unchanged: no result
    within `timeout_s` while the child is alive is still a timeout.
    """
    ctx = mp.get_context("spawn")
    outbox = ctx.Queue()
    proc = ctx.Process(target=_child_target, args=(outbox, fn, args))
    proc.start()
    deadline = time.monotonic() + timeout_s
    result = _MISSING
    while result is _MISSING and time.monotonic() < deadline:
        result = _take(outbox)
        if result is not _MISSING or not proc.is_alive():
            break
        proc.join(min(_POLL_INTERVAL_S, max(0.0, deadline - time.monotonic())))
    if result is _MISSING and not proc.is_alive():
        # Exited with data still in flight: one bounded blocking take.
        try:
            result = outbox.get(timeout=_EXIT_DRAIN_S)
        except queue.Empty:
            pass
    if result is not _MISSING:
        if proc.is_alive():
            proc.join(_TEARDOWN_JOIN_S)
            if proc.is_alive():
                proc.terminate()
                proc.join(_TEARDOWN_JOIN_S)
        return result
    if proc.is_alive():
        proc.terminate()
        proc.join(_TEARDOWN_JOIN_S)
        return {"ok": None, "reason": "timeout"}
    try:
        return outbox.get_nowait()
    except queue.Empty:
        return {"ok": None, "reason": "crash: no-result"}


def parse_file_nocheck(repo_root: str, relpath: str) -> dict:
    """Parse one file. Runs in the child; must stay import-safe."""
    from mentor.parse import py_extract, ts_extract  # deferred: child-side import
    root = Path(repo_root)
    path = root / relpath
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".py":
        return py_extract.extract_py(path, data, root)
    lang = T.LANGUAGE_FOR_EXT.get(suffix)
    if lang in ("typescript", "tsx"):
        return ts_extract.extract_ts(path, data, root, lang)
    return {"path": relpath, "language": "other", "status": "skipped_unsupported"}


def parse_one(repo_root: Path, relpath: str,
              timeout_s: float = C.PARSE_TIMEOUT_S,
              size_cap: int = C.PARSE_MAX_BYTES,
              pool: WorkerPool | None = None) -> dict:
    """Parent-side parse with size cap + timeout. Never raises for bad input.

    `pool`, when given, serves the isolated call from the persistent worker
    (same shapes and timeouts as `run_isolated`); otherwise one spawn is
    used, exactly as before.
    """
    root = repo_root.resolve()
    try:
        target = F.safe_join(root, relpath)
    except ValueError:
        return {"path": relpath, "status": "parse_failed", "reason": "path-escape"}
    try:
        if F.is_link(target) or not target.is_file():
            return {"path": relpath, "status": "parse_failed", "reason": "not-regular-file"}
        if target.stat().st_size > size_cap:
            return {"path": relpath, "status": "parse_failed", "reason": "size"}
    except OSError as exc:
        return {"path": relpath, "status": "parse_failed", "reason": f"stat: {exc}"}
    if pool is not None:
        result = pool.run(parse_file_nocheck, (str(root), relpath), timeout_s)
    else:
        result = run_isolated(parse_file_nocheck, (str(root), relpath), timeout_s)
    if result.get("ok") is None:
        return {"path": relpath, "status": "parse_failed",
                "reason": result.get("reason", "unknown")}
    return result["ok"]


def parse_many(repo_root: Path, relpaths: list[str],
               timeout_s: float = C.PARSE_TIMEOUT_S,
               size_cap: int = C.PARSE_MAX_BYTES,
               retries: int = 1, progress=None,
               pool: WorkerPool | None = None) -> dict[str, dict]:
    """Parse files sequentially (one child at a time). Deterministic order.

    Transient worker deaths (proven: identical input passes and crashes
    across runs in tree-sitter 0.26.0 on Windows) are retried `retries`
    times in a fresh process. Only crash/timeout reasons retry; deterministic
    skips (size, path-escape, unsupported) never retry. Persistent failures
    stay `parse_failed`. Each result carries its attempt count. `progress`,
    if given, is called as `progress(done, total)` after each file (used by
    CLI progress logging; never affects results).
    """
    out: dict[str, dict] = {}
    remaining = sorted(relpaths)
    total = len(remaining)
    attempt = 0
    own_pool = pool is None
    if own_pool:
        pool = WorkerPool(timeout_s)
    assert pool is not None
    try:
        while remaining and attempt <= retries:
            attempt += 1
            retry: list[str] = []
            for rel in remaining:
                res = parse_one(repo_root, rel, timeout_s, size_cap, pool=pool)
                res["attempts"] = attempt
                out[rel] = res
                if progress is not None:
                    progress(len(out), total)
            reason = res.get("reason", "")
            if res.get("status") != "parsed" and (
                    reason == "timeout" or reason.startswith("crash")):
                retry.append(rel)
            remaining = retry
    finally:
        if own_pool:
            assert pool is not None
            pool.close()
    return out


def check_ranges(parsed: dict, lines: list[str]) -> list[str]:
    """Line-invariant violations: 1 <= start <= end <= file_lines, the
    symbol name appears on its signature line, and the signature line is
    the symbol's first text line (start_line == signature_line)."""
    problems = []
    total = parsed.get("file_lines", 0)
    for sym in parsed.get("symbols", []):
        start, end = sym["start_line"], sym["end_line"]
        if not (1 <= start <= end <= total):
            problems.append(f"{sym['qualname']}: range [{start},{end}] outside 1..{total}")
            continue
        if sym["signature_line"] != start:
            problems.append(f"{sym['qualname']}: signature {sym['signature_line']} != start {start}")
        first = lines[start - 1] if 0 < start <= len(lines) else ""
        if sym["name"] not in first and sym["name"] != "<anonymous>":
            problems.append(f"{sym['qualname']}: name not on signature line {start}")
    return problems

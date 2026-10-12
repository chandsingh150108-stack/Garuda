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


def run_isolated(fn, args: tuple, timeout_s: float) -> dict:
    """Run `fn(*args)` in a child process. Returns {'ok': result} or
    {'ok': None, 'reason': 'timeout'|'crash'}."""
    ctx = mp.get_context("spawn")
    outbox = ctx.Queue()
    proc = ctx.Process(target=_child_target, args=(outbox, fn, args))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(10)
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
              size_cap: int = C.PARSE_MAX_BYTES) -> dict:
    """Parent-side parse with size cap + timeout. Never raises for bad input."""
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
    result = run_isolated(parse_file_nocheck, (str(root), relpath), timeout_s)
    if result.get("ok") is None:
        return {"path": relpath, "status": "parse_failed",
                "reason": result.get("reason", "unknown")}
    return result["ok"]


def parse_many(repo_root: Path, relpaths: list[str],
               timeout_s: float = C.PARSE_TIMEOUT_S,
               size_cap: int = C.PARSE_MAX_BYTES,
               retries: int = 1) -> dict[str, dict]:
    """Parse files sequentially (one child at a time). Deterministic order.

    Transient worker deaths (proven: identical input passes and crashes
    across runs in tree-sitter 0.26.0 on Windows) are retried `retries`
    times in a fresh process. Only crash/timeout reasons retry; deterministic
    skips (size, path-escape, unsupported) never retry. Persistent failures
    stay `parse_failed`. Each result carries its attempt count.
    """
    out: dict[str, dict] = {}
    remaining = sorted(relpaths)
    attempt = 0
    while remaining and attempt <= retries:
        attempt += 1
        retry: list[str] = []
        for rel in remaining:
            res = parse_one(repo_root, rel, timeout_s, size_cap)
            res["attempts"] = attempt
            out[rel] = res
            reason = res.get("reason", "")
            if res.get("status") != "parsed" and (
                    reason == "timeout" or reason.startswith("crash")):
                retry.append(rel)
        remaining = retry
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

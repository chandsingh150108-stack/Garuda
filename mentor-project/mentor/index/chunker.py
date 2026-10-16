"""AST split-then-merge chunker (spec Phase 4, D4.1-D4.3).

Code files: AST units from an isolated child process (same containment as
D3.2), recursive split at child boundaries, greedy merge of small siblings.
Other indexed text files: degraded line windows (80 lines / 20 overlap).
`text` is always exact source lines; `embed_text` adds a header and is never
used for citations. No content line is ever dropped: gaps between AST units
are emitted as their own spans.
"""
from __future__ import annotations

from pathlib import Path

from mentor.index import hashing as H
from mentor.index import identifiers as I
from mentor.ingest import filters as F
from mentor.parse import parse_worker as W
from mentor.parse import treesitter as T

CHUNK_BUDGET_TOKENS = 512
LINE_WINDOW = 80
LINE_OVERLAP = 20
PLAN_MAX_DEPTH = 16
CODE_EXTS = set(T.LANGUAGE_FOR_EXT)


def approx_tokens(text: str) -> int:
    """Deterministic size approximation: characters // 4 (recorded in D4.1)."""
    return len(text) // 4


def slice_text(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1:end])


def _plan_in_child(repo_root: str, relpath: str, language: str, max_depth: int) -> dict:
    """Child-side: nested AST units {start,end,kind,children}. Import-safe."""
    root = Path(repo_root)
    data = (root / relpath).read_bytes()
    tree = T.parse_bytes(language, data)
    total = len(data.decode("utf-8", errors="replace").splitlines())

    def unit(node, depth: int) -> dict:
        start = node.start_point.row + 1
        end = node.end_point.row + 1
        kids = []
        if depth < max_depth:
            kids = [unit(c, depth + 1) for c in node.children
                    if c.is_named and c.end_point.row >= c.start_point.row
                    and not (c.start_point.row + 1 == start and c.end_point.row + 1 == end
                             and c.type == node.type and len(node.children) == 1)]
        return {"start": start, "end": end, "kind": node.type, "children": kids}

    top = [unit(c, 1) for c in tree.root_node.children if c.is_named]
    return {"status": "ok", "file_lines": total, "units": top}


def plan_file(repo_root: Path, relpath: str, language: str,
              timeout_s: float = 10.0, retries: int = 1) -> dict:
    """Parent-side AST plan with timeout. Never raises for bad input.

    Transient worker deaths retry once in a fresh process (same policy as
    D3.2 clarification); deterministic failures never retry.
    """
    root = repo_root.resolve()
    try:
        target = F.safe_join(root, relpath)
    except ValueError:
        return {"status": "failed", "reason": "path-escape"}
    try:
        if F.is_link(target) or not target.is_file():
            return {"status": "failed", "reason": "not-regular-file"}
    except OSError as exc:
        return {"status": "failed", "reason": f"stat: {exc}"}
    attempts = 0
    while True:
        attempts += 1
        result = W.run_isolated(_plan_in_child,
                                (str(root), relpath, language, PLAN_MAX_DEPTH), timeout_s)
        if result.get("ok") is not None:
            return result["ok"]
        reason = result.get("reason", "unknown")
        if attempts > retries or not (reason == "timeout" or reason.startswith("crash")):
            return {"status": "failed", "reason": reason}


def _spans_from_children(start: int, end: int, children: list[dict],
                         lines: list[str], budget: int,
                         out: list[tuple[int, int, bool, str]]):
    """Split [start,end] using child boundaries; gaps become their own spans."""
    kids = sorted(
        (k for k in children if k["end"] >= k["start"]
         and k["start"] >= start and k["end"] <= end),
        key=lambda k: (k["start"], k["end"]))
    cursor = start
    for kid in kids:
        if kid["start"] > cursor:
            _split_span(cursor, kid["start"] - 1, [], lines, budget, out)
        _split_span(kid["start"], kid["end"], kid["children"], lines, budget, out)
        cursor = max(cursor, kid["end"] + 1)
    if cursor <= end:
        _split_span(cursor, end, [], lines, budget, out)


def _split_span(start: int, end: int, children: list[dict], lines: list[str],
                budget: int, out: list[tuple[int, int, bool, str]]):
    if start > end:
        return
    text = slice_text(lines, start, end)
    if approx_tokens(text) <= budget:
        out.append((start, end, False, "ast"))
        return
    if start == end:
        # Single line spans are atomic (spans are line-granular; children of
        # a one-line node share its exact range, so recursing would re-emit
        # the same line once per descendant). Over budget => exception.
        out.append((start, end, True, "ast"))
        return
    if children:
        _spans_from_children(start, end, children, lines, budget, out)
        return
    # Multi-line span with no AST children (blank/comment run or cap): split
    # by lines so content is never dropped and budget holds. A single line
    # that alone exceeds the budget is the unsplittable leaf → exception.
    max_chars = budget * 4
    cur_start = start
    cur_chars = 0
    for ln in range(start, end + 1):
        width = len(lines[ln - 1]) + 1
        if cur_chars + width > max_chars and ln > cur_start:
            single = cur_start == ln - 1
            exc = single and approx_tokens(lines[cur_start - 1]) > budget
            out.append((cur_start, ln - 1, exc, "lines"))
            cur_start = ln
            cur_chars = 0
        cur_chars += width
    tail_exc = cur_start == end and approx_tokens(lines[end - 1]) > budget
    out.append((cur_start, end, tail_exc, "lines"))


def split_units(units: list[dict], lines: list[str], budget: int = CHUNK_BUDGET_TOKENS,
                ) -> list[tuple[int, int, bool, str]]:
    """Split top-level units into (start, end, is_exception, method) spans."""
    total = len(lines)
    out: list[tuple[int, int, bool, str]] = []
    cursor = 1
    for unit in sorted(units, key=lambda u: (u["start"], u["end"])):
        if unit["start"] > cursor:
            _split_span(cursor, unit["start"] - 1, [], lines, budget, out)
        _split_span(unit["start"], min(unit["end"], total),
                    unit.get("children", []), lines, budget, out)
        cursor = max(cursor, min(unit["end"], total) + 1)
    if cursor <= total:
        _split_span(cursor, total, [], lines, budget, out)
    # Defense in depth for the chunk_id UNIQUE constraint: identical ranges
    # from overlapping units collapse to one span (same range => same text =>
    # same chunk). Keeps first occurrence for determinism.
    seen: set[tuple[int, int]] = set()
    unique = []
    for span in out:
        key = (span[0], span[1])
        if key in seen:
            continue
        seen.add(key)
        unique.append(span)
    return [(s, e, x, m) for (s, e, x, m) in unique
            if s >= 1 and e <= total and s <= e]


def merge_spans(spans: list[tuple[int, int, bool, str]], lines: list[str],
                budget: int = CHUNK_BUDGET_TOKENS,
                ) -> list[tuple[int, int, bool, str]]:
    """Greedy merge of adjacent spans while within budget. Exceptions (single
    over-budget leaves) never merge — they stay exactly one line."""
    merged: list[tuple[int, int, bool, str]] = []
    cur = None  # [start, end, method]
    for (start, end, exc, method) in sorted(spans):
        if exc:
            if cur is not None:
                merged.append((cur[0], cur[1], False, cur[2]))
                cur = None
            merged.append((start, end, True, method))
            continue
        text = slice_text(lines, start, end)
        if cur is None:
            cur = [start, end, method]
        elif approx_tokens(slice_text(lines, cur[0], end)) <= budget:
            cur[1] = end
            if method == "lines":
                cur[2] = method
        else:
            merged.append((cur[0], cur[1], False, cur[2]))
            cur = [start, end, method]
    if cur is not None:
        merged.append((cur[0], cur[1], False, cur[2]))
    return merged


def chunk_line_windows(lines: list[str], window: int = LINE_WINDOW,
                       overlap: int = LINE_OVERLAP,
                       budget: int = CHUNK_BUDGET_TOKENS,
                       ) -> list[tuple[int, int, bool, str]]:
    """Degraded fallback for non-code text: up-to-`window` line spans with up
    to `overlap` lines of overlap, each within `budget` tokens. A single
    line over budget is the unsplittable leaf (exception). Budget is hard;
    overlap is best-effort (short budget-cut windows overlap less)."""
    total = len(lines)
    if total == 0:
        return []
    max_chars = budget * 4
    spans: list[tuple[int, int, bool, str]] = []
    start = 1
    while start <= total:
        end = start
        chars = 0
        while (end <= total and (end - start) < window
               and chars + len(lines[end - 1]) + 1 <= max_chars):
            chars += len(lines[end - 1]) + 1
            end += 1
        if end == start:
            spans.append((start, start, True, "lines"))
            start += 1
            continue
        spans.append((start, end - 1, False, "lines"))
        if end > total:
            break
        start = max(start + 1, end - overlap)
    return spans


def assemble(repo_sha: str, path: str, spans: list[tuple[int, int, bool, str]],
             symbols: list[dict], lines: list[str]) -> list[dict]:
    """Build chunk records with exact text, headers, hashes, and IDs."""
    chunks = []
    for (start, end, exc, method) in spans:
        text = slice_text(lines, start, end)
        content_hash = H.sha256_text(text)
        quals = sorted({s["qualname"] for s in symbols
                        if s["start_line"] <= end and s["end_line"] >= start})
        header = path + ((" | " + ", ".join(quals)) if quals else "")
        chunks.append({
            "chunk_id": H.chunk_id(repo_sha, path, start, end, content_hash),
            "path": path, "start_line": start, "end_line": end,
            "method": method, "header": header, "text": text,
            "embed_text": header + "\n" + text,
            "identifiers": I.identifiers_text(text, path),
            "content_hash": content_hash,
            "approx_tokens": approx_tokens(text),
            "is_exception": exc, "symbols": quals,
        })
    return chunks


def chunk_file(repo_root: Path, relpath: str, symbols: list[dict],
               timeout_s: float = 10.0,
               budget: int = CHUNK_BUDGET_TOKENS,
               force_lines: bool = False) -> dict:
    """Chunk one indexed file. Returns {status, chunks} or {status: failed}.

    `force_lines` skips the AST plan (and its worker spawn + timeout budget)
    and goes straight to degraded line windows. Used for files whose Phase 3
    parse already failed: re-spending up to 2x timeout there is pure burn,
    and the parses record already documents the cause.
    """
    root = repo_root.resolve()
    try:
        target = F.safe_join(root, relpath)
        raw = target.read_bytes()
    except (ValueError, OSError) as exc:
        return {"status": "failed", "reason": str(exc)}
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if not lines:
        return {"status": "ok", "spans": [], "lines": []}
    suffix = Path(relpath).suffix.lower()
    language = T.LANGUAGE_FOR_EXT.get(suffix)
    spans: list[tuple[int, int, bool, str]] | None = None
    if language in ("python", "typescript", "tsx") and not force_lines:
        plan = plan_file(root, relpath, language, timeout_s)
        if plan.get("status") == "ok":
            spans = merge_spans(split_units(plan["units"], lines, budget), lines, budget)
    if spans is None:
        spans = chunk_line_windows(lines, budget=budget)
    return {"status": "ok", "spans": spans, "lines": lines}

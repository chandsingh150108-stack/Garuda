"""Exact + prefix symbol lookup (spec Phase 5, D5.2).

Matches query identifiers against symbol names and qualified names (exact
first, then prefix), then maps symbols to chunks by path + line-range
overlap. Returns chunk IDs ranked by match quality. Parameterized only.
"""
from __future__ import annotations

import sqlite3

from mentor.retrieve import analyze as A


def _chunks_for_symbol(con: sqlite3.Connection, sha: str, path: str,
                       start: int, end: int) -> list[str]:
    rows = con.execute(
        "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path = ?"
        " AND start_line <= ? AND end_line >= ? ORDER BY chunk_id",
        (sha, path, end, start)).fetchall()
    return [r[0] for r in rows]


def search_symbols(con: sqlite3.Connection, sha: str, analysis: A.QueryAnalysis,
                   k: int) -> list[dict]:
    """Return [{chunk_id, rank}] with rank = 1-based match order."""
    seen: list[str] = []
    seen_set: set[str] = set()

    def emit(cid: str):
        if cid not in seen_set:
            seen_set.add(cid)
            seen.append(cid)

    # Pass 1: exact name or qualname match.
    for ident in analysis.identifiers:
        rows = con.execute(
            "SELECT path, start_line, end_line FROM symbols"
            " WHERE snapshot_sha = ? AND (name = ? OR qualname = ?)"
            " ORDER BY path, start_line",
            (sha, ident, ident)).fetchall()
        for path, start, end in rows:
            for cid in _chunks_for_symbol(con, sha, path, start, end):
                emit(cid)
                if len(seen) >= k:
                    return [{"chunk_id": c, "rank": i + 1} for i, c in enumerate(seen)]
    # Pass 2: prefix match on name or qualname.
    for ident in analysis.identifiers:
        like = ident.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = con.execute(
            "SELECT path, start_line, end_line FROM symbols"
            " WHERE snapshot_sha = ? AND (name LIKE ? ESCAPE '\\'"
            " OR qualname LIKE ? ESCAPE '\\')"
            " ORDER BY path, start_line",
            (sha, like, like)).fetchall()
        for path, start, end in rows:
            for cid in _chunks_for_symbol(con, sha, path, start, end):
                emit(cid)
                if len(seen) >= k:
                    return [{"chunk_id": c, "rank": i + 1} for i, c in enumerate(seen)]
    return [{"chunk_id": c, "rank": i + 1} for i, c in enumerate(seen)]

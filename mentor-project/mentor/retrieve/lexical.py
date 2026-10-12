"""Lexical BM25 retrieval over FTS5 (spec Phase 5, D5.2).

MATCH queries are built from tokenized terms only (lowercase alphanumerics,
double-quoted, OR-joined) and passed as a bound parameter — repository and
query text never touch SQL syntax. Terms within one query token form a phrase
only when adjacent in the analyzed token stream; across tokens we use OR for
recall and let BM25 rank.
"""
from __future__ import annotations

import re
import sqlite3

from mentor.retrieve import analyze as A


def build_match(terms: list[str]) -> str:
    """Quote each term; join with OR. Safe alphabet by construction."""
    clean = [t for t in terms if re.fullmatch(r"[a-z0-9]+", t)]
    return " OR ".join(f'"{t}"' for t in clean)


def search_lexical(con: sqlite3.Connection, analysis: A.QueryAnalysis,
                   k: int) -> list[dict]:
    """Return [{chunk_id, rank}] ordered best-first (bm25 ascending)."""
    match = build_match(A.fts_terms(analysis))
    if not match:
        return []
    rows = con.execute(
        "SELECT chunk_id, bm25(chunks_fts) AS rank FROM chunks_fts"
        " WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
        (match, k)).fetchall()
    return [{"chunk_id": r[0], "rank": r[1]} for r in rows]

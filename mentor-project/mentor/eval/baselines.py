"""Named retrieval baselines (spec Phase 6).

B1: lexical BM25 only. B3: fused lexical+symbol+path (the MVP). Vector-only
B2, no-retrieval B6, long-context and agentic variants are defined in their
own phases (7, 9, 22) — never silently.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

BASELINES = ("B1", "B3")


def run(baseline: str, db: Path, sha: str, query: str, k: int = 10) -> list[dict]:
    if baseline not in BASELINES:
        raise ValueError(f"unknown baseline: {baseline}")
    if baseline == "B3":
        from mentor.retrieve import search as SR
        return SR.search(db, sha, query, k=k)["hits"]
    # B1: lexical only.
    from mentor.retrieve import analyze as A
    from mentor.retrieve import lexical as L
    analysis = A.analyze(query)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        ranked = L.search_lexical(con, analysis, k)
        hits = []
        for entry in ranked:
            row = con.execute(
                "SELECT path, start_line, end_line FROM chunks"
                " WHERE chunk_id = ? AND snapshot_sha = ?",
                (entry["chunk_id"], sha)).fetchone()
            if row:
                hits.append({"chunk_id": entry["chunk_id"], "path": row[0],
                             "start_line": row[1], "end_line": row[2],
                             "score": entry["rank"], "retrievers": ["lexical"]})
        return hits
    finally:
        con.close()

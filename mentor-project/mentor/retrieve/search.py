"""Fused search over one repository index (spec Phase 5).

Combines BM25 + symbol + path rankings with RRF and returns hits with
chunk ranges, contributing retrievers, and confidence signals. The database
is opened read-only: search never modifies the index.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from mentor.retrieve import analyze as A
from mentor.retrieve import confidence as CF
from mentor.retrieve import fusion as FU
from mentor.retrieve import lexical as L
from mentor.retrieve import paths as PT
from mentor.retrieve import symbols as SY

RANKING_DEPTH = 50


def search(db: Path, sha: str, query: str, k: int = 10,
           depth: int = RANKING_DEPTH) -> dict:
    """Run fused retrieval. Returns {query, analysis, hits, confidence}."""
    analysis = A.analyze(query)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        lex = L.search_lexical(con, analysis, depth)
        sym = SY.search_symbols(con, sha, analysis, depth)
        pth = PT.search_paths(con, sha, analysis, depth)
        rankings = [[h["chunk_id"] for h in lex],
                    [h["chunk_id"] for h in sym],
                    [h["chunk_id"] for h in pth]]
        names = ("lexical", "symbol", "path")
        contributors: dict[str, set[str]] = {}
        for name, ranking in zip(names, rankings):
            for hit in ranking:
                contributors.setdefault(hit, set()).add(name)
        fused = FU.fuse(rankings)
        hits = []
        for chunk_id, score in fused[:k]:
            row = con.execute(
                "SELECT path, start_line, end_line, header FROM chunks"
                " WHERE chunk_id = ? AND snapshot_sha = ?",
                (chunk_id, sha)).fetchone()
            if row is None:
                continue
            hits.append({"chunk_id": chunk_id, "path": row[0],
                         "start_line": row[1], "end_line": row[2],
                         "header": row[3], "score": score,
                         "retrievers": sorted(contributors.get(chunk_id, set()))})
        conf = CF.confidence(con, analysis, fused, rankings)
    finally:
        con.close()
    return {"query": query,
            "analysis": {"identifiers": analysis.identifiers, "routes": analysis.routes,
                         "files": analysis.files, "words": analysis.words[:12]},
            "hits": hits, "confidence": conf}

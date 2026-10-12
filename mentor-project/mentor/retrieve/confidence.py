"""Confidence signals for abstention gating (spec Phase 5, D5.3).

Emitted for every query; thresholds stay GATED to Phase 9 calibration.
Signals: top fused score; identifier coverage (fraction of extracted
identifiers whose parts all appear in the top-10 chunks' identifier text);
two-retriever agreement (whether >=2 rankings put the same chunk first).
"""
from __future__ import annotations

import re
import sqlite3

from mentor.index import identifiers as I
from mentor.retrieve import analyze as A


def identifier_coverage(con: sqlite3.Connection, analysis: A.QueryAnalysis,
                        top_ids: list[str]) -> float:
    """Fraction of identifiers with all parts present in top chunk terms."""
    if not analysis.identifiers:
        return 1.0
    if not top_ids:
        return 0.0
    placeholders = ",".join("?" for _ in top_ids)
    rows = con.execute(
        f"SELECT identifiers FROM chunks WHERE chunk_id IN ({placeholders})",
        tuple(top_ids)).fetchall()
    union: set[str] = set()
    for (blob,) in rows:
        union.update(re.findall(r"[a-z0-9]+", blob.lower()))
    hits = 0
    for ident in analysis.identifiers:
        parts = I.split_identifier(ident)
        if parts and all(p in union for p in parts):
            hits += 1
    return hits / len(analysis.identifiers)


def retriever_agreement(rankings: list[list[str]]) -> bool:
    """True when >=2 non-empty rankings agree on rank 1."""
    firsts = [r[0] for r in rankings if r]
    return len(firsts) >= 2 and len(set(firsts)) < len(firsts)


def confidence(con: sqlite3.Connection, analysis: A.QueryAnalysis,
               fused: list[tuple[str, float]],
               rankings: list[list[str]]) -> dict:
    top = fused[:10]
    return {
        "top_score": fused[0][1] if fused else 0.0,
        "identifier_coverage": identifier_coverage(con, analysis, [c for c, _ in top]),
        "two_retriever_agreement": retriever_agreement(rankings),
    }

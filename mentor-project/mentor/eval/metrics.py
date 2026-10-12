"""Retrieval metrics (spec Phase 6, D6.2-D6.3).

A retrieval hit is relevant iff its line range overlaps a gold range in the
same file. Metrics are reported with n + Wilson 95% intervals (stats.py).
"""
from __future__ import annotations


def overlaps(path: str, start: int, end: int, gold_path: str,
             gold_start: int, gold_end: int) -> bool:
    return path == gold_path and start <= gold_end and gold_start <= end


def relevant(hit: dict, gold_ranges: list) -> bool:
    ranges = [(g["path"] if isinstance(g, dict) else g.path,
               g["start_line"] if isinstance(g, dict) else g.start_line,
               g["end_line"] if isinstance(g, dict) else g.end_line)
              for g in gold_ranges]
    return any(overlaps(hit["path"], hit["start_line"], hit["end_line"],
                       gp, gs, ge) for gp, gs, ge in ranges)


def recall_at_k(ranked_hits: list[dict], gold_ranges: list, k: int) -> float:
    """Fraction of gold ranges hit by at least one top-k result."""
    ranges = [g for g in gold_ranges]
    if not ranges:
        return 1.0
    hits = ranked_hits[:k]
    covered = 0
    for g in ranges:
        gp = g["path"] if isinstance(g, dict) else g.path
        gs = g["start_line"] if isinstance(g, dict) else g.start_line
        ge = g["end_line"] if isinstance(g, dict) else g.end_line
        if any(overlaps(h["path"], h["start_line"], h["end_line"], gp, gs, ge)
               for h in hits):
            covered += 1
    return covered / len(ranges)


def mrr(ranked_hits: list[dict], gold_ranges: list) -> float:
    """Mean reciprocal rank of the first relevant hit (0.0 if none)."""
    for i, hit in enumerate(ranked_hits, start=1):
        if relevant(hit, gold_ranges):
            return 1.0 / i
    return 0.0


def symbol_hit_rate(ranked_hits: list[dict], gold_ranges: list) -> float:
    """Share of gold ranges whose file appears anywhere in the ranking."""
    if not gold_ranges:
        return 1.0
    files = {h["path"] for h in ranked_hits}
    hit = 0
    for g in gold_ranges:
        gp = g["path"] if isinstance(g, dict) else g.path
        if gp in files:
            hit += 1
    return hit / len(gold_ranges)


def file_precision_at_k(ranked_files: list[str], relevant_files: set[str], k: int = 10) -> float:
    """CodeGrep-style file-level precision: fraction of top-k retrieved files
    that are relevant (G3 input definition, D5.3)."""
    top = ranked_files[:k]
    if not top:
        return 0.0
    return sum(1 for f in top if f in relevant_files) / k

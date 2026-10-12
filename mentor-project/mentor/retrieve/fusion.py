"""Reciprocal rank fusion (spec Phase 5, D5.2).

score(d) = SUM_over_rankings 1 / (k + rank(d)), k = 60 per Cormack, Clarke
and Buttcher, SIGIR 2009 (constant fixed in their pilot, unaltered in
validation). Ranks are 1-based positions in each input ranking. Sort by
score descending; ties broken by document ID ascending (deterministic).
"""
from __future__ import annotations

RRF_K = 60


def fuse(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse id-rankings into [(doc_id, score)] sorted best-first."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))

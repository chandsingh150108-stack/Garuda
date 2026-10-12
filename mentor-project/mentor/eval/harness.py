"""Gold harness: run a baseline over the gold set (spec Phase 6).

Reports recall@5/10, MRR, and symbol-hit rate over answerable items, each
with n + Wilson 95% intervals. Unanswerable items are excluded from recall
(they have no ranges) and counted separately for abstention scoring later.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from mentor.eval import baselines as B
from mentor.eval import gold as G
from mentor.eval import metrics as M
from mentor.eval import stats as ST


def run(gold: G.GoldSet, db: Path, sha: str, baseline: str,
        k_recall: tuple[int, ...] = (5, 10)) -> dict:
    items = G.answerable(gold)
    per_item = []
    for item in items:
        hits = B.run(baseline, db, sha, item.question, k=max(k_recall))
        gold_ranges = [{"path": g.path, "start_line": g.start_line,
                        "end_line": g.end_line} for g in item.gold]
        per_item.append({
            "id": item.id,
            **{f"recall@{k}": M.recall_at_k(hits, gold_ranges, k) for k in k_recall},
            "mrr": M.mrr(hits, gold_ranges),
            "symbol_hit": M.symbol_hit_rate(hits, gold_ranges),
        })
    summary = {}
    for key in ([f"recall@{k}" for k in k_recall] + ["mrr", "symbol_hit"]):
        vals = [p[key] for p in per_item]
        mean = statistics.fmean(vals) if vals else 0.0
        # Wilson applies to proportions; report mean with interval of the
        # binarized (==1.0) rate alongside.
        full = sum(1 for v in vals if v >= 1.0)
        summary[key] = {"mean": round(mean, 3), "n": len(vals),
                        "full_rate": round(full / len(vals), 3) if vals else 0.0,
                        "full_rate_ci95": [round(v, 3) for v in
                                           ST.wilson(full / len(vals), len(vals))] if vals else [0.0, 1.0]}
    return {"baseline": baseline, "n": len(items), "items": per_item, "summary": summary}

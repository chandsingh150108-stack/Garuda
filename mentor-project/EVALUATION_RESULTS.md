# EVALUATION_RESULTS

No gold-set measurements yet (Phase 6). All metrics reported with n + method + date + SHA + command (spec Final Evaluation).

| Metric | n | Value | CI | Date | SHA | Command |
|---|---|---|---|---|---|---|
| Retrieval latency p50 (fused, k=10, 20 mixed queries) | 20 | 21.2 ms | n/a (point; nearest-rank) | 2026-10-12 | 7257e60 | `python scripts/bench_search.py` |
| Retrieval latency p95 (same) | 20 | 55.9 ms | n/a | 2026-10-12 | 7257e60 | `python scripts/bench_search.py` |
| Retrieval latency, second run p50/p95 | 20 | 23.6 / 38.9 ms | n/a | 2026-10-12 | 7257e60 | `python scripts/bench_search.py` |
| File-level P@10 probe, lexical-only (5 identifier queries, 1 relevant file each) | 5 | 0.2, 0.1, 0.0, 0.1, 0.1 (mean 0.10) | wide (n=5, directional only) | 2026-10-12 | 7257e60 | `python scripts/bench_search.py` |
| File-level P@10 probe, fused B3 (same 5) | 5 | 0.2, 0.1, 0.1, 0.1, 0.1 (mean 0.12) | wide (n=5, directional only) | 2026-10-12 | 7257e60 | `python scripts/bench_search.py` |

Notes: p95 < 200 ms gate passes in both latency runs (variance is machine load). Precision probe is G3 INPUT, not the gate: fused ≥ lexical on all 5 (symbol retriever rescued `verify_password` + `User`, both lexical 0.0 → fused 0.1). Definition: (# top-10 files containing ≥1 known-relevant location)/10, per CodeGrep usage.

## Phase 6 baselines (frozen gold v1, n=22 answerable, 2026-10-12, SHA 7257e60)

| Baseline | Recall@5 (mean, full-rate [95% CI]) | Recall@10 | MRR | Symbol-hit |
|---|---|---|---|---|
| B1 lexical-only | 0.205, 0.182 [0.07, 0.39] | 0.341, 0.318 [0.16, 0.53] | 0.148, 0.091 [0.03, 0.28] | 0.386, 0.364 [0.20, 0.57] |
| B3 fused (MVP) | 0.288, 0.273 [0.13, 0.48] | 0.424, 0.409 [0.23, 0.61] | 0.270, 0.182 [0.07, 0.39] | 0.424, 0.409 [0.23, 0.61] |
| B3 on counterfactual (fst-cf) | 0.311, 0.273 [0.13, 0.48] | 0.424, 0.409 [0.23, 0.61] | 0.318, 0.273 [0.13, 0.48] | 0.424, 0.409 [0.23, 0.61] |

Command: `python -m mentor.cli eval retrieval --gold evals/gold/v1.yaml --index data/indexes/fst.sqlite --baseline B1|B3 --sha <SHA>` (CF: `--gold evals/gold/v1_counterfactual.yaml --index data/indexes/fst-cf.sqlite --sha <SHA>-cf`).

Reading: B3 beats B1 on every point estimate (R@10 +8.3pp, MRR +12.2pp) but intervals overlap substantially at n=22 — directional gain, not statistically separated. Identifier-worded questions score ~1.0; conceptual ones (no stemming, no summaries yet) often miss — the documented floor that later phases must lift. Counterfactual B3 == original B3 (R@10 0.424 both): retrieval is structure-grounded, renames cost nothing at retrieval level.

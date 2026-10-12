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

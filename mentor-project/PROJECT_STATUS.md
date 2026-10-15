# PROJECT_STATUS

- Current phase: 9 gate PASSED 2026-10-16 (validator 100% on 12-case suite, injection rejected, τ_score=0.02 locked; test FA 1/2 [0.09,0.91], FAb 4/13 [0.13,0.58]); next: Phase 10
- Completed phases: 0 (probe + control files), 1 (A1-A18 + G1-G4, test_decisions.py 3/3 passed), 2 (pinned repo 7257e60 + sandboxed ingest + counterfactual, 13/13 tests green), 3 (parser + symbol model, 152/152 coverage, 43/43 tests green), 4 (chunker + SQLite index, 208 files/1279 chunks/0 failed, 69/69 tests green), 5 (lexical+symbol+path retrieval with RRF-60 fusion, 5/5 identifier queries top-3, p95 <200ms, 89/89 tests green), 6 (frozen 30-Q gold v1 + B1/B3 baselines + counterfactual set, 101/101 tests green), 7 (G1 REJECTED: licences verified, bge-m3 too slow on CPU, jina unrunnable; lexical-only ships, 107/107 tests green), 8 (gateway + both adapters + egress guard + G2: 4B peak 3.57GB/100% valid/82.9 tok/s beats 7B 4.70GB/100%/51.9 tok/s on VRAM tiebreak, 125/125 tests green + live smoke), 9 (answer layer p9v1: evidence/contract/validator V1-V8/abstain/qa + `ask`/`eval answers` CLI, τ_score=0.02 τ_cov=0.0, dev FA 0/6 FAb 3/9, test FA 1/2 FAb 4/13)
- Blocked: none
- Failed tests: none
- Open questions:
  - Target laptop probe DONE 2026-10-11: RTX 5060 8GB (8151 MiB, max 100W). Phase 8 G2 runs here.
  - Python is 3.14.0, spec wants 3.12: deviation stands (recorded D0.2); venv+pip used, stdlib-only Phase 2 code is version-agnostic.
  - Secondary repo licence: Conduit-FastAPI + Express-Conduit have no licence file (GitHub API null). D2.2 GATED; ask human before use.
  - Disk free 22.8GB < 30GB Phase 0 precondition: sufficient for Phase 2; re-check before Phase 8 model pulls.
- Next action: Phase 10 (question-answering service and audit log).

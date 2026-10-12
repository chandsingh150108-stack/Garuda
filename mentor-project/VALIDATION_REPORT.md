# VALIDATION_REPORT

| Date | Phase/Gate | Command | Result | Notes |
|---|---|---|---|---|
| 2026-10-08 | Phase 0 probe | `python scripts/probe_env.py` | PASS | Dev RTX 4050 6GB (6141 MiB, free 5858), driver 581.57, power.limit N/A / max 75W, Python 3.14.0, Node v24.19.0, Ollama client 0.34.0 no daemon, disk 51.82GB free. NOT target (RTX 5060 8GB pending). |
| 2026-10-08 | Phase 0 | `pytest tests/test_probe.py -q` | PASS 1/1 | Valid JSON, all 14 keys present |
| 2026-10-08 | Phase 1 | `pytest tests/test_decisions.py -q` | PASS 3/3 | 18 A-entries with status/evidence/reason/confidence/fallback; G1-G4 name procedure + results file |
| 2026-10-08 | Phase 1 security | paid-dependency check | PASS | No LOCKED decision requires paid API/DB/VM; cloud (A10) optional default-off with local fallback |
| 2026-10-11 | Phase 2 env (target) | `nvidia-smi` + `pytest tests/ -q` | PASS (deviations recorded) | RTX 5060 8GB (8151 MiB, max 100W, driver 610.74); Python 3.14 vs spec 3.12; disk 22.8GB <30GB precondition; 13/13 tests green |
| 2026-10-11 | Phase 2 ingest | `pytest tests/test_ingest.py -q` | PASS 9/9 | symlink (junction fallback), traversal, canary hash-only, kwarg-no-FP, size, submodule, counterfactual fixture, manifest count, acquire SHA/dirty |
| 2026-10-11 | Phase 2 acquire | `python -m mentor.ingest.acquire --repo data/repos/fst --sha 7257e60...` | PASS | HEAD matches pinned SHA, tree clean |
| 2026-10-11 | Phase 2 manifest | manifest build + scanner self-check | PASS | 252 entries (matches walk), 208 indexed / 41 extension / 2 filename / 1 lockfile / 0 secret; manifest has zero scanner findings, no secret values |
| 2026-10-11 | Phase 2 counterfactual | integrity check (ident `\b`, route `(?!-cf)` guard) | PASS | 20 identifiers + 5 routes (signup prioritized) + 3 config; zero genuine old-name leftovers; 984 new-name occurrences |
| 2026-10-11 | Phase 3 goldens | `pytest tests/test_parse_python.py tests/test_parse_ts.py tests/test_parse_config.py -q` | PASS 30/30 | 10 frozen goldens exact; review caught+fixed 3 extractor bugs (docstring inversion, TS body traversal, nested-const noise) |
| 2026-10-11 | Phase 3 invariant | `check_ranges` over 10 goldens + all fst parsed files | PASS 0 violations | 1<=start<=end<=lines, signature==start, name-on-signature-line |
| 2026-10-11 | Phase 3 worker | timeout mechanism + pathological nesting + isolation | PASS | `run_isolated` sleep→timeout; 3000-deep brackets completes inside 10s; symlink/size/path guards |
| 2026-10-11 | Phase 3 secret exclusion | golden values + fst config blob scan | PASS | `supersecret-value`/`${SECRET_KEY`/`abc123` absent; scanner finds nothing in config output |
| 2026-10-12 | Phase 3 runtime crash saga | 0.26.0 native deaths (Event 1000, 0xC0000005) | RECORDED, resolved by downgrade | test_users.py whole-file ~12/12 deaths, parts fine; identical fragment 3 pass/2 crash (flaky); 0.25.2: 4/4 clean both killers |
| 2026-10-12 | Phase 3 coverage | `python -m mentor.parse.cli --repo data/repos/fst --sha 7257e60` | PASS 152/152 (100.0%) | 0 failed; 23 routes (incl. POST /users/signup users.py:146 register_user); 2 models (User, Item); 675 import + 943 call edges. Earlier 0.26.0 runs: 98.68/99.34/98.03/98.68 (flaky) |
| 2026-10-12 | Phase 3 suite | `pytest tests/ -q` | PASS 43/43 | 13 Phase-2 + 30 Phase-3 green |

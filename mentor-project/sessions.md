# SESSIONS

## 2026-10-08 — Phases 0 + 1 (this machine: RTX 4050 dev, NOT the RTX 5060 target)

### What was asked
- "read the whole repository" → read `CODEBASE_MENTOR_EXECUTABLE.md` (2640 lines), `Codebase Mentor Reassessment Report.md` (479 lines); `.dist/` empty, no code existed.
- "go ahead" (x2) → executed Phase 0, then Phase 1, in `mentor-project/` subfolder (user chose subfolder to keep specs clean).

### Phase 0 — Workspace, environment, hardware probe → GATE PASSED (`03b6d33`)
- Created PROJECT_ROOT `mentor-project/` with `scripts/ docs/ tests/ data/`.
- Wrote `scripts/probe_env.py` (JSON probe, null on missing tools) + `tests/test_probe.py` (14 required keys).
- Created 9 control files: PROJECT_STATUS, RESEARCH_LOG (V1–V22 ledger), DECISIONS (D0.1/D0.2), VALIDATION_REPORT, SECURITY_THREAT_MODEL (skeleton), EVALUATION_RESULTS (empty), DEMO_RUNBOOK (skeleton), README, docs/ARCHITECTURE.md (skeleton) + `.gitignore`.
- Probe result (dev machine): Windows 10.0.26200, Python 3.14.0 (spec wants 3.12 — deviation recorded), Node v24.19.0, Git 2.56, RTX 4050 Laptop 6GB (6141 MiB, free 5858), driver 581.57, power.limit N/A / max 75W, Ollama client 0.34.0 no daemon, disk 51.8GB free. Saved to `docs/hardware_probe.json`.
- `test_probe.py` 1/1 passed. `git init` + commit `phase-00: probe and control files`.
- Open: target RTX 5060 8GB probe still pending (user said target is a different machine); Phase 8 G2 must run there.

### Phase 1 — Architecture decisions locked → GATE PASSED (`a0a6b53`)
- Wrote DECISIONS.md A1–A18 (status/evidence/alternatives/reason/confidence/fallback) + G1–G4 gate index (procedure + results file). No LOCKED decision needs paid services (A10 cloud optional default-off).
- Populated `docs/ARCHITECTURE.md` to match decisions; created `evals/{gold,tours,study}/README.md` placeholders.
- Wrote `tests/test_decisions.py` (18 entries present, fields check, GATED→procedure check) — 3/3 passed; full suite 4/4 with probe test.
- Updated PROJECT_STATUS (next: Phase 2), VALIDATION_REPORT, commit `phase-01: decisions locked`.

### Next
- Phase 2: clone + pin `full-stack-fastapi-template` SHA, sandboxed ingest (filters/secrets/manifest), counterfactual copy. Needs one network clone; then offline.

## 2026-10-11 — Phase 2 (target machine: RTX 5060 8GB, Python 3.14.0)

### What was asked
- "how many phases ... are implemented" → answered 2/23 (Phases 0+1).
- "start implementing the next phases" (plan mode) → planned Phase 2 only, on target laptop; answers: clone now, Phase 2 only, target laptop.
- "go ahead" (build mode) → executed Phase 2.

### Phase 2 — Repository acquisition, pinning, sandboxed ingestion → GATE PASSED
- Env: target confirmed via `nvidia-smi` (8151 MiB, max 100W, driver 610.74); `pytest` installed (9.1.1, MIT); full suite 13/13 green. Deviations: Python 3.14 vs 3.12, disk 22.8GB <30GB, ollama/node absent from PATH (not needed).
- Research: pinned `7257e60` (master HEAD 2026-10-08); MIT licence read locally; 152 Py/TS/JS files; signup `POST {API_V1_STR}/users/signup` at `users.py:146-147`; 5 candidates scored (secondary GATED on licence question).
- Implemented: `mentor/{config,ingest/{acquire,filters,secrets,manifest}}`, `scripts/make_counterfactual.py`, `tests/test_ingest.py` (9 tests) + `tests/fixtures/` (canary FAKE key + README; rest runtime-generated).
- Hardening found by measurement: (1) Windows junctions treated as symlink-equivalent (os.walk would descend otherwise); (2) secret scanner narrowed to quoted literals after unquoted matching FP-excluded 14 source files incl. signup handler; (3) counterfactual route rename extended to path substrings + signup prioritized.
- Manifest: 252 entries = filesystem walk; 208 indexed; zero scanner findings. Counterfactual `fst-cf`: 20/5/3 renames, integrity clean, map at `evals/counterfactual_map.json`.
- Docs: D2.1–D2.4 in DECISIONS.md; rubric + tuning in RESEARCH_LOG.md; gates in VALIDATION_REPORT.md; commit `phase-02: pinned repo and sandboxed ingest`.

### Next
- Phase 3: parser + symbol model (tree-sitter Py/TS, routes/models, 10s worker timeout, golden tests).

## 2026-10-11/12 — Phase 3 (parser + symbol model) → GATE PASSED
- Research: tree-sitter 0.26.0/MIT + grammars MIT probed live (API, node shapes for imports/decorators/class-kwargs/TS-calls); repo patterns code-read (decorator routes, SQLModel table=True inferred tables, compose.yml actual layout differing from spec names).
- Implemented: `mentor/parse/{treesitter,py_extract,ts_extract,config_extract,edges,parse_worker,cli}.py`, `requirements.txt` (pins), `mentor/config.py` parser limits, 10 golden fixtures + expected outputs, 30 tests.
- Golden review caught 3 real bugs before freezing: inverted `_docstring` condition, TS function bodies never descended (empty client_calls), nested consts recorded as symbols.
- Native-crash saga: 0.26.0 segfaulted (0xC0000005, Event 1000) — test_users.py whole-file ~12/12 deaths while parts parsed; identical fragment 3 pass/2 crash (proven flaky, not logic). Contained every time by the worker (D3.2 vindicated). Resolved: runtime downgrade to 0.25.2 (4/4 clean, full CLI 152/152). Recorded as D3.1 amendment + D3.2 retry clarification (one fresh-process retry, persistent failures stay parse_failed).
- Coverage: 152/152 (100.0%), 0 failed; 23 routes (POST /users/signup users.py:146 register_user verified); 2 models (User, Item); 675 import + 943 call edges; invariant 0 violations; secret exclusion clean.
- Suite 43/43 green. Commit `phase-03: parser and symbol model`.

### Next
- Phase 4: chunking + SQLite index store (cAST split-then-merge, FTS5, identifiers, hashing, CLI).

## 2026-10-12 — Phase 4 (chunking + SQLite index) → GATE PASSED
- Research: FTS5 docs + live probe (UNINDEXED, unicode61, bm25, SQLite 3.50.4); chars//4 tokens; identifier splitting rules.
- Implemented: `mentor/index/{identifiers,hashing,chunker,store,schema.sql}`, `mentor/cli.py` (`index` command). Isolated AST plans per file (D3.2 containment reused); line windows (80/20, budget-bounded) for non-code; exact-text citations vs header embed separation; deterministic chunk IDs.
- Bugs found by measurement (own logic, fixed + regression-tested): (1) duplicate chunk_ids — 130 same-line AST children re-emitted one line 130x (single-line atomicity + dedupe fix); (2) fixed 80-line windows exceeded budget on long lines (64 violations → budget-bounded windows fix).
- Index: 208 files, 1279 chunks (261 ast/1018 lines), 609 symbols, 1618 edges, 23 routes, 2 models, 8 config_facts, failed=[]; max non-exception 512 tokens; 4 recorded single-line exceptions; second build byte-identical (dump-equal).
- Suite 69/69 green. Commit `phase-04: chunker and sqlite index`.

### Next
- Phase 5: lexical/symbol/path retrieval + RRF fusion + confidence signals (D5.1–D5.3).

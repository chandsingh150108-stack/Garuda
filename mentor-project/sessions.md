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

## 2026-10-12 — Phase 5 (lexical/symbol/path retrieval + RRF fusion) → GATE PASSED
- Research: RRF k=60 confirmed in primary paper (live PDF); CodeGrep abstract verified live (threshold 0.375/0.445/0.677); PowerShell backtick-mangling lesson (tests call API directly).
- Implemented: `mentor/retrieve/{analyze,lexical,symbols,paths,fusion,confidence,search}.py`, `search` CLI command, `scripts/bench_search.py`. Parameterized-only SQL (incl. LIKE ESCAPE + quoted FTS terms); read-only index open; deterministic RRF with chunk_id tiebreak.
- Gates: 5/5 identifier definitions top-3 fused (`register_user`, `create_user`, `verify_password`, `User`, `get_password_hash`); determinism; injection read-only; p50 ~21ms / p95 ~56ms (<200ms, two runs); G3 input recorded (fused ≥ lexical, 2 symbol rescues, n=5 directional).
- Suite 89/89 green. Commit `phase-05: lexical and fused retrieval`.

### Next
- Phase 6: frozen 30-Q gold set + harness (B1/B3 baselines, counterfactual set, Wilson stats).

## 2026-10-12 — Phase 6 (frozen gold set + harness) → GATE PASSED
- Authored 30-Q v1 (8/6/6/4/6) from verbatim code reads + git history (constant-time auth, open registration) + repo-wide absence greps; SHA-256 frozen in DECISIONS.md (D6.1–D6.3).
- Implemented `mentor/eval/{gold,metrics,stats,harness,baselines,counterfactual}.py` + `eval retrieval` CLI; built fst-cf manifest/parses/index pipeline for the contamination control.
- Baselines: B1 R@10 0.341 / B3 0.424 / CF-B3 0.424 (n=22, intervals overlap — directional gain only; identical CF retrieval proves structure grounding). Identifier questions ~1.0, conceptual ones often miss (no stemming/summaries — documented floor).
- Suite 101/101 green. Commit `phase-06: frozen gold set and retrieval baselines`.

### Next
- Phase 7: embedding decision gate G1 (licence checks + recall@10 benchmark; adopt or ship lexical-only).

## 2026-10-12 — Phase 7 (embedding gate G1) -> GATE PASSED with REJECT outcome
- Licences verified on cards: bge-m3 MIT, jina-v2-base-code Apache-2.0 (trust_remote_code), jina-code-0.5b non-commercial (skipped).
- Implemented `mentor/retrieve/dense.py` (CPU, normalized fp32, brute-force cosine, metadata guards) + `scripts/bench_embedders.py` (sharded, resume-safe caches, B1/B3-equivalent harness).
- Measured: bge-m3 loads (low-mem flags; plain load OOM at 3.9GB free) but encodes ~3.75 s/chunk -> ~80 min projected, FAILS <30 min rule; jina load BLOCKED by custom-code vs transformers-5 incompatibility.
- G1 REJECTED per rule (gain AND time AND licence); `DENSE_MODEL = "none"` ships; eval tooling pinned separately (requirements-eval.txt, not shipped).
- Suite 107/107 green. Commit `phase-07: embedding gate G1 decided`.

### Next
- Phase 8: local LLM gateway + laptop hardware benchmark G2 (Qwen2.5-Coder-7B Q4 via Ollama, VRAM/throughput/schema-validity).

## 2026-10-15 — Phase 8 (gateway + G2) → GATE PASSED (G2 DECIDED: Qwen3-4B)
- Pre-existing scaffolding (uncommitted): `mentor/llm/{gateway,ollama_adapter,llamacpp_adapter,egress}.py`, `scripts/{bench_llm,fetch_llm}.py`, `tests/{socket_guard,test_gateway,test_ollama_adapter,test_egress}.py`, D8.0–D8.4. Verified, kept, completed.
- Added missing spec item: `test_live_smoke_opt_in` (skips unless MENTOR_LIVE=1) — passes against loopback llama-server.
- Harness bugs found by measurement (own logic, fixed): (1) llamacpp path never sent the schema — `response_format: json_object` constrains to valid JSON only, model invented its own keys → first 7B run 0/22 validity; fixed per D8.4 with schema-in-prompt, re-ran 22/22. (2) max-tokens 256 truncated JSON mid-object → 1024.
- G2 (llamacpp-vulkan, b11429, `-ngl 99 -c 8192 -np 1`): 7B peak 4814 MiB / 22-22 valid / 51.9 tok/s; 4B peak 3658 MiB / 22-22 valid (/no_think required — without it thinking exhausts budget → empty) / 82.9 tok/s. Both pass all three; validity tied → tiebreak lower VRAM → 4B wins (Rule 5). 7B stays qualified fallback; code-answer-quality revisit assigned to Phase 9 with evidence.
- Raw: `docs/bench_7b.json`, `docs/bench_4b.json`. Suite 125/125 green. Commit `phase-08: local llm gateway and gate G2`.

### Next
- Phase 9: evidence assembly, answer contract, validator, abstention calibration (thresholds τ gated on gold).

## 2026-10-16 — Phase 9 (grounded answers, validator, abstention) → GATE PASSED
- Research from sources: ICTIR 2025 correctness≠faithfulness (57% post-rationalized, Command-R+); OWASP LLM01 delimiting reduces≠eliminates (schema validated in trusted code is the enforcement); NLI≠factual support (FactRel 84%, RefNLI) → honest limit finalized in docs/ARCHITECTURE.md.
- Implemented `mentor/answer/{evidence,contract,prompts,validator,abstain,qa}.py` + `mentor ask` + `mentor eval answers --split` CLI + `scripts/calibrate_tau.py`; pydantic==2.13.5 pinned (MIT).
- Prompt bug found by measurement (own logic): full JSON schema in system prompt → 4B echoes schema (V6 fail); compact shape + example → validated answers.
- τ calibration (seed 7, one live pass + offline grid): TAU_SCORE=0.02, TAU_COV=0.0 (coverage adds nothing); dev FA 0/6, FAb 3/9; locked-τ held-out test FA 1/2 [0.09,0.91], FAb 4/13 [0.13,0.58] — matches simulation exactly.
- Residual: q25 billing confabulation cites 10 unrelated blocks yet passes V1–V8 — recorded as the honest limit in action, not a validator bug.
- Suite 139/139 green (125 prior + 14 new). Commit `phase-09: grounded answers, validator, abstention`.

### Next
- Phase 10: question-answering service and audit log (FastAPI loopback, provider label, hash-only audit).

## 2026-10-16 — Phase 10 (QA service + audit) → GATE PASSED
- Implemented `mentor/api/{schemas,routes,app}.py` (repos/index/ask/code/status, typed), `mentor/answer/{cache,audit}.py`, `mentor serve` CLI (loopback-only, --unsafe-bind refusal).
- schema.sql v1→v2 (additive audit+cache); `ensure_service_tables()` upgrades existing indexes without content rebuild (D10.4).
- Test fixes from measurement: abstain responses now carry closest refs (qa.py; audit evidence matched); range-cap test uses a >400-line file.
- Live smoke via loopback :8000: 5/5 clean (2 answers, 2 pre-gate abstains with closest, 1 known billing residual). Suite 149/149 green. Commit `phase-10: qa service and audit`.

### Next
- Phase 11: optional free-cloud adapters with egress gating (Groq/Gemini behind allow_free_cloud + allowlist + redaction + budget, default OFF).

## 2026-10-16 — Phase 11 (free-cloud gating) → GATE PASSED
- Research dated: Groq free 30 RPM/1K RPD/8K TPM/200K TPD per model (live docs; V4 model name now on official page, still not hardcoded); Gemini unpaid-services trains products (terms eff. 2026-03-23) → Gemini never private; Gemini limits fail-closed (no keys here).
- Implemented `mentor/llm/{groq_adapter,gemini_adapter,redact,budget}.py`, gateway 429 kind + D11.1 gate + generate_auto, qa groq→gemini→local chain with provider/fallback labels, per-repo allowlisted_public, cloud-aware cache key.
- Test repairs from measurement: 429 is not retried (correct); cloud tests pin retrieval τ to isolate gating; fallthrough serving label unified to configured provider.
- Suite 166/166 (165 + 1 skip) with no keys. Commit `phase-11: optional free cloud with gating`.

### Next
- Phase 12: architecture extraction and deterministic diagrams (component graph from imports/routes, Mermaid by construction).

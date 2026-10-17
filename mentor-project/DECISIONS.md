# DECISIONS

## D0.1 Operating system path
- Status: LOCKED
- Decision: Native Windows primary (this dev machine Win + native CUDA Ollama). WSL2 fallback only if vLLM needed (not in scope).
- Alternatives: Linux primary, WSL2 primary.
- Evidence: Ollama uses native CUDA on Windows; vLLM WSL2-only not needed (spec Phase 0 research Q1). Dev probe confirms Windows + nvidia-smi works.
- Reason: Fewest moving parts for laptop demo.
- Confidence: High
- Fallback: Document WSL2 steps if native GPU fails.
- Date: 2026-10-08

## D0.2 Python environment
- Status: LOCKED
- Decision: venv + pip, no hosted env tools. Spec wants 3.12; dev machine has 3.14.0 — target laptop must use 3.12 venv; deviation recorded until confirmed.
- Alternatives: conda/uv/hosted.
- Evidence: Spec Global Rule zero-cost; python --version on dev.
- Reason: Free, reproducible, matches spec toolchain.
- Confidence: High
- Fallback: If 3.12 unavailable on target, record deviation and pin deps to tested versions.
- Date: 2026-10-08

## PROJECT_ROOT location (user-directed)
- Status: LOCKED
- Decision: PROJECT_ROOT = `mentor-project/` subfolder under Code Apex; parent specs stay reference-only.
- Alternatives: repo root = Code Apex itself.
- Evidence: User answer 2026-10-08 (subfolder to keep specs clean).
- Reason: Avoid polluting research docs with build artifacts.
- Confidence: High
- Fallback: None.
- Date: 2026-10-08

## A1 Product framing
- Status: LOCKED
- Decision: Verifiable repository onboarding, not generic RAG. Facts from deterministic index; language from model; trust from validator.
- Alternatives: Generic chunk+RAG chat; long-context stuff-whole-repo.
- Evidence: Spec ledger V10-V12; ICTIR 2025 correctness-vs-faithfulness finding (to verify Phase 9); CodeGrep precision-threshold observation (directional).
- Reason: Citations must be checkable; prompts alone cannot guarantee grounding.
- Confidence: High
- Fallback: None (framing is fixed).
- Date: 2026-10-08

## A2 Parser
- Status: LOCKED
- Decision: tree-sitter primary (tree-sitter-python, tree-sitter-typescript, both MIT to confirm on pin in Phase 3) + regex/YAML/TOML/JSON config parsers (PyYAML MIT, tomllib stdlib). LSP/CodeQL Future enrichers only.
- Alternatives: LSP-only; SCIP/LSIF; CodeQL/Joern.
- Evidence: cAST paper (EMNLP 2025 Findings, verified V12); tree-sitter error-tolerant + exact lines [OFFICIAL docs to confirm Phase 3]; licences: py-tree-sitter MIT, grammars MIT (confirm per-grammar Phase 3), PyYAML MIT.
- Reason: Uniform multi-lang, exact ranges, works without buildable project.
- Confidence: High
- Fallback: Regex extraction for missing grammar, labelled lower confidence.
- Date: 2026-10-08

## A3 Chunking
- Status: LOCKED
- Decision: AST-based split-then-merge (cAST): max ~512 approx tokens, recursive split oversized nodes at child boundaries, merge small siblings; store `text` (original, cited) apart from `embed_text` (header+text).
- Alternatives: Fixed token windows; line windows (80 + overlap, degraded fallback).
- Evidence: cAST +4.3 Recall@5 RepoEval / +2.67 Pass@1 SWE-bench [PRIMARY RESEARCH V12].
- Reason: Chunks align to syntax so cites point at real units.
- Confidence: High (principle); Medium (gain transfer — measured Phase 5).
- Fallback: Line windows of 80 lines with overlap, recorded as degraded mode.
- Date: 2026-10-08

## A4 Storage
- Status: LOCKED
- Decision: One SQLite file per repository with FTS5 (public domain). No server daemon. Schema versioned in schema.sql.
- Alternatives: PostgreSQL+tsvector; pgvector; Qdrant; LanceDB; Chroma; OpenSearch (all rejected for MVP).
- Evidence: Spec correction C1; report storage benchmarks UNVERIFIED third-party (V21) so not relied on; single-user single-repo needs no tenant filtering or daemon; SQLite native Windows [OFFICIAL]. Licence: SQLite public domain.
- Reason: Zero services, BM25 via FTS5, native Windows.
- Confidence: Medium-high
- Fallback: PostgreSQL + tsvector/pgvector only if Phase 7/22 latency gates fail at test repo size.
- Date: 2026-10-08

## A5 Lexical retrieval + fusion
- Status: LOCKED
- Decision: FTS5 BM25 over identifier-split text + symbol and path boosts, fused with RRF constant 60, ties broken by chunk_id.
- Alternatives: Dense-only (rejected); learned sparse retrieval.
- Evidence: RRF paper Cormack/Clarke/Buttcher SIGIR 2009 [PRIMARY RESEARCH to confirm Phase 5]; CoREB keyword-collapse directional (V10); identifier-splitting practice.
- Reason: Identifiers/literals/routes need lexical; deterministic, explainable, fast.
- Confidence: High
- Fallback: None needed; lexical is the floor.
- Date: 2026-10-08

## A6 Dense retrieval
- Status: GATED (gate G1, Phase 7)
- Decision: Off by default until measured. Candidates: none (lexical-only B3), bge-m3 (MIT), jina-embeddings-v2-base-code (licence to confirm on card).
- Alternatives: jina-code-embeddings 0.5B/1.5B (non-commercial per converter card V15 — measurement-only, never shipped); Voyage/cloud (excluded by budget).
- Evidence: V13-V15; CoREB code-specialization directional (V10 caveat: CP snippets, not repo QA).
- Reason: Adopt only on measured gain with permissive licence.
- Confidence: Low (until G1 runs)
- Fallback: Lexical-only, the shipped default if G1 not met.
- Benchmark procedure: Run scripts/bench_embedders.py on frozen gold v1 (Phase 7); criterion G1; results recorded in EVALUATION_RESULTS.md.
- Date: 2026-10-08

## A7 Reranker
- Status: LOCKED (none in MVP)
- Decision: No reranker in MVP. Reconsidered only through gate G4 (Phase 22).
- Alternatives: Qwen3-Reranker-0.6B; CoREB-tuned reranker; Jina reranker.
- Evidence: CoREB off-shelf rerankers task-asymmetric, not net-positive (V10, with transfer caveat); +1-2GB VRAM +300ms cost.
- Reason: No positive evidence for repo QA; VRAM better spent on 7B.
- Confidence: Medium
- Fallback: None in MVP.
- Date: 2026-10-08

## A8 Local LLM
- Status: LOCKED default, GATED alternative (gate G2, Phase 8)
- Decision: Default candidate Qwen2.5-Coder-7B Q4_K_M via Ollama (Apache-2.0, 128K ctx, 28 layers / 4 KV heads per V16). Alternative: small dense model ≤5.5GB Q4 (licence checked Phase 8).
- Alternatives: 14B Q4 (~8.4-9GB, no fit V17); gpt-oss-20b (16GB min, no fit); 30B+ MoE (server only).
- Evidence: V16-V17; Ollama docs [OFFICIAL]; KV arithmetic Phase 8 (0.47GB @8K, [INFERENCE]); licences: Ollama MIT, Qwen2.5-Coder-7B Apache-2.0.
- Reason: Largest permissive coder fitting ~7GB usable of 8GB.
- Confidence: Medium (calculated; measured in Phase 8)
- Fallback: Smaller model at 4096 ctx, then CPU-only; record perf impact.
- Benchmark procedure: Run scripts/bench_llm.py for both candidates (Phase 8); criterion G2; results in EVALUATION_RESULTS.md.
- Date: 2026-10-08

## A9 Agentic retrieval
- Status: GATED (gate G3, Phase 22)
- Decision: Stage 3 only. Enabled only if measured file-level precision on our gold set exceeds the level where the agent's own eval shows benefit; max 3 read-only tools on 7B, ≤4 turns.
- Alternatives: Pure RAG forever; free-form shell agent (rejected: hard rule, model never gets shell).
- Evidence: CodeGrep 14B searcher does not fit laptop (V11); Morph/Cognition parallel-search pattern [OBSERVED PRACTICE, unverified V22]; our precision measured Phase 5.
- Reason: Follows call chains RAG cannot, but bad retrieval hurts (CodeGrep threshold observation).
- Confidence: Medium
- Fallback: Hybrid RAG remains the product.
- Benchmark procedure: Measure file-level precision top-10 on gold v1 (Phase 5/22); criterion G3; results in EVALUATION_RESULTS.md.
- Date: 2026-10-08

## A10 Free cloud
- Status: LOCKED
- Decision: Optional, public-repo-only, default OFF (allow_free_cloud=false). Groq primary, Gemini fallback, provider list read live. Never for private code.
- Alternatives: Paid APIs (excluded by budget); no cloud at all (fallback if gating fragile).
- Evidence: V3-V7 (quotas re-verify demo week; V4/V5 unverified numbers removed); Gemini training-use verified V6; licences/terms: provider ToS per console.
- Reason: $0 quality boost for public demo without required dependency.
- Confidence: High (policy); Medium (quotas change)
- Fallback: Local-only with no other change (allow_free_cloud=false).
- Date: 2026-10-08

## A11 Evidence contract
- Status: LOCKED
- Decision: Model outputs evidence IDs only; server expands ranges from index; blocks E1..En server-numbered in rank order, line-numbered, ~3000 tok cap.
- Alternatives: Model-written paths/lines (rejected: post-rationalization risk).
- Evidence: Citation-faithfulness literature to confirm Phase 9 (ICTIR 2025 57% claim); Ollama format schema not guaranteed V18.
- Reason: Validity true by construction; support measured separately.
- Confidence: High
- Fallback: Abstention when expansion fails.
- Date: 2026-10-08

## A12 Abstention
- Status: LOCKED (thresholds GATED on Phase 9)
- Decision: Three layers: pre-generation confidence gate (tau_score, tau_cov) + in-generation insufficient_evidence + post-generation validation fail -> abstain.
- Alternatives: Model self-confidence only (unreliable); no abstention (unsafe).
- Evidence: Spec calibration plan; AwF precision/recall framing (report, verify Phase 9).
- Reason: Independent layers catch different failures.
- Confidence: Medium (thresholds calibrated on small set)
- Fallback: Stricter gate (higher threshold), more false abstentions, reported.
- Benchmark procedure: Calibrate tau on dev split (seed recorded), evaluate held-out false-answer/false-abstain with Wilson intervals (Phase 9); results in EVALUATION_RESULTS.md.
- Date: 2026-10-08

## A13 Diagrams
- Status: LOCKED
- Decision: Mermaid generated deterministically from component graph; node IDs generated; labels escaped; LLM only proposes short titles containing an evidence term (validator rejects otherwise).
- Alternatives: LLM-written Mermaid (rejected: bracket errors + invented structure); D2/Cytoscape.
- Evidence: Report bracket-error observation; Mermaid text-diffable [OFFICIAL docs Phase 12]; licences: Mermaid MIT, React/Vite/Monaco MIT.
- Reason: Facts not invented; syntax by construction.
- Confidence: High
- Fallback: Plain component list.
- Date: 2026-10-08

## A14 Freshness
- Status: LOCKED
- Decision: git diff --name-status + content hashes; artifacts carry dependency sets; lazy regen; citation hash check at open; reindex command + optional post-commit hook (no webhook server v1).
- Alternatives: Timestamps (wrong); webhooks (need server); full rebuild (fallback).
- Evidence: Git docs [OFFICIAL Phase 17]; report freshness design.
- Reason: Updates only what changed; staleness visible via badge.
- Confidence: High
- Fallback: Full reindex from pinned SHA.
- Date: 2026-10-08

## A15 Frontend
- Status: LOCKED
- Decision: React + TypeScript + Vite + read-only Monaco + Mermaid + plain CSS (no Tailwind) + plain-text answer rendering (no Markdown/HTML) + CSP same-origin.
- Alternatives: Next.js; CodeMirror; Markdown rendering (rejected: XSS surface).
- Evidence: Monaco/Mermaid/MDN CSP docs [OFFICIAL Phase 16]; licences all MIT; Playwright Apache-2.0.
- Reason: Line ranges without server rendering or injection class.
- Confidence: Medium-high
- Fallback: Plain line-numbered code view if Monaco heavy.
- Date: 2026-10-08

## A16 Backend
- Status: LOCKED
- Decision: Python 3.12 + FastAPI + Pydantic, loopback 127.0.0.1 only (refuse other bind without --unsafe-bind), CORS single local origin, request size limit.
- Alternatives: Flask; Node.
- Evidence: FastAPI/Pydantic docs [OFFICIAL Phase 10]; licences: Python PSF, FastAPI/Pydantic MIT.
- Reason: Parsing/ML ecosystem + typed schemas reused for LLM-schema validation + OpenAPI.
- Confidence: High
- Fallback: None.
- Date: 2026-10-08

## A17 Serving
- Status: LOCKED
- Decision: Ollama on laptop (loopback 127.0.0.1:11434, temp 0, 1 model / 1 parallel). vLLM/SGLang Future server-tier only.
- Alternatives: llama.cpp server (fallback, same API shape); vLLM/SGLang now (rejected: 90% VRAM pre-alloc, WSL2-only Win, 24GB+ need).
- Evidence: Ollama docs [OFFICIAL Phase 8]; licences: Ollama/llama.cpp MIT, vLLM/SGLang Apache-2.0.
- Reason: Single-user laptop gains nothing from batching servers.
- Confidence: High
- Fallback: llama.cpp server.
- Date: 2026-10-08

## A18 Demo repository
- Status: LOCKED primary, GATED secondary
- Decision: Primary fastapi/full-stack-fastapi-template (MIT, ~43.5K stars Jun 2026, V19) + counterfactual copy; secondary stress repo chosen by Phase 2 rubric (licence permissive, <200 Py/TS files, request flow, tests, fork-copy risk scored).
- Alternatives: Conduit FastAPI; Mealie (AGPL caution); PetClinic (overexposed); Gitea/Mattermost/Superset (too big).
- Evidence: V19; licences verified on repos themselves Phase 2.
- Reason: Matches Py+React stack, fastest indexing; contamination controlled by counterfactual + B6 baseline.
- Confidence: Medium
- Fallback: Conduit-Express/Spring if primary unsuitable; record SUPERSEDED.
- Benchmark procedure: Phase 2 five-candidate rubric scoring; decision D2.2; recorded in RESEARCH_LOG.md.
- Date: 2026-10-08

## Gates G1-G4 (procedures later phases cite)
- Status: GATED index
- Decision: G1 embedding (Phase 7): run bench_embedders.py --candidates none,bge-m3,jina-v2-code --device cpu on gold v1; adopt dense only if fused Recall@10 exceeds B3 by >=5pp (interval reported) AND full CPU embed <30min AND licence permits; else lexical-only ships (success). Results in EVALUATION_RESULTS.md; default in mentor/config.py must match.
- Alternatives: Adopt on leaderboard (rejected).
- Evidence: V13-V15; CoREB directional V10.
- Reason: Leaderboards do not transfer; lexical already works.
- Confidence: Medium
- Fallback: Lexical-only.
- Benchmark procedure: scripts/bench_embedders.py (Phase 7); criterion above; results in EVALUATION_RESULTS.md.
- Date: 2026-10-08
- Status: GATED index
- Decision: G2 local model (Phase 8): run bench_llm.py --model each --ctx 8192 --sustained-minutes 10; choose model meeting (a) peak VRAM <=7.0GB at 8K, (b) schema validity >=90% no-repair on 30 gold prompts (interval), (c) sustained throughput usable; prefer higher validity, tie lower VRAM; else retry 4096. Record nvidia-smi + ollama ps + TTFT + tok/s + temp/power.
- Alternatives: Estimate VRAM (rejected); single-model claim (rejected).
- Evidence: V16-V18; hardware_probe.json.
- Reason: 8GB shared with OS/display; measurement replaces arithmetic.
- Confidence: Medium
- Fallback: Smaller model 4096, then CPU-only; document slower demo.
- Benchmark procedure: scripts/bench_llm.py (Phase 8); criterion above; results in EVALUATION_RESULTS.md.
- Date: 2026-10-08
- Status: GATED index
- Decision: G3 agentic retrieval (Phase 22, input Phase 5): measure file-level precision@10 of lexical/symbol/path on gold v1 (CodeGrep definition); enable 3-tool 7B agent only if precision exceeds level where agent eval shows benefit with intervals excluding zero; else record precision + reason, stay RAG.
- Alternatives: Assume 0.45-0.68 band as constant (rejected per V11: 3-point observation, 14B searcher no-fit).
- Evidence: V11.
- Reason: Empirical gate, not assumed constant.
- Confidence: Medium
- Fallback: Hybrid RAG.
- Benchmark procedure: harness.py precision run + agent eval sample (Phase 22); results in EVALUATION_RESULTS.md.
- Date: 2026-10-08
- Status: GATED index
- Decision: G4 reranker (Phase 22 only): run gold with/without smallest fitting reranker on laptop; adopt only if held-out Recall@10 AND answer correctness improve with intervals excluding zero AND latency within demo limit; else record not-adopted + numbers.
- Alternatives: Ship off-shelf reranker by default (rejected).
- Evidence: V10 (transfer caveat both directions).
- Reason: Only own-gold gain justifies cost.
- Confidence: Medium
- Fallback: No reranker.
- Benchmark procedure: reranker A/B script (Phase 22); results in EVALUATION_RESULTS.md.
- Date: 2026-10-08

## D2.1 Primary repository SHA
- Status: LOCKED
- Decision: `fastapi/full-stack-fastapi-template` at `7257e606cb94eada1dca40173e2b7f99dd549bc6` (master HEAD, committed 2026-10-08, "Update release notes"). Verified via `git rev-parse HEAD`, working tree clean.
- Alternatives: A later commit (rejected: citations must pin to a fixed commit; HEAD-at-phase-time is the rule).
- Evidence: Local clone `data/repos/fst`; `LICENSE` = MIT (verified on repo itself); 152 Py/TS/JS files (43 .py, 109 .ts/.tsx), 252 files total; signup flow at `backend/app/api/routes/users.py:146-147` (`POST {API_V1_STR}/users/signup` -> `register_user`, router prefix `/users`, no extra api_router prefix); `tests/` present.
- Reason: Matches Py+React stack per A18; HEAD-at-phase-time with recorded SHA is checkable.
- Confidence: High
- Fallback: None (SHA immutable; SUPERSEDED + repin only before any evaluation if wrong).
- Date: 2026-10-11

## D2.2 Secondary repository
- Status: GATED (rubric scored; choice deferred)
- Decision: No secondary locked yet. Rubric (licence permissive / <200 Py-TS files / documented request flow / tests / fork-copy risk), scored 2026-10-11 via repo pages + GitHub API (licences) + local inspection (primary only):
  - full-stack-fastapi-template: MIT / 152 files PASS / auth+CRUD flows PASS / tests PASS / template-copy risk HIGH. Primary per A18.
  - borys25ol/fastapi-realworld-backend: licence NULL on GitHub API (no licence file) FAIL / small Py backend / RealWorld auth+articles spec PASS / tests/ PASS / low copy risk. Best technical fit, BLOCKED on licence.
  - mealie-recipes/mealie: AGPL-3.0 FAIL (demo OK, redistribution caution) / large (5603 commits) FAIL / domain flows PASS / tests PASS.
  - spring-projects/spring-petclinic: Apache-2.0 PASS / Java-only FAIL (Py+TS scope) / tiny demo app / tests PASS / overexposed.
  - gothinkster/node-express-realworld-example-app: licence NULL FAIL / TS, spec-standardized / tests vary.
- Alternatives: Lock Conduit-FastAPI now (rejected: licence unclear is a stop condition); lock PetClinic (rejected: wrong language for MVP indexing).
- Evidence: GitHub API licence fields (null = no licence); repo READMEs; local file counts for primary.
- Reason: No candidate besides the primary currently passes licence + scope; per stop conditions, ask human before using an unlicensed repo.
- Confidence: Medium
- Fallback: PetClinic as cross-language stress reference only (never indexed in MVP), or Conduit-FastAPI if human confirms licence in writing.
- Benchmark procedure: Re-score when human resolves licence question; record decision before Phase 6 needs it.
- Date: 2026-10-11

## D2.3 Secret scanner
- Status: LOCKED
- Decision: Built-in regex scanner required (`mentor/ingest/secrets.py`): AWS AKID, private-key headers, JWT-like, and quoted-literal `password=`/`api_key=` assignments (>=8 chars). gitleaks optional extra (not installed; built-in is the gate).
- Alternatives: gitleaks as required (rejected: extra install, same gate achievable with regex + filename exclusions); unquoted-assignment matching (rejected: false-positived on kwarg passing `password=user_in.password` and excluded 14 source files incl. the signup route).
- Evidence: Scanner tuning verified on `fst`: 0 files excluded as secret, signup `users.py` indexed, canary `AKIAIOSFODNN7EXAMPLE` detected, manifest contains zero scanner findings.
- Reason: Quoted-literal rule catches real key material while `.env`/key files (real secret locations) are excluded by filename.
- Confidence: Medium-high
- Fallback: gitleaks as extra check if installed; tighten patterns if a canary ever leaks.
- Date: 2026-10-11

## D2.4 Counterfactual transformation
- Status: LOCKED
- Decision: `scripts/make_counterfactual.py` (deterministic, seeded by sort order): top-20 defined symbols with >2 whole-word refs renamed to `<old>_cf` (whole-word, all text files); 5 route strings suffixed `-cf` (whole-literal + path-substring with `[A-Za-z0-9_-]` lookahead guard), signup-prioritized; 3 UPPER_CASE config defaults in `backend/app/core/config.py` suffixed `-cf`. `.git`/caches excluded from copy. Map at `evals/counterfactual_map.json` (identifiers/routes/config/intentionally_kept=[]).
- Alternatives: Random renames (rejected: non-reproducible); fewer renames (rejected: spec fixes 20/5/3).
- Evidence: `fst-cf` generated; integrity check (identifier `\bOLD\b`, route with `(?!-cf)` guard) reports zero genuine leftovers; `users.py:146` is `@router.post("/signup-cf", ...)` with `UserPublic_cf`; 984 new-name occurrences.
- Reason: Reproducible renames + signup coverage give the strongest available contamination control for the demo's key flow.
- Confidence: Medium (rename-everywhere can touch generated client code; harmless since the copy is never executed).
- Fallback: Delete `fst-cf` + map and regenerate (rollback procedure); never hand-edit the copy.
- Date: 2026-10-11

## D3.1 Grammars
- Status: LOCKED
- Decision: `tree-sitter==0.26.0` runtime + `tree-sitter-python==0.25.0` + `tree-sitter-typescript==0.23.2` (covers `typescript` and `tsx` via `language_typescript()`/`language_tsx()`); config via `PyYAML==6.0.3` (MIT) + stdlib `tomllib`/`json`. All pinned in `requirements.txt`.
- Alternatives: Older `py-tree-sitter` API (rejected: 0.2x line retired; 0.25+ unified `Parser(Language(...))` API verified working on this machine); LSP/CodeQL now (rejected: Future enrichers per A2).
- Evidence: Installed + probed 2026-10-11: `Parser(Language(tsp.language()))` parses Py classes/methods; TSX `export function` + `fetch("/api/x")` parses without error. Licences: METADATA classifier MIT (runtime), `License: MIT` on both grammar packages and PyYAML [OFFICIAL].
- Reason: Uniform multi-lang, error-tolerant, exact 0-based row/col positions (line = row+1).
- Confidence: High
- Fallback: Regex extraction for a language with no grammar, labelled lower confidence (per A2).
- Date: 2026-10-11

## D3.2 Worker isolation
- Status: LOCKED
- Decision: Parse each file in a child `multiprocessing.Process` (spawn) with per-file timeout 10s and 1MB size cap enforced in the parent. Crash/timeout/oversize marks the file `parse_failed` and indexing continues. `data/parses/<sha>.json` carries per-file status for Phase 4.
- Alternatives: Threads (rejected: a native crash/hang kills the indexer); larger timeout (rejected: 10s is generous; tree-sitter is linear-time, hangs mean pathological input).
- Evidence: Spec Phase 3 + tree-sitter linear-time property; pathological-nesting test proves the timeout path.
- Reason: A malformed file must never crash or hang the indexer.
- Confidence: High
- Fallback: Mark `parse_failed`, continue; Phase 4 skips such files with reason recorded.
- Date: 2026-10-11

## D3.1 amendment — runtime downgrade 0.26.0 → 0.25.2 (SUPERSEDES the D3.1 version pin)
- Status: LOCKED
- Decision: `tree-sitter==0.25.2` (grammars unchanged: `tree-sitter-python==0.25.0`, `tree-sitter-typescript==0.23.2`). `requirements.txt` updated.
- Alternatives: Stay on 0.26.0 and exclude crashing files (rejected: 0.26.0 killed workers non-deterministically — identical input passed 3/5 and crashed 2/5 in-process — so any coverage number on 0.26.0 was unrepeatable); upgrade grammars instead (rejected: grammars were never implicated; the runtime swap alone fixed it).
- Evidence: 2026-10-12 — `test_users.py` whole-file extract died ~12/12 attempts on 0.26.0 (in-process + workers, hang-or-0xC0000005 in python314.dll per Windows Event 1000) while all 27 functions parsed individually and all sub-ranges parsed; same file extracts 4/4 clean on 0.25.2; full-repo CLI on 0.25.2: 152/152 (100%). Golden outputs byte-identical across runtimes (same node shapes).
- Reason: Deterministic 100% beats flaky 98-99%. Per rollback rule, the previous version is pinned and the change recorded here.
- Confidence: High (measured, repeated)
- Fallback: If 0.25.2 shows any native death, the worker still contains it as `parse_failed` and the file is recorded.
- Date: 2026-10-12

## D3.2 clarification — one retry of transient worker deaths
- Status: LOCKED (clarifies D3.2, does not weaken it)
- Decision: `parse_many` retries crash/timeout failures once in a fresh process (`attempts` recorded per file). Deterministic skips (size, path-escape, unsupported) never retry. A file failing twice is `parse_failed` exactly per D3.2.
- Alternatives: No retry (rejected: proven-transient native deaths would permanently exclude parseable files); unlimited retries (rejected: a truly pathological file must fail fast).
- Evidence: `sdk.gen.ts` failed-then-passed across runs on 0.26.0; retry converts transients into parses without changing any success output.
- Reason: Fresh-process retry distinguishes transient worker death from unparseable input.
- Confidence: Medium-high
- Fallback: `retries=0` restores single-attempt behavior; nothing else changes.
- Date: 2026-10-12

## D3.2 amendment — supervised persistent worker (SUPERSEDES spawn-per-call)
- Status: LOCKED
- Decision: `parse_many` and `chunker.plan_file` may serve sequential calls from ONE persistent spawned child (`parse_worker.WorkerPool`: one process, request/response over the same Queue protocol, supervisor respawns on crash/timeout before the next call). Per-call timeout, one-retry, attempt-count, and drain-while-join semantics are unchanged; `run_isolated` stays as the API (and the fallback: deleting the pool call-sites restores spawn-per-call with no other change).
- Alternatives: Stay spawn-per-call (rejected: measured ~0.3s spawn tax per call, ~30x the parse itself; ~1,800 spawns for sklearn — see EVALUATION_RESULTS.md perf-00); threads (rejected: a native crash kills the indexer — the original D3.2 reason stands).
- Evidence: perf-00 spawn-tax measurement (0.28–0.34s spawned vs 0.009–0.01s in-process); crash-poisoning + determinism tests in `tests/test_parse_python.py`.
- Reason: Same containment (crash/timeout still contained per call and retried once), ~30x less overhead per file.
- Confidence: Medium-high (measured tax; containment re-proven by tests)
- Fallback: Revert call-sites to `run_isolated`; delete the pool.
- Date: 2026-10-17

## perf-05 gate: plan pruning NOT ADOPTED
- Status: LOCKED
- Decision: Keep full-tree chunk plans. Measured plan cost via pool (0.10–0.52s even on the 215KB file) is linear and small; pruning would save ~5% while risking `chunk_id` drift on oversized units (line-split fallback), which would invalidate caches, tour dep-hashes, and audit trails.
- Alternatives: Top-level-only plans with on-demand child fetch (rejected: complexity + identity risk for ~1 min on sklearn scale).
- Evidence: EVALUATION_RESULTS.md perf-05 gate (numbers above).
- Reason: Measured, not argued — the two binding costs (deadlock, spawn tax) are already gone.
- Confidence: High
- Fallback: Revisit only with new evidence + SUPERSEDED entry.
- Date: 2026-10-17

## D5.1 Query analysis
- Status: LOCKED
- Decision: Extract backticked identifiers, CamelCase/snake_case word tokens, route-like paths (`/seg/seg`), and file-like tokens (`name.ext`); keep the original query string for display and Phase 7 dense use. Identifier splitting reuses Phase 4 `split_identifier` for FTS matching.
- Alternatives: Raw query straight to FTS (rejected: backticks/slashes become noise; symbol/path retrievers need typed tokens); stemming (rejected: code identifiers must match exactly).
- Evidence: Spec Phase 5; fst flows contain literal routes (`/users/signup`) and symbol names.
- Reason: Code questions carry typed signals; each retriever consumes its own type.
- Confidence: High
- Fallback: Untyped fallback — all word tokens to BM25 when no typed token is found.
- Date: 2026-10-12

## D5.2 Fusion
- Status: LOCKED
- Decision: RRF over three rankings (BM25, symbol, path) with constant k=60: score(d) = Σ 1/(60 + rank). 1-based ranks; ties broken by chunk_id ascending for determinism.
- Alternatives: Score-weighted sums (rejected: BM25/symbol/path scores are incommensurable); lower k (rejected: paper fixed 60 in pilot, unaltered in validation).
- Evidence: Cormack/Clarke/Büttcher SIGIR 2009 primary paper, formula + k=60 confirmed live from cormack.uwaterloo.ca PDF 2026-10-12 [PRIMARY RESEARCH].
- Reason: Unsupervised, no training, robust to outlier rankings; deterministic.
- Confidence: High
- Fallback: Any single ranking alone (all three remain independently queryable).
- Date: 2026-10-12

## D5.3 Confidence signals
- Status: LOCKED
- Decision: Per query record top fused score; identifier coverage = fraction of extracted identifiers found (as FTS tokens) in top-10 chunk identifiers; two-retriever agreement = whether ≥2 of (BM25, symbol, path) rank the same chunk #1. Thresholds (τ_score, τ_cov) stay GATED to Phase 9 calibration; this phase only emits signals.
- Alternatives: Single-score gating now (rejected: thresholds need gold data, Phase 6/9).
- Evidence: Spec Phase 5; CodeGrep abstract verified live (arXiv 2608.05886): BM25 P=0.375 degrades, Jina 0.445 neutral, 0.677 helps — directional support for precision-gated behavior. File-level precision@10 defined operationally as (# top-10 files containing ≥1 known-relevant location)/10; G3 gate uses this definition on our gold set in Phase 22.
- Reason: Abstention (Phase 9) needs calibrated, explainable signals, not vibes.
- Confidence: Medium (thresholds uncalibrated until Phase 9)
- Fallback: None (signals always emitted, even when weak).
- Date: 2026-10-12

## D6.1 Gold composition
- Status: LOCKED (frozen; changes require v2 + SUPERSEDED entry)
- Decision: 30 items pre-tuning — 8 where/how, 6 arch, 6 flow, 4 why (2 HISTORY-answerable with commit blame, 2 UNKNOWN abstain-expected), 6 unanswerable with recorded grep absence evidence. Every answerable range read verbatim at the pinned SHA before authoring.
- Alternatives: Fewer items (rejected: 22 answerable is already the minimum for Wilson intervals with any width); tuning-first (rejected: unfalsifiable).
- Evidence: `evals/gold/v1.yaml` validates clean against fst (paths exist, ranges in-bounds); composition test enforces 8/6/6/4/6.
- Reason: Fixed target written before any retrieval/answer tuning.
- Confidence: High (verified locations); Medium (rubric coverage of "understanding" is inherently partial).
- Fallback: v2 with SUPERSEDED entry; never edit v1 in place.
- Date: 2026-10-12

## D6.2 Scoring unit + frozen hash
- Status: LOCKED
- Decision: Retrieval hit relevant iff its line range overlaps a gold range in the same file. Frozen `evals/gold/v1.yaml` SHA-256: `0389d55fb9811cdae33f3ec934baf7b523e3e38dbba09ef2fcc60412063b7762` (counterfactual `v1_counterfactual.yaml`: `aabf582ad4fe9c6022318a9492168f441783a8cd930c198d16f869d1931b6d75`, derived via `counterfactual_map.json`, validity-checked).
- Alternatives: File-level relevance (rejected: too coarse; line overlap rewards precise chunks).
- Evidence: Overlap rule implemented in `mentor/eval/metrics.py`; hash recorded here at freeze time.
- Reason: Line overlap matches the citation granularity the product promises.
- Confidence: High
- Fallback: None.
- Date: 2026-10-12

## D6.3 Statistics
- Status: LOCKED
- Decision: Every metric reported with n + Wilson 95% intervals (`mentor/eval/stats.py`); intervals that overlap mean "no detectable difference" (spec statistical honesty). Unanswerable items excluded from recall denominators (no ranges), counted for abstention later.
- Alternatives: Point estimates only (rejected: n=22 misleads); bootstrap (rejected: overkill for proportions; study phase uses it where paired).
- Evidence: Wilson unit test matches reference values.
- Reason: 30 items cannot separate small effects; intervals make that visible.
- Confidence: High
- Fallback: None.
- Date: 2026-10-12

## G1 embedding gate — OUTCOME: REJECTED (lexical-only ships)
- Status: LOCKED (outcome; revisit only with new evidence + SUPERSEDED entry)
- Decision: Dense retrieval NOT adopted. Default `DENSE_MODEL = "none"` (B3 lexical+symbol+path). `mentor/retrieve/dense.py` stays as a tested-but-disabled path; eval tooling pinned in `requirements-eval.txt` (not shipped).
- Alternatives: Adopt bge-m3 (rejected: fails time criterion, recall unmeasured-moot); adopt jina-v2-code (rejected: unrunnable + trust_remote_code supply-chain cost); adopt jina-code-0.5b (rejected without download: non-commercial per V15, needs GPU + trust_remote_code).
- Evidence (measured 2026-10-12, this laptop, CPU-only torch 2.14.1):
  - Licences verified on source cards: bge-m3 MIT (1024d/8192ctx/568M, no query prefix needed); jina-embeddings-v2-base-code Apache-2.0 (768d/8k/161M, needs trust_remote_code); jina-code-0.5b class non-commercial (V15).
  - bge-m3: downloaded (~2.3 GB) + loads with low-mem flags (first attempt OOM at 3.9 GB free RAM without them); encode throughput 319 chunks / 19.9 min (~3.75 s/chunk, batch 4 @1024 ctx, 16 threads) → ~80 min projected full-corpus, FAILS the <30 min rule. Recall@10 therefore unmeasured (moot: all three criteria must hold).
  - jina-v2-code: downloaded; load BLOCKED — custom modeling code imports `find_pruneable_heads_and_indices`, removed in transformers 5.19.0 (ST 6.1.0 stack). Downgrading transformers risks the ST stack; the model additionally requires trust_remote_code (T8). Fails the runs-on-CPU requirement.
  - B3 floor stands: R@10 0.424 (Phase 6, n=22).
- Reason: Neither candidate satisfies all of (gain ∧ time ∧ licence). Lexical-only shipping is the specified success outcome, not a failure.
- Confidence: High (time/licence blockers measured, not inferred)
- Fallback: B3 lexical-only; revisit on server-tier hardware (GPU) or lighter permissive models, via new G1 run.
- Date: 2026-10-12

## D8.0 Serving deviation (Ollama blocked -> llama.cpp server)
- Status: LOCKED (for G2 measurement; Ollama remains the documented default)
- Decision: G2 measurements run on llama.cpp `llama-server` (Vulkan backend, ggml-org nightly b11429, MIT) with GGUF weights from official Qwen HF repos, because the Ollama Windows installer (1.5 GB) downloads at ~0.06 MB/s from here (~300 h; measured over 25 min with resume). The gateway ships BOTH adapters: Ollama (spec default, loopback, for when installable) and llama-server (OpenAI-compatible, A17 fallback, used live now). G2 numbers are labeled with backend `llamacpp-vulkan`; Ollama/CUDA re-measurement is future work when the installer is obtainable.
- Alternatives: Wait for Ollama (rejected: blocks the phase on a ~300 h download); CPU-only inference (rejected: cannot measure GPU VRAM, the point of G2); untrusted mirror downloads (rejected: T8 supply-chain violation).
- Evidence: Measured throughput (103 MB in 25 min, resume-capable); llama.cpp v0.6.0/b11429 release notes + API asset list (vulkan-x64 33 MB); nvcuda.dll present (driver 610.74) so no CUDA toolkit needed for Vulkan.
- Reason: Same GGUF weights + same JSON-schema contract make the VRAM/schema/throughput answers transfer with a stated backend caveat.
- Confidence: Medium (backend differs; VRAM physics does not)
- Fallback: If Vulkan offload fails, CPU-only llama-server for schema-validity only, VRAM recorded as unmeasured.
- Date: 2026-10-12

## D8.1 Default model
- Status: SUPERSEDED by G2 outcome 2026-10-15 (7B remains qualified fallback)
- Decision: Default candidate Qwen2.5-Coder-7B-Instruct Q4_K_M GGUF (Apache-2.0 per V16; ~4.7 GB) from the official Qwen HF repo. Alternative: Qwen3-4B-Instruct Q4_K_M GGUF (Apache-2.0 verified on Qwen/Qwen3-4B-GGUF card 2026-10-12; 4B dense, 36 layers, 8 KV heads, ~2.5 GB, within the 5.5 GB Q4 cap; run in non-thinking mode via /no_think for deterministic output).
- Alternatives: 14B Q4 (~8.4-9 GB, no fit per V17); gpt-oss-20b (16 GB min); Qwen3-30B MoE (server only).
- Evidence: V16-V17; Qwen3-4B-GGUF card (apache-2.0, Q4_K_M 2.5 GB) [OFFICIAL].
- Reason: Largest permissive coder fitting ~7 GB usable; Qwen3-4B is the only smaller permissive dense coder in the cap.
- Confidence: Medium (measured in G2)
- Fallback: Smaller model at 4096 ctx, then CPU-only; record perf impact.
- Date: 2026-10-12

## D8.2 Context length
- Status: LOCKED (default 8192; G2 may revise to 4096)
- Decision: Default 8192. Reference arithmetic [INFERENCE]: Qwen2.5-Coder-7B (28 layers, 4 KV heads, head dim 128): KV fp16 = 2*28*4*128*2 B/token = 57,344 B/token, ~0.47 GB at 8192. Weights ~4.7 GB Q4_K_M + buffers + display share of 8 GB. Measurement replaces arithmetic.
- Alternatives: 4096 default (fallback if 8K peak >7.0 GB); 32K YaRN (rejected: KV alone ~1.9 GB, no headroom).
- Evidence: Architecture figures V16; nvidia-smi measurement in G2.
- Reason: 8K fits the demo evidence budget (~3000 tokens) with headroom; 4K fallback documented.
- Confidence: Medium (calculated; measured in G2)
- Fallback: 4096, re-run G2.
- Date: 2026-10-12

## D8.3 Concurrency
- Status: LOCKED
- Decision: Single-user laptop: one loaded model, one parallel request. Ollama names verified in current docs (docs.ollama.com/faq 2026-10-12): `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1` (RAM scales NUM_PARALLEL x CONTEXT_LENGTH). llama-server equivalent used live: `--n-parallel 1`.
- Alternatives: Defaults (3 models / parallel>1) (rejected: VRAM contention on 8 GB).
- Evidence: Ollama FAQ concurrency section [OFFICIAL].
- Reason: Deterministic latency + no OOM from parallel KV.
- Confidence: High
- Fallback: None.
- Date: 2026-10-12

## D8.4 Output mode
- Status: LOCKED
- Decision: Always JSON schema (`format` in Ollama; `response_format: {type: json_object}` + schema prompt on llama-server OpenAI endpoint), temperature 0, plus server-side validation + one repair (Phase 9). Never rely on schema adherence alone (V18: adherence not guaranteed).
- Alternatives: Prompt-only JSON (rejected: unreliable on small models); grammar-constrained decoding (rejected: extra dependency for equal guarantee since server validates anyway).
- Evidence: V18; llama-server OpenAI-compat docs (response_format support).
- Reason: Adherence is probabilistic; validation is deterministic.
- Confidence: High
- Fallback: Deterministic abstention after two failures (Phase 9).
- Date: 2026-10-12

## D4.1 Chunk budget
- Status: LOCKED
- Decision: Max ~512 approximate tokens per chunk, tokens = characters // 4 of chunk `text` (deterministic approximation, recorded here). cAST split-then-merge: top-level AST units; oversized units split recursively at named-child boundaries; small adjacent siblings merged greedily while within budget. Code files (py/ts/tsx/js/jsx) via isolated AST plan (fresh `run_isolated` child per file — same containment as D3.2 after the 0.26.0 saga); other indexed text files (json/yaml/toml/md/etc.) via degraded line windows of 80 lines with 20-line overlap. A single leaf that cannot split within budget is emitted whole and flagged `is_exception=1` (recorded, queryable).
- Alternatives: Fixed token windows (rejected: splits mid-syntax, citations point at fragments); AST-only with no fallback (rejected: config files carry ports/deps facts needed for arch questions).
- Evidence: cAST paper V12 (principle); FTS5 docs verified live (UNINDEXED, unicode61, bm25 on SQLite 3.50.4, 2026-10-12) [OFFICIAL].
- Reason: Chunks align to syntax so citations point at real units; every indexed line lands in some chunk.
- Confidence: High (principle); Medium (gain transfer — measured Phase 5+).
- Fallback: Line windows for everything (degraded mode), recorded as such.
- Date: 2026-10-12

## D4.2 Two text forms
- Status: LOCKED
- Decision: `text` = exact original source lines (citation/display only). `embed_text` = `header + "\n" + text` where header = repo path + overlapping symbol qualnames. Citations never use `embed_text`; validator (Phase 9) will reject header-only evidence.
- Alternatives: Single text with header prepended (rejected: displayed citation would show text the file does not contain at those lines).
- Evidence: Spec Phase 4; Phase 3 line-invariant machinery.
- Reason: Displayed citations must be byte-exact reproductions of source lines.
- Confidence: High
- Fallback: None.
- Date: 2026-10-12

## D4.3 Chunk identity
- Status: LOCKED
- Decision: `chunk_id = sha256(repo_sha + "\n" + path + "\n" + str(start) + "\n" + str(end) + "\n" + content_hash)[:16]`, `content_hash = sha256(text)`. Newline-joined (unambiguous vs raw concatenation). Rebuilds are byte-identical by construction (no timestamps stored anywhere).
- Alternatives: Raw concatenation (rejected: ambiguous boundaries, e.g. path "a/b"+lines vs "a"+"/b" lines); UUIDs (rejected: non-deterministic, breaks idempotence gate).
- Evidence: Implemented in `mentor/index/hashing.py`; idempotence test compares two independent builds.
- Reason: Deterministic identity is the freshness/invalidation key (Phase 17).
- Confidence: High
- Fallback: None.
- Date: 2026-10-12

## D3.3 Edge labels
- Status: LOCKED
- Decision: Import edges are `resolved` only when the resolved target file exists in the repository (relative imports + `backend/`-rooted absolute imports for Py; relative + `@/`-aliased for TS). Everything name-based is `likely`. No other label permitted.
- Alternatives: Trusting unresolved imports as resolved (rejected: dishonest); full type resolution (rejected: needs LSP/build, Future).
- Evidence: fst verified: `from app import crud` resolves to `backend/app/crud.py`; `settings.API_V1_STR` app prefix is dynamic so full URL prefixes stay `prefix_unknown`.
- Reason: Tours (Phase 13) may state `calls` only on resolved edges.
- Confidence: High
- Fallback: `likely` label; unresolved imports recorded with `target: null`.
- Date: 2026-10-11

## G2 local-model gate — OUTCOME: Qwen3-4B-Instruct Q4_K_M @8192 (SUPERSEDES D8.1 default)
- Status: LOCKED (outcome; revisit only with new evidence + SUPERSEDED entry)
- Decision: G2 winner is Qwen3-4B-Instruct Q4_K_M (`Qwen/Qwen3-4B-GGUF`, Apache-2.0, ~2.5 GB) at ctx 8192 via llamacpp-vulkan. `mentor/config.py`: `LLM_MODEL = "qwen3-4b-instruct-q4_k_m"`, `LLM_CTX = 8192`, `LLM_SYSTEM_SUFFIX = "/no_think"`. Qwen2.5-Coder-7B-Instruct Q4_K_M stays a qualified fallback (`LLM_FALLBACK_MODEL`, no suffix).
- Alternatives: Keep 7B default (rejected: G2 tiebreak is explicit — validity tied at ceiling, lower VRAM wins; Rule 5, gates are measured not argued); 14B/gpt-oss-20b/30B-MoE (rejected without download: no VRAM fit per V17).
- Evidence (measured 2026-10-15, target RTX 5060 8GB, llama.cpp b11429 Vulkan, `-ngl 99 -c 8192 -np 1`; raw `docs/bench_7b.json`, `docs/bench_4b.json`):
  - 7B: peak 4814 MiB (4.70 GB) ≤7.0 GB ✓; validity 22/22 = 1.000 [0.85, 1.00] ✓; sustained 288 it, 51.9 tok/s, ≤70.5 W ✓; Q mean 2.55 s / TTFT 0.10 s.
  - 4B: peak 3658 MiB (3.57 GB) ✓; validity 22/22 = 1.000 [0.85, 1.00] ✓ (with `/no_think`); sustained 345 it, 82.9 tok/s, 62–71 W ✓; Q mean 0.94 s / TTFT 0.13 s.
  - Both satisfy (a)+(b)+(c); validity tied → tiebreak lower VRAM → 4B (EVALUATION_RESULTS.md Phase 8).
- Reason: Rule-bound choice with real wins (1.6× throughput, 1.1 GB less VRAM, equal validity). Known caveats recorded, not argued away: validity probe checks shape, not code-answer correctness (Phase 9 correctness comparison is the defined revisit trigger if it favors the code-specialized 7B); 4B needs `/no_think` or thinking tokens exhaust the budget (measured 5.1 s + empty vs 0.3 s + valid JSON).
- Confidence: High (gates measured); Medium (code-answer quality unmeasured until Phase 9)
- Fallback: 7B-coder at 8192 (all gates pass, 2.3 GB headroom), then 4096, then CPU-only per Phase 8 rollback.
- Date: 2026-10-15

## D9.1 Evidence format
- Status: LOCKED
- Decision: Blocks E1..En assigned by the server in retrieval rank order; each carries path, start/end lines, header symbol, and line-numbered text (`  12 | code`). Text read from `chunks.text` in the index, never the working tree. Budget ~3000 approx tokens (chars//4, D4.1); over-budget hits dropped with `truncated=true`.
- Alternatives: File reads at answer time (rejected: cited artifact must be the index); larger budget (rejected: 4B context discipline + G2 8K ctx).
- Evidence: `mentor/answer/evidence.py`; budget test in `tests/test_abstain.py`.
- Reason: Server-numbered IDs make citation validity true by construction (model never writes paths/lines).
- Confidence: High
- Fallback: Smaller k (fewer hits) if budgets bind.
- Date: 2026-10-16

## D9.2 Answer contract
- Status: LOCKED
- Decision: Pydantic models (`mentor/answer/contract.py`): `Answer{status: answer|abstain, segments: [{text, kind: fact|inference|unknown, evidence_ids}], missing: []}`. Full JSON schema travels via the gateway `format` parameter; the PROMPT carries only a compact shape + one example — pasting the full schema makes the 4B model echo it verbatim (measured 2026-10-16).
- Alternatives: Raw-dict validation (rejected: Pydantic reuses the Phase 10 API schemas, MIT, free); full-schema-in-prompt (rejected by measurement).
- Evidence: `pydantic==2.13.5` pinned in `requirements.txt`; licence MIT [OFFICIAL: pydantic docs/LICENSE].
- Reason: One schema definition serves gateway constraint, validation, and (Phase 10) API.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D9.3 Validator rules
- Status: LOCKED (V1–V8; V9 arrives Phase 14)
- Decision: `mentor/answer/validator.py` enforces V1 schema-parse+conform, V2 known IDs, V3 facts cited, V4 backticked identifiers substring-matched in cited text, V5 ≤600 chars/≤12 segments, V6 answer needs a cited fact, V7 no URLs/HTML/Markdown-links, V8 no `path:line` strings. Failures return codes fed to the single repair; double failure abstains. Target 100% on `tests/fixtures/invalid_outputs.json`.
- Alternatives: LLM-as-judge validation (rejected: probabilistic guard for a deterministic property); NLI entailment in the loop (rejected: FactRel shows factual support ≠ NLI entailment; RefNLI shows retrieved premises break reference determinacy — validator checks containment, Phase 22 measures support).
- Evidence: `tests/test_validator.py` (12-case suite + valid controls); RESEARCH_LOG.md Phase 9.
- Reason: Deterministic property, deterministic check; semantic entailment is explicitly out of scope (honest limit, docs/ARCHITECTURE.md).
- Confidence: High
- Fallback: Per rollback rule, never remove a rule to pass tests; record failure rates instead.
- Date: 2026-10-16

## D9.3 Amendment (V4 match scope, 2026-10-17)
- Status: LOCKED (amends V4 of D9.3 only; V1–V3, V5–V9 stand)
- Decision: V4 accepts a backticked identifier when it appears in the cited blocks' text OR equals the server-assigned `path` of a cited block. Path match is exact on the block's own `path` field; the model cannot invent it (paths are server-assigned per D9.1), so the containment property is preserved while removing a measured false positive: a file's own path never occurs in its source text.
- Alternatives: Keep text-only matching (rejected: measured — an answer correctly citing the block for `backend/app/api/routes/users.py` and naming that path is rejected as `V4_UNSUPPORTED_IDENTIFIER`, burning the single repair and abstaining on a correct answer; reproduced deterministically 2026-10-17 on the live pipeline); drop V4 for path-shaped identifiers (rejected: naming the path of a NON-cited block must still fail — pinned as a new negative test).
- Evidence: `tests/test_validator.py::test_v4_accepts_path_of_cited_block` + `::test_v4_rejects_path_of_uncited_block`; invalid suite still 12/12 (fixture `backticked_identifier_absent` keeps its code; blocks without a `path` field still reject).
- Reason: The cited block is itself the proof its path exists; V4's property is "identifiers are supported by the cited evidence", not "identifiers are substrings of code text".
- Confidence: High (false-positive fix; both directions pinned by tests)
- Fallback: Revert to text-only match (restores the measured false positive).
- Date: 2026-10-17

## D9.4 Abstention (thresholds LOCKED)
- Status: LOCKED
- Decision: Two layers. Pre-generation: abstain without a model call when `top_score < TAU_SCORE (0.02)` or (`identifier_coverage < TAU_COV (0.0)` with identifiers present — i.e. coverage gate OFF: grid search found it adds nothing beyond score on dev). Post-generation: abstain when validation + one repair fail. Calibrated on dev split (seed 7, n=15): correct 12/15, accuracy 0.800, false_answer 0, false_abstain 3. Held-out test (n=15): correct 10/15, false_answer 1/2 = 0.500 [0.09, 0.91], false_abstain 4/13 = 0.308 [0.13, 0.58]. Raw: `docs/calibration_p9.json`.
- Alternatives: Higher taus (rejected: dev accuracy drops); coverage gate on (rejected: no dev gain); τ_score at exact observed-score values is a grid artifact — recorded as limitation, re-check in Phase 22 on more items.
- Evidence: `scripts/calibrate_tau.py`; `docs/eval_answers_dev.json` + `docs/eval_answers_test.json` (locked-taus confirmation runs).
- Reason: False answers are the product failure; the gate trades a measured false-abstain rate for zero dev false answers.
- Confidence: Medium (n=15/split; intervals wide and reported)
- Fallback: τ_score=0.0 (gate off) restores full-recall behavior; any τ change after held-out use requires a recorded entry.
- Date: 2026-10-16

## D10.1 Binding
- Status: LOCKED
- Decision: Serve binds loopback only (127.0.0.1/::1/localhost). `resolve_bind()` refuses any other host unless `--unsafe-bind` is passed (documented unsupported). CORS allows exactly one local origin (`WEB_ORIGIN`, credentials off, GET+POST only). Bodies capped at 1 MB (413 beyond).
- Alternatives: 0.0.0.0 for LAN demo (rejected: single-user localhost product; C7); wildcard CORS (rejected).
- Evidence: `mentor/api/app.py`; `tests/test_api.py::test_bind_refuses_non_loopback_without_flag`; FastAPI CORSMiddleware docs (explicit allow_origins list) + local TestClient verification [OFFICIAL + measurement].
- Reason: The laptop is not a server (hardware ledger); loopback is the isolation boundary for the single-user tier.
- Confidence: High
- Fallback: `--unsafe-bind` exists but is unsupported and untested beyond the refusal test.
- Date: 2026-10-16

## D10.2 Audit contents
- Status: LOCKED
- Decision: One row per served ask in the index `audit` table: ts, repo_id, sha, q_hash (SHA-256 of normalized question), evidence [{id,path,lines}] (closest refs for abstentions), provider, model, status, verdict (valid|repaired|abstained-pre|abstained-post|gateway-error|cached), prompt_version, cached flag. q_text/a_text stay NULL unless `AUDIT_STORE_TEXT=true` (default false).
- Alternatives: Full-text logs (rejected: leak damage; T1); no audit (rejected: egress accountability).
- Evidence: `mentor/answer/audit.py`; `tests/test_audit.py` (exactly one row, hash matches, text columns NULL).
- Reason: Hashes answer "what left the laptop on what evidence" without storing content.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D10.3 Caching
- Status: LOCKED
- Decision: Cache key = sha256(repo_id, sha, INDEX_SCHEMA_VERSION, normalized-question hash, provider, model, prompt version, k). Only status=answer outputs with ≥1 cited fact are stored; abstentions never (re-evaluated after index changes). SHA+repo+schema-version in the key makes cross-repo/cross-commit hits impossible by construction.
- Alternatives: Cache abstentions (rejected: staleness after reindex); TTL expiry (rejected: content-keyed already; freshness handled Phase 17).
- Evidence: `mentor/answer/cache.py`; `tests/test_cache.py` (hit on repeat, miss on SHA change, abstention re-calls model).
- Reason: Deterministic answers are pure functions of (repo, commit, question, model, prompt) — safe to memoize.
- Confidence: High
- Fallback: Delete cache rows (recomputed on demand).
- Date: 2026-10-16

## D10.4 Service tables without content rebuild
- Status: LOCKED
- Decision: schema.sql gains additive `audit` + `cache` tables; version 1→2 (`store.SCHEMA_VERSION`, `PRAGMA user_version`, meta row). Content tables byte-identical, so existing indexes gain the tables via `ensure_service_tables()` (CREATE TABLE IF NOT EXISTS from canonical DDL) instead of a full rebuild.
- Alternatives: Full re-index (rejected: content unchanged, wasteful); silent migration (rejected: version rule).
- Evidence: `mentor/index/store.py::ensure_service_tables`; existing fst.sqlite (v1) serves audit/cache after ensure.
- Reason: Version rule honored (bump + record), rebuild cost avoided with proof of equivalence (DDL sourced from schema.sql itself).
- Confidence: High
- Fallback: Full rebuild produces identical content tables plus the new ones.
- Date: 2026-10-16

## D10.5 Service dependencies
- Status: LOCKED
- Decision: `fastapi==0.141.1` (MIT), `uvicorn==0.53.0` (BSD-3), `httpx==0.28.1` (BSD-3, TestClient transport) pinned in requirements.txt. All free/open, permissive licences.
- Alternatives: stdlib http.server (rejected: no typing/validation story; FastAPI+Pydantic reuse the contract models).
- Evidence: Installed + smoke-served 2026-10-16 [OFFICIAL: package licences].
- Reason: Spec stack (A16) names FastAPI+Pydantic; uvicorn/httpx are its standard serve/test companions.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D11.1 Cloud gate order
- Status: LOCKED
- Decision: A cloud call happens only if ALL hold, in this order: `ALLOW_FREE_CLOUD=true` → repo `allowlisted_public=true` (per-repo registration field, default false) → manifest shows no `secret`-skipped files → redaction ran on every block (secret-indicator lines removed, flagged blocks dropped, counts-only report) → redacted payload ≤ `CLOUD_MAX_TOKENS` (6000) → daily budget under 90% of recorded limits. Gemini additionally requires public (its own pre-check). First failure returns `CLOUD_BLOCKED:<reason>` and the chain falls back; nothing is sent.
- Alternatives: Single master switch only (rejected: one flag cannot express repo/scan/budget states); allowlist-only (rejected: secret/budget risks remain).
- Evidence: `gateway.check_cloud_allowed` + `qa._serve_with_cloud`; `tests/test_cloud_gating.py` (order, private block, dirty-scan block, host pinning).
- Reason: Six independent failure modes need six named, testable conditions with a deterministic order.
- Confidence: High
- Fallback: `ALLOW_FREE_CLOUD=false` restores pure-local with no other change (rollback procedure).
- Date: 2026-10-16

## D11.2 Primary and fallback
- Status: LOCKED
- Decision: Groq primary → Gemini fallback → local last. Chain tries each configured provider once (no 429 retries — re-hitting a rate limit is wrong); any transport/rate-limit/timeout/schema failure moves to the next; final local failure abstains per Phase 9. Contract identical at every step; responses carry provider/fallback/cloud_status labels (Phase 16 UI). Repair always runs locally (no quota spent). Model names from live `list_models`, never hardcoded; empty model/key = provider skipped as "unconfigured".
- Alternatives: Single provider (rejected: free quotas are volatile); 429 retry-with-backoff (rejected: burns quota, delays fallback).
- Evidence: `qa._serve_with_cloud`, `gateway.generate_auto`; `tests/test_fallback.py` (429→local same contract, schema propagates, no-keys local).
- Reason: Free tiers fail often and without notice; the chain treats every cloud call as expendable.
- Confidence: High
- Fallback: Local-only (default).
- Date: 2026-10-16

## D11.3 Budget tracking
- Status: LOCKED
- Decision: `mentor/llm/budget.py` counts requests + approx tokens per provider per UTC day in `data/budget.sqlite` (gitignored runtime). Stop at 90% of RECORDED limits: Groq free {rpd: 1000, tpd: 200000} (docs 2026-10-16); Gemini `{}` = fail-closed until AI Studio console quotas are recorded by the operator (no keys on this machine). Estimates use prompt tokens + max_tokens ceiling (recorded approximation).
- Alternatives: Header-based remaining-quota tracking (rejected: headers only arrive WITH responses; budget must gate BEFORE the call); no budget (rejected: quota burn kills the demo).
- Evidence: `tests/test_budget.py` (90% stop on both legs, fail-closed, accumulation).
- Reason: Free-tier binding constraint is tokens/day; the gate must trip before the provider does.
- Confidence: Medium (estimate-based accounting; headers would refine)
- Fallback: Local inference (automatic).
- Date: 2026-10-16

## D12.1 Clustering
- Status: LOCKED
- Decision: Directory-based grouping (the repo's own packaging) refined by import density: groups are fixed directory rules; IMPORT edges between groups come from resolved import rows with chunk evidence. Heavier methods (ACDC dominator patterns, Bunch MQ search, WCA/LIMBO hierarchical, DSM ensembles) rejected for this repo: fully-automatic techniques lack precision alone, and fst's top-level dirs already name its layers.
- Alternatives: Pure directory listing without edges (rejected: no flow information); Bunch-style optimization (rejected: unreadable tuning cost for 208 files).
- Evidence: RESEARCH_LOG.md Phase 12 (recovery literature survey); `mentor/features/arch.py`; golden `tests/golden/arch_fst.json` (8 nodes / 14 edges, reviewed).
- Reason: Simplest readable result; every group and edge traces to evidence.
- Confidence: High
- Fallback: Directory-only grouping (drop inter-component edges) per rollback rule.
- Date: 2026-10-16

## D12.2 Component kinds
- Status: LOCKED
- Decision: Kinds assigned by rule from actual fst paths: entrypoint=backend/app/main.py; api-layer=backend/app/api/**; model-layer=models.py + alembic/ (schema-adjacent); service-layer=crud.py + initial_data.py + utils.py; frontend=frontend/src/**; external-database=compose `db` service image (never code); configuration=compose.*.yml + core/**; test=backend/tests/** + frontend/tests/**.
- Alternatives: Language-based grouping (rejected: splits the request flow); per-file nodes (rejected: 208 nodes unreadable).
- Evidence: fst tree + index facts read 2026-10-16 (23 routes, User/Item tables, postgres:18, TanStack routes).
- Reason: Rules mirror the reviewed layout, so the diagram cannot drift from the code it claims to show.
- Confidence: High
- Fallback: None (rules are data; new repos get their own recorded mapping).
- Date: 2026-10-16

## D12.3 Label source
- Status: LOCKED
- Decision: Labels generated from directory/symbol names by code. Optional LLM plain titles accepted ONLY if containing a ≥4-char word present in the node's cited evidence (`summaries.accept_title`); otherwise the deterministic label stands. Unknown node ids ignored.
- Alternatives: Free LLM labels (rejected: failure condition — unevidenced titles); no LLM step (kept as fallback; currently optional/precompute).
- Evidence: `tests/test_arch.py::test_title_validation_rejects_unevidenced`.
- Reason: Readability upgrade without breaking the evidence chain.
- Confidence: High
- Fallback: Deterministic labels (always).
- Date: 2026-10-16

## D13.1 Tour definitions
- Status: LOCKED
- Decision: Three seeds in `evals/tours/*.yaml` (question, method, route, handler + handler lines), all authored from code reading and cross-checked against the routes table: signup POST /signup → register_user users.py:147-159; login POST /login/access-token → login_access_token login.py:24-42; crud POST /items/ → create_item items.py:62-72. Seed resolves via routes table (method+handler+route-substring); yaml lines are the reviewed record.
- Alternatives: Free-text tour requests resolved by retrieval (rejected: seed must be exact for reproducibility).
- Evidence: Code reads recorded in RESEARCH_LOG.md Phase 13; `tests/test_tours.py::test_golden_signup_first_step`.
- Reason: A wrong seed invents the whole tour; seeds are the one human input.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D13.2 Traversal
- Status: LOCKED
- Decision: BFS from the handler over resolved-first then likely edges, depth ≤ 3, fan-out ≤ 8 per node, same-named symbols disambiguated by caller file (edge from_file must match). Resolution upgrades: (1) Phase 3 import rows store {name,alias} dicts — matched on either; (2) `from package import submodule` (empty __init__ shims) falls back to the sibling submodule file; (3) `module.attr(...)` sites resolve the ATTRIBUTE in the module file; (4) external imports, builtins, and caller parameters drop with logged reasons (tours trace first-party flow).
- Alternatives: Pure name-based hops (rejected: measured 0 resolved hops before the fix — the import-row shape bug); full call-graph precision (rejected: needs LSP, Future).
- Evidence: `mentor/features/tours.py::_outgoing`; traversal progression measured in-session (0 → majority-resolved hops).
- Reason: Each rule converts a measured "likely" into a "calls" with evidence, or a principled drop.
- Confidence: High
- Fallback: Directory-only arch nodes (no tour) if a flow cannot reach 3 steps.
- Date: 2026-10-16

## D13.3 Step rule
- Status: LOCKED
- Decision: Every step — LLM-narrated AND deterministic fallback — passes through the Phase 9 validator (fact segment citing step evidence); rejection drops the step with a logged reason and renumbers. Resolved steps cite definition + call-site chunks (the claim spans both). CRUD tour holds exactly 3 steps: session.add/commit produce no call edges (parser limitation, recorded) — minimum met honestly, no invention.
- Alternatives: Unevidenced fallback steps (rejected: failure condition).
- Evidence: `tours.narrate` (returns None on rejection); precompute logs (signup 8, login 6, crud 3 steps).
- Reason: D13.3 makes no exception for fallbacks; structure never depends on the model.
- Confidence: High
- Fallback: Narrow the tour (rollback rule), never invent steps.
- Date: 2026-10-16

## D13.4 Labelling
- Status: LOCKED
- Decision: `calls` only for import-resolved definitions; everything else "likely calls, by name" (tested on fixture + real index). Deterministic titles use bare identifiers (module prefixes name the call site, not the chunk — normalized before validation AND display).
- Alternatives: Confident labels for likely hops (rejected: failure condition).
- Evidence: `tests/test_tours.py::test_label_rule_resolved_vs_likely`.
- Reason: The label IS the uncertainty communication (C9).
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D14.1 Provenance labels
- Status: LOCKED
- Decision: Per-segment provenance: `proven` (code evidence only), `history` (an H commit-record cited), `inferred` (labelled guess, separate section by kind), `unknown`. Labels DEFAULT server-side from pointers (fact+H→history, fact→proven, inference→inferred, unknown→unknown); an explicit model label is kept. Enforcement is on evidence IDs (V9), never on the label — labels are display, pointers are proof.
- Alternatives: Model-assigned labels only (rejected: cheap talk, unenforced); no labels (rejected: acceptance requires labelled answers).
- Evidence: `qa.ask` provenance defaulting; `tests/test_why.py::test_provenance_derived_from_pointers_not_labels`.
- Reason: A model can write "history" next to any claim; only the H-citation makes it so.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D14.2 Causal rule (V9)
- Status: LOCKED
- Decision: Validator V9 rejects fact-kind segments whose text matches causal markers (because|in order to|so that|to avoid|to prevent|exists to|designed to|intended to|was created/added/introduced to) unless they cite ≥1 H-block. Tight by design ("to <verb>" alone is everywhere). History means "recorded rationale" (commit text is untrusted input), never "proven intent" — the honest limit extends here.
- Alternatives: Broad causal regex (rejected: false positives on benign flow text); NLI entailment check (rejected: Phase 9 honest limit).
- Evidence: `tests/test_validator_v9.py` (reject/accept/inference/label cases).
- Reason: "X exists because Y" as fact without a record is the most misleading output class; V9 makes it unservable.
- Confidence: Medium (heuristic markers, not semantic understanding — recorded limitation)
- Fallback: Per rollback rule, never remove V9 to pass; record rejection rates.
- Date: 2026-10-16

## D14.3 Optional network
- Status: LOCKED
- Decision: `gh pr view` lookup exists (`why.gh_pr`) but is OFF by default (`GH_PR_LOOKUP=false`); disabled path returns None with zero socket attempts (SocketGuard-verified). When enabled, PR number/title/URL/author appends as an H-block. fst history is deep enough locally (1535 commits, PR refs in squash summaries) that offline is the default.
- Alternatives: Always-on PR enrichment (rejected: network dependency + failure mode for zero offline gain on this repo).
- Evidence: `tests/test_why.py::test_gh_disabled_makes_no_network_call`; `gh` absent on this machine (recorded).
- Reason: Offline-first product; network is an accelerator, never a requirement.
- Confidence: High
- Fallback: Local blame/log (always).
- Date: 2026-10-16

## D15.1 Signals
- Status: LOCKED
- Decision: Offline signals only: TODO/FIXME/HACK at exact lines; public backend functions with no test-name refs AND no dedicated test file (test_<stem>.py / stem.spec.* — helper-name collisions excluded); route handlers lacking response_model (decorator-span check, not chunk substring); undocumented public functions capped at 3 smallest (stylistic absence is not a task per file). Excluded: alembic/* (migration history), *.gen.ts (build artifacts). No `good first issue` labels (network off by default).
- Alternatives: All-signals firehose (rejected: measured noise — alembic downgrades, name collisions); GitHub labels (rejected: network dependency).
- Evidence: `mentor/features/tasks.py`; 20 candidates on fst (14 missing-tests, 6 no-response-model, 3 docstring, 2 todo→1 after dedupe).
- Reason: Every signal must survive a "would a maintainer accept this PR" test; exclusions are recorded, not silent.
- Confidence: Medium (heuristics, honest)
- Fallback: TODO + missing-test signals only (rollback rule).
- Date: 2026-10-16

## D15.2 Difficulty
- Status: LOCKED
- Decision: difficulty = 1.0·log(lines) + 2.0·files_touched + 0.5·fan_in in config. fan_in is SYMBOL-level (callers + resolving name-importers); file-popularity scoring measured absurd (2-line helper at 10.69) and was rejected. Calibration rank recorded before weights (evals/tasks_calibration.md); one deviation recorded as revision (security-tests scope-small but risk-flagged — axes separated by design). Weights unchanged after measurement.
- Alternatives: File fan-in (rejected by measurement); complexity metrics (rejected: literature shows practitioners prefer simple, interpretable metrics).
- Evidence: `tests/test_tasks.py::test_scoring_matches_configured_formula`; RESEARCH_LOG.md Phase 15.
- Reason: Repeatable within-repo ordering with interpretable parts; weights are judgment, stated as such.
- Confidence: Medium (judgment, per literature)
- Fallback: None (weight changes require a recorded entry).
- Date: 2026-10-16

## D15.3 Risk
- Status: LOCKED
- Decision: risk = fan_in + 5 per keyword hit (auth|password|migration|security|payment over file+symbol). Risk ≥ 8 sinks below the top five, still listed. No fst task hits 8 (max measured 7); the cutoff is live but untriggered — recorded, not tuned to trigger.
- Alternatives: Keyword-only risk (rejected: ignores blast radius); exclusion instead of sinking (rejected: hiding information from newcomers).
- Evidence: `tests/test_tasks.py::test_high_risk_excluded_from_top_five` (fixture).
- Reason: Risk communication, not censorship.
- Confidence: Medium
- Fallback: None.
- Date: 2026-10-16

## D15.4 Prerequisites
- Status: LOCKED
- Decision: From the task file's imports: sqlmodel/sqlalchemy/alembic → ORM; fastapi/starlette → FastAPI routing; pwdlib/passlib/jose/security/auth → authentication flow; pytest/httpx → test client. Deterministic, no model involved.
- Alternatives: LLM-inferred prerequisites (rejected: uncheckable).
- Evidence: `tasks.prerequisites`; e.g. deps.py tasks list all three correctly.
- Reason: Import lists ARE the prerequisite lists.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D15 refresh (tasks-1–tasks-6, SUPERSEDES parts of D15.1)
- Status: LOCKED
- Decision: (1) Signals are repo-agnostic: source/test split by suffix + test-path rules (no `backend/app/%` literals); exclusions match path segments (`alembic/`, `migrations/`, vendored `externals/`/`vendor/`); fst top-10 preserved, sklearn fires todo + missing-tests + missing-docstring (453 + 3 post-vendored-exclusion). (2) Every task carries deterministic acceptance criteria + a `pytest`/`bandit` verify command + nearest-example test + open-first range; validator confirms all paths. (3) Optional LLM polish (`ALLOW_TASK_POLISH=false` default) through the Phase 9 contract with deterministic fallback; served only on id + evidence-hash match. (4) New signals: Bandit findings via a stored index artifact (LOW first, HIGH sinks, cap 12); GitHub good-first-issue/help-wanted via opt-in live fetch (`ALLOW_GH_TASKS=false`, never offline), evidence-linked to retrieval hits, uncited issues skipped. (5) Calibration v2 on a sklearn sample: weights stand; framework-comprehension blind spot + benchmark-helper low-value recorded as limits.
- Alternatives: Per-repo signal configs (rejected: unmaintainable); LLM-written acceptance (rejected: uncheckable); cloud-hosted issue sync (rejected: network dependency in serving path).
- Evidence: `tests/test_tasks.py` (incl. cross-repo kinds test), `tests/test_task_polish.py`, `evals/tasks_calibration.md` v2, EVALUATION_RESULTS.md perf acceptance.
- Reason: Tasks must work on any repo, tell the newcomer exactly what "done" means, and never display unvalidated or stale text.
- Confidence: Medium-high (measured on two repos; GH path live-untested — no `gh` binary on this machine)
- Fallback: Deterministic spine (titles, acceptance, verify) serves alone with all flags off.
- Date: 2026-10-17

## D16.1 Stack
- Status: LOCKED
- Decision: React 18.3.1 + TypeScript 5.7.2 + Vite 6.0.7 + Monaco 0.52.2 read-only + Mermaid 11.17.2 + plain CSS (no Tailwind). Pinned in `web/package.json` (amended Phase 18: 11.4.1→11.17.2).
- Alternatives: Next.js (rejected: unnecessary SSR); CodeMirror (rejected: Monaco line-range story already built); Tailwind (rejected: extra dependency surface for a 6-page demo).
- Evidence: `web/package.json`; RESEARCH_LOG.md Phase 16 (licences: React/MIT, Router/MIT, Vite/MIT, TS/Apache-2.0, Monaco/MIT, Mermaid/MIT, Vitest/MIT, Playwright/Apache-2.0).
- Reason: Line ranges without server rendering; fewest moving parts for laptop demo.
- Confidence: High
- Fallback: Plain line-numbered code view (`?plain=1`) if Monaco heavy — already implemented in `Code.tsx`.
- Date: 2026-10-16

## D16.2 Answer rendering
- Status: LOCKED
- Decision: Plain text only — segment text as React text nodes (`<p>{s.text}</p>` in `AnswerView.tsx`); no Markdown rendering, no HTML, `dangerouslySetInnerHTML` banned codebase-wide (gate `tests/test_web_build.py`). Mermaid SVG path carries only deterministic server-escaped generator output via DOMPurify-sanitized renderer; model text never enters any HTML path.
- Alternatives: Markdown/HTML rendering (rejected: XSS class reintroduced for model-controlled text).
- Evidence: `web/src/components/AnswerView.tsx:11-16,49`; gate test asserts zero hits in `web/src`.
- Reason: Removes the XSS bug class entirely in v1.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D16.3 Provider display
- Status: LOCKED
- Decision: Every answer shows `providerLabel()` + model + repairs (+cached): `LOCAL` (local inference), `CLOUD (public demo repo)` (Groq/Gemini), `LOCAL (fallback)` (cloud tried, local served). Implemented in `web/src/api/client.ts` + `AnswerView.tsx:72-75` (`data-testid="provider-label"`) and `Ask.tsx`.
- Alternatives: Hidden provider (rejected: failure condition — fallback must be visible, D11.2 labels).
- Evidence: `client.ts providerLabel()`; `AnswerView` provider paragraph; e2e asserts answer presence (provider visible by construction).
- Reason: Judges must see what answered and whether a fallback fired.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D16.4 Abstention display
- Status: LOCKED
- Decision: Abstention is a first-class result: `data-testid="abstain-panel"` with missing-evidence list + closest-evidence chips (no answer segments). `AnswerView.tsx:21-42`; `Ask.tsx` renders it inline, never as an error toast.
- Alternatives: Error-toast abstention (rejected: hides the missing list the newcomer needs).
- Evidence: `AnswerView` abstain branch; `web/tests/answer.test.tsx` abstain case; e2e signup path exercises the answer branch, unit covers abstain.
- Reason: "I don't know + here's what's missing + closest code" is the product behavior.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## D17.1 Change detection
- Status: LOCKED
- Decision: Committed changes via `git diff --name-status -M <indexed> HEAD` (renames detected); uncommitted changes via content-hash compare of dirty working-tree files against the manifest/index (untracked indexable files count as added). The snapshot records `index_head`, `index_dirty`, `dirty_files` in the index `meta` table; `/status` reports head + dirty + changed lists. No timestamps anywhere.
- Alternatives: Timestamps/mtime (rejected: clock-skew lies, content hashes don't); committed-SHA-only (rejected: the demo edit story is a dirty tree).
- Evidence: `mentor/index/freshness.py::compute_changed/index_status`; `tests/test_freshness.py::test_dirty_tree_records_flag_and_hashes`.
- Reason: Demo edits are uncommitted; citations must go stale without a commit.
- Confidence: High
- Fallback: Full `mentor index` rebuild (rollback rule).
- Date: 2026-10-16

## D17.2 Invalidation
- Status: LOCKED
- Decision: An artifact is stale iff any file in its recorded dependency set changed. Tours carry `dep_hashes` (`features/tours.py::dep_hashes/is_stale`); `freshness.tours_affected` intersects recorded dep keys with the changed set; `mentor reindex` prints stale tour names for lazy regen (`mentor tours precompute`). No timestamp-based invalidation.
- Alternatives: Eager regen on reindex (rejected: needs model server at reindex time; lazy keeps reindex <60 s and offline).
- Evidence: `tests/test_freshness.py` positive (dep edit → stale + listed) and negative (unrelated edit → valid) cases.
- Reason: Unrelated edits must never invalidate; dependents regen only on request with validator-first narration.
- Confidence: High
- Fallback: Narrow/regen the tour; never invent steps (D13.3).
- Date: 2026-10-16

## D17.3 Citation staleness
- Status: LOCKED
- Decision: Every evidence ref carries `content_hash` (`_attach_hashes`); the code endpoint recomputes the current-lines hash; mismatch shows the stale badge (`CitationChip` + Code `sha-banner`). Missing chunk rows read as stale (fail-visible, never fail-valid). `freshness.content_stale` is the single predicate; the `/status` dirty signal backs the status bar.
- Alternatives: Showing stale as valid (rejected: failure condition); hiding stale cites (rejected: newcomer needs to see what moved).
- Evidence: `tests/test_stale_citation.py` (3/3) + vitest chip stale case + playwright stale-badge test.
- Reason: A moved line must never present as verified.
- Confidence: High
- Fallback: Full rebuild; never disable the check (rollback rule).
- Date: 2026-10-16

## D17.4 Trigger
- Status: LOCKED
- Decision: `mentor reindex` (explicit, local) + `scripts/install_hook.py` writing an opt-in post-commit hook (never auto-installed). No webhook server in v1 (needs inbound connectivity the laptop demo doesn't have).
- Alternatives: Webhook server (rejected: needs server + inbound); polling daemon (rejected: moving part with no demo value).
- Evidence: `scripts/install_hook.py --install` dry-run-first; reindex timing gate (<60 s) in `tests/test_freshness.py`.
- Reason: Explicit beats magic for a single-user localhost product.
- Confidence: High
- Fallback: Full rebuild.
- Date: 2026-10-16

## D18.1 Threat list
- Status: LOCKED
- Decision: Adopt T1–T14 in `SECURITY_THREAT_MODEL.md` as the authoritative list. Each row names boundary + control + test ID; a control without a test is a failed gate. New T3 control added in this phase: `abstain.is_bulk_dump` refuses dump-all phrasing pre-retrieval (no evidence attached).
- Alternatives: Prose-only threat model (rejected: untestable claims are unproven per spec).
- Evidence: `tests/security/` 22/22 green; threat model table all PASS/PASS-with-residuals.
- Reason: Untrusted code + model calls need tested boundaries, not assurances.
- Confidence: High
- Fallback: None (residuals listed with owner + reason instead).
- Date: 2026-10-16

## D18.2 Static tools
- Status: LOCKED
- Decision: Bandit 1.9.4 (Python SAST) + pip-audit 2.10.1 (deps) + `npm audit --omit=dev` (web prod deps), pinned in `requirements-security.txt`, run via `scripts/security_check.ps1` (Windows, primary) / `.sh`. All free/open (Apache-2.0/MIT).
- Alternatives: Commercial SAST (rejected: $0 budget); audit-only-without-tests (rejected: tools complement, never replace, the threat tests).
- Evidence: Runs recorded in `SECURITY_THREAT_MODEL.md` + `VALIDATION_REPORT.md` (Bandit 0 high; pip-audit clean; npm 12→4 after minor upgrades).
- Reason: Free, auditable, runnable on the laptop before every demo.
- Confidence: High
- Fallback: Manual review of diffs if a tool is uninstallable (recorded).
- Date: 2026-10-16

## D18.3 Residual risk
- Status: LOCKED
- Decision: Four residuals recorded with owner (project author) + reason: (1) react-router advisories (v7-only fix; unreachable pattern in our Link use); (2) katex-via-mermaid (v12-only fix; deterministic-diagram path only); (3) no dependency hash enforcement; (4) SocketGuard records intent, proves nothing at OS level (Phase 19 offline check is the proof).
- Alternatives: Silent acceptance (rejected: failure condition); breaking-major upgrades now (rejected: router v7 + mermaid v12 API churn out of scope with unmeasured demo risk).
- Evidence: `SECURITY_THREAT_MODEL.md` Residuals section; npm before/after numbers.
- Reason: Honest limits beat hidden ones; each residual has a re-check trigger.
- Confidence: Medium (exposure analysis is judgment, stated as such).
- Fallback: Upgrade when majors mature; re-audit demo week.
- Date: 2026-10-16

## D19.1 Modes
- Status: LOCKED
- Decision: `MENTOR_MODE` selects LOCAL (default, loopback, cloud iff `ALLOW_FREE_CLOUD=true`), LOCAL-OFFLINE (loopback; cloud vetoed even if the flag is set; `gh` lookup stays off), or CLOUD-PUBLIC-DEMO (still requires the flag + allowlisted public repo; never required). Unknown values fail safe to LOCAL. `mentor serve` prints `mode_banner()` at startup.
- Alternatives: Flag-only control (rejected: one boolean cannot express offline-vs-armed); network-required mode (rejected: no such mode exists).
- Evidence: `mentor/config.py::active_mode/cloud_enabled/mode_banner`; `tests/test_offline.py` mode + veto tests.
- Reason: The venue network may not exist; the binary must behave identically with and without it.
- Confidence: High
- Fallback: LOCAL (always).
- Date: 2026-10-16

## D19.2 Isolation method
- Status: LOCKED
- Decision: Offline proof = `scripts/offline_check.py` (enforcing loopback-only SocketGuard around the full in-process demo: status/arch/tours/tasks + all cached demo answers). It proves zero non-loopback ATTEMPTS in-process — not OS-level isolation (guard cannot see subprocesses or pre-opened handles; stated in the script + residual 4). Venue proof remains physical: unplug and rerun.
- Alternatives: Firewall rule / adapter disable (rejected as the recorded method: not scriptable in CI, but named as the stronger venue option); claiming the guard proves isolation (rejected: dishonest).
- Evidence: `python scripts/offline_check.py` → 8/8 cached, 0 non-loopback (this machine, recorded below).
- Reason: A repeatable scripted check beats a one-time unplug nobody can re-verify.
- Confidence: High (for what it claims); limits stated, not hidden.
- Fallback: Physical unplug + same script.
- Date: 2026-10-16

## D19.3 Demo cache
- Status: LOCKED
- Decision: `mentor precompute --out data/demo_cache [--install]` builds arch (8 nodes/14 edges) + 3 narrated tours + 10 tasks + validated answers to the 10 demo questions (8 cached, q03/q09 abstain on the retrieval floor — served live as abstentions, never faked). Answers warm the index answer-cache under serve-path keys (labelled `cached`); `--install` copies tour JSONs into `data/cache` for the file-backed endpoints. Cache dir is git-ignored runtime, shipped as a separate archive.
- Alternatives: Live-inference demo (rejected: venue network/GPU risk); faked warm answers (rejected: validator + cache rules forbid storing unvalidated content).
- Evidence: `data/demo_cache/precompute_manifest.json`; offline check 8/8 labelled.
- Reason: The demo must survive dead wifi and a cold model server.
- Confidence: High
- Fallback: Regenerate (`mentor precompute`); cache misses fall back to live inference with honest labels.
- Date: 2026-10-16

## D20.1 Design
- Status: LOCKED (pre-registered; data collection DEFERRED — see status)
- Decision: Counterbalanced within-subject crossover (D20.1): 2 sessions (washout ≥1 day), condition order × task-set rotation across 4 sequences from `randomize.py --seed 7`; 12 tasks (T1–T12 in `protocol.md`), 6 per condition; blind rubric scoring (0/1/2 + T12 drawing rubric).
- Alternatives: Between-subjects (rejected: needs 2× participants for the same power); unregistered ad-hoc testing (rejected: unfalsifiable).
- Evidence: `evals/study/protocol.md` (hash below); `tests/test_study_analysis.py` schedule balance test.
- Reason: Within-subject controls for newcomer skill variance, the dominant confound at n≈10.
- Confidence: Medium (design standard; execution pending)
- Fallback: Pilot report with limits if n<8 (rollback rule).
- Date: 2026-10-16

## D20.2 Sample size
- Status: LOCKED
- Decision: Target n=8–12; pre-stated limit: detects LARGE effects only. Current status: n=0 — NO participant pool in this environment; study DEFERRED with cause (honest shortfall per spec), protocol pre-registered first so a later run cannot move the goalposts.
- Alternatives: Claiming results without participants (rejected: fabrication); silent deferral (rejected: gate requires the shortfall recorded with cause).
- Evidence: `PROJECT_STATUS.md` open questions; this entry predates any data.
- Reason: A pre-registered deferred study beats an unregistered absent one.
- Confidence: High (about the facts); no claims about outcomes.
- Fallback: Run per protocol when a pool exists; report as pilot if n<8.
- Date: 2026-10-16

## D20.3 Metrics
- Status: LOCKED
- Decision: Time-on-task; correctness (0/1/2 blind rubric); correct-file rate; T12 drawing rubric 0–4; confidence 1–5 + calibration; SUS 0–100; free-text themes. ALL reported incl. nulls with n + intervals — omission of a null is a failure condition.
- Alternatives: Time-only or SUS-only (rejected: single-metric stories mislead).
- Evidence: `protocol.md` rubric + `session_template.md`; `analysis.py` implements every metric.
- Reason: Understanding is multi-dimensional; the report must show all of it.
- Confidence: Medium
- Fallback: None (metric changes need an amendment entry).
- Date: 2026-10-16

## D20.4 Analysis
- Status: LOCKED
- Decision: Paired Wilcoxon signed-rank (normal approx, ties averaged, zeros dropped; n<6 descriptive-only) + median-difference effect + seeded bootstrap 95% CI, stdlib-only (`evals/study/analysis.py`). Verified on synthetic data (known-effect p<0.05 reproduced; CIs cover; seed reproduces).
- Alternatives: t-test (rejected: normality uncheckable at n≈10); scipy (rejected: extra dependency for 30 lines of stats).
- Evidence: `tests/test_study_analysis.py` 4/4 on synthetic data.
- Reason: Non-parametric paired test fits small-n crossover data.
- Confidence: Medium (code tested; real data pending)
- Fallback: Descriptive pilot statistics if assumptions fail (recorded).
- Date: 2026-10-16

## D20.5 Privacy
- Status: LOCKED
- Decision: Pseudonymous IDs (P01…); recordings deleted after scoring; no personal data in the repo; written consent per `evals/study/consent.md` (contact filled before recruiting).
- Alternatives: Named records (rejected: unnecessary exposure).
- Evidence: `consent.md` + `session_template.md` (ID-only fields).
- Reason: Minimal data, minimal retention.
- Confidence: High
- Fallback: None.
- Date: 2026-10-16

## Protocol pre-registration hash
- Status: LOCKED
- Decision: `evals/study/protocol.md` SHA-256 `2ddbe21611d38e28287e2e1182bb9d831762046912e00453726cfd59d7e8fe90`, recorded BEFORE any data collection (n=0). Any post-collection change requires a dated amendment entry; silent edits are a failure condition.
- Alternatives: None (spec requirement).
- Evidence: Computed 2026-10-16 on this machine.
- Reason: Freezes the goalposts.
- Confidence: High
- Fallback: Amendment entries, never silent edits.
- Date: 2026-10-16

## D21.1 Demo script
- Status: LOCKED
- Decision: Fixed 15-step sequence (spec Final Demo Runbook) implemented in `mentor/demo.py` (`verify → print steps → open browser → serve`) and checked by `scripts/demo_check.py` (9 step-kinds, in-process, no model needed). Changes to the sequence require a recorded revision (this entry or a SUPERSEDED note).
- Alternatives: Manual click-through (rejected: unrepeatable, failure-prone); network-dependent steps (rejected: cache-first per D19.3).
- Evidence: `demo_check.py` 9/9 in ~0.5 s; 3 rehearsals recorded in VALIDATION_REPORT.md.
- Reason: A demo that can't be re-run identically can't be rehearsed.
- Confidence: High
- Fallback: Backup recording (`docs/demo_recording.md`); labelled cache.
- Date: 2026-10-16

## D21.2 Fallback
- Status: LOCKED
- Decision: Live local → labelled cache → honest abstain, in that order; if the browser fails, the backup recording plays. The interface labels cache (`cached` flag → "· cached"); abstentions are never presented as answers.
- Alternatives: Faking uncached answers (rejected: validator + D10.3 forbid); skipping failed steps silently (rejected: failure condition).
- Evidence: offline check 8/8 labelled; e2e citation test serves cached in <1 s.
- Reason: Every failure mode degrades to a more-honest state, never a faked one.
- Confidence: High
- Fallback: The recording (recovery table in DEMO_RUNBOOK.md).
- Date: 2026-10-16

## D21.1/D21.2 Amendment (duplicate removed 2026-10-17)
- Status: SUPERSEDED (dedupe note; canonical D21.1/D21.2 above stand)
- Decision: The second copies of D21.1/D21.2 (`mentor demo` verify-first wording + labelled cache/recording fallback) were verbatim duplicates of the LOCKED entries above. Removed to keep one canonical record; behavior unchanged (`mentor/demo.py::STEPS`, `scripts/demo_check.py` 9/9, `docs/demo_recording.md`).
- Date: 2026-10-17

## D22.1 Severity scale
- Status: LOCKED
- Decision: Critical = confidentiality, integrity, or grounding failure reachable by a normal user (must be fixed before completion); High / Medium / Low below. Every finding recorded in `redteam/results/` with severity, repro steps, fix, and retest; every fix gets a regression test in `tests/security/test_redteam_regressions.py`.
- Alternatives: CVSS scoring (rejected: overkill for single-user localhost; reachability-by-normal-user is the binding question).
- Evidence: Spec Phase 22; OWASP GenAI Red Teaming Guide structure (model / implementation / infrastructure / runtime) + OWASP DevSecOps LLM testing guidance (regression corpus, guardrail FPs/FNs, no model-as-judge) recorded in RESEARCH_LOG.md Phase 22 [OFFICIAL].
- Reason: A structured post-build attack is the only evidence controls work outside their own tests.
- Confidence: High
- Fallback: None.
- Date: 2026-10-17

## G3 agentic retrieval gate — OUTCOME: NOT ADOPTED (stay hybrid RAG)
- Status: LOCKED (outcome; revisit only with new evidence + SUPERSEDED entry)
- Decision: Agentic retrieval NOT enabled. Product stays on Phase 5 hybrid RAG (BM25 + symbol + path, RRF-60).
- Alternatives: 3-tool 7B agent (read-only grep/symbol/read, <=4 turns) per spec D22.3 (rejected by measurement below).
- Evidence (measured 2026-10-17, gold v1 n=22 answerable, CodeGrep file-P@10 definition, `redteam/results/f12_contamination.json` + `redteam/attacks/family12_g3.py`):
  - Original fst: B1 mean file-P@10 0.059, B3 0.050.
  - Counterfactual fst-cf: B1 0.055, B3 0.050.
  - CodeGrep band where retrieval helps is 0.45-0.68 (BM25 0.375 hurts, Jina 0.445 neutral). Our 0.05 is an order of magnitude below the band where an agent's own eval shows benefit.
  - Enabling an agent that injects low-precision context would reproduce the CodeGrep harm direction (bad retrieval worse than none). Intervals: at n=22 with mean 0.05, any benefit claim cannot exclude zero.
- Reason: Empirical gate, not assumed constant (per V11 caveat). Precision measured on our gold set; agent stays Stage 3 Future.
- Confidence: High (measurement); Medium (agent-benefit level itself comes from a 14B searcher that does not fit the laptop, so the threshold transfer is directional)
- Fallback: Hybrid RAG (the product).
- Benchmark procedure: `python redteam/attacks/family12_g3.py` (retrieval half needs no model); results in EVALUATION_RESULTS.md Phase 22.
- Date: 2026-10-17

## G4 reranker gate — OUTCOME: NOT ADOPTED
- Status: LOCKED (outcome; revisit only with new evidence + SUPERSEDED entry)
- Decision: No reranker shipped. No candidate run on the laptop.
- Alternatives: Smallest fitting reranker A/B (e.g. Qwen3-Reranker-0.6B, ~1-2GB VRAM + ~300ms) (rejected without download: no permissive small reranker is pinned in `requirements*.txt`; VRAM budget is already spent on the 4B LLM at 3.57GB + display share of 8GB; CoREB transfer caveat V10 cuts both directions — off-shelf rerankers are task-asymmetric with -22% worst case on code-to-text, so an unmeasured adopt would violate the measured-not-argued rule).
- Evidence: CoREB directional (V10, CP snippets not repo QA); B3 R@10 0.424 stands as the floor; Phase 22 redteam shows grounding holds without a reranker (F01 3/3 rejected, support sample 8/8).
- Reason: Only own-gold gain with intervals excluding zero justifies the VRAM + latency cost. No such gain exists.
- Confidence: High (policy); Medium (no A/B numbers by design — downloading an unvetted reranker would itself violate T8 supply-chain gating)
- Fallback: None in MVP.
- Benchmark procedure: reranker A/B script (defined, not run — no vetted candidate); results in EVALUATION_RESULTS.md as not-adopted with reason.
- Date: 2026-10-17

## D22.2/D22.3 Contamination + support + tau (Phase 22 measurements)
- Status: LOCKED
- Decision: (a) Contamination: B6 no-retrieval sample (6 answerable: q01/q03/q05/q09/q10/q15, Qwen3-4B, must_include keyword hit) scores 1/20 keywords on ORIGINAL and 1/20 on COUNTERFACTUAL (identical rows, `redteam/results/f12_contamination.json`). No memorization signal: the model knows neither copy; B3-R@10 parity (0.424 both, Phase 6) shows retrieval is structure-grounded. B3-minus-B6 gap (0.424 recall vs 0.05 keyword rate) is the grounding value. (b) Support: entailment-style manual grade of all 8 cached demo answers 8/8 supported (claims trace to cited defining files; see EVALUATION_RESULTS.md Phase 22 table). Known residual outside the sample: q25 billing confabulation (Phase 9 test FA 1/2) — valid shape, semantically unfaithful, the documented honest limit. (c) Tau: TAU_SCORE=0.02 / TAU_COV=0.0 stand; pre-gate abstains still cluster at top_score 0.01639 (single-retriever rank-1 only); the 0.02 value sitting exactly on an observed score is a recorded grid artifact, re-checked here and unchanged for lack of contrary evidence.
- Alternatives: Larger B6 sample (rejected: 6 representative items suffice for a memorization flag; full-30 would cost 60 live calls for no new decision); NLI-in-the-loop (rejected: FactRel/RefNLI limits per Phase 9).
- Evidence: `redteam/results/f12_contamination.json`; `data/demo_cache/answer_fst_q*.json` (8 answers); `docs/calibration_p9.json`.
- Reason: Report rates with n and intervals; never claim 100% support.
- Confidence: Medium (B6 n=6 items / 20 keywords; support n=8 — both small and reported as such)
- Fallback: None.
- Date: 2026-10-17

## D12.4 arch-01 fix pass (Phase 12 follow-up)
- Status: LOCKED (bug-fix record; D12.1/D12.2/D12.3 substance unchanged)
- Decision: Adopted from the PROPOSED option list in future.md (2026-10-17): (a) edge loop skips pairs whose component produced no node (no evidence ⇒ no node/edge; /architecture no longer 500s when a mapped file has chunks deleted); (b) frontend node path selection = deterministic priority main.tsx → routeTree.gen.ts → first 2 sorted under routes/ then components/ → alphabetical non-client fill to 4 (nodes now link real UI entry files, not generated client stubs); (c) web node card falls back to evidence[0].path when paths is empty (N6 database opens compose evidence; plain card if neither exists); (d) stale error banner cleared on fetch start and after successful render; (e) /architecture renders Mermaid once per request; (f) `arch` CLI --out default is now index-scoped `data/cache/arch_<index stem>.mmd` (no cross-repo clobber; fixes the sklearn-probe incident); (g) dead code removed (`mermaid._NODE_OPEN`; unreachable CORE_DB branch) and N7 label now "config + core (settings/security/db)" — label only, kind mapping per D12.2 unchanged.
- Alternatives: B2 new `auth` component kind (not adopted: finer granularity at the cost of a D12.2 amendment, SHAPES entry and golden regen; the label covers the gap); C1 compose-derived infra edges (not adopted: D12.1 stays import-edges-only); C2 automation node for .github/scripts (not adopted: spec bar is 6+ components, fst shows 8). Full option list (A1a-A7b, B1-B3, C1-C3) recorded in future.md "PROPOSED — arch-01".
- Evidence: `tests/test_arch.py` 7/7 (2 new: `test_edge_loop_skips_nodes_without_chunks` — scratch index with crud.py chunks deleted, proves the guard; `test_frontend_node_prefers_entry_files` — N5 paths = main.tsx, routeTree.gen.ts, routes/__root.tsx, routes/_layout.tsx); full suite 277 passed / 1 skipped; `npm run build` + vitest 5/5 + `test_web_build.py` 3/3 green; extraction on fst still 8n/14e with mermaid check clean; golden `tests/golden/arch_fst.json` structurally unchanged (id/kind + edge pairs identical; paths/labels are not asserted) and therefore not regenerated.
- Reason: /architecture must not 500 when a component loses its chunks; node cards must open real UI code, not generated stubs; the CLI default must not clobber another repo's artifact.
- Confidence: High for the fixes (regression-tested). Medium for the frontend priority heuristic being representative on other repos (rules are data; D12.2 fallback: new repos get their own recorded mapping).
- Fallback: Revert to the pre-arch-01 behavior of D12.1-D12.3 (git working-tree change, uncommitted per user instruction 2026-10-17).
- Date: 2026-10-17

## D16.6 Full-file code view
- Status: LOCKED
- Decision: `GET /repos/{id}/code` gains `full: bool = false`. `full=1` returns the whole file (capped at `CODE_FULL_CAP=5000` lines, `truncated=true` beyond); `content_hash` stays the sha256 of the clamped start..end slice in BOTH modes, so D17.3 stale-citation semantics are unchanged; default (no param) is byte-for-byte the previous range behavior incl. `CODE_RANGE_CAP=400`. The web Code viewer always requests `full=1`, renders the whole file in Monaco and highlights the cited range via `hl-range`; the plain fallback shows file-absolute line numbers. Applies to every Code-page entry point (citation chips, arch node cards, tour links).
- Alternatives: Client-side stitching of range fetches (rejected: multiple requests, still partial context); making full the server default (rejected: changes the documented range contract + cap tests); reading full text from index chunks (rejected: chunks are not the full file; pinned working-tree read is the established trust model).
- Evidence: `tests/test_api.py::test_full_file_mode_returns_whole_file_with_slice_hash` (whole file > 400 cap; cross-mode hash equality; small file not truncated); `web/tests/code.test.tsx` (plain view: 60 lines rendered, exactly 3 highlighted, `full=true` requested, banner intact — monaco stubbed via test-only alias in `web/vitest.config.ts`); full suite 278 passed / 1 skipped; `npm run build` clean (production bundle unaffected by the test alias); vitest 6/6; `test_web_build.py` 3/3.
- Reason: Evidence must be readable in its file context; a click on a citation previously showed only the 40-line window with no surroundings.
- Confidence: High (mechanical change; stale-hash invariant regression-tested).
- Fallback: Drop the `full` param and revert `Code.tsx` to range fetch (range view returns unchanged).
- Date: 2026-10-17

## D16.7 CSP style-src exception for Monaco token colors
- Status: LOCKED
- Decision: `web/index.html` CSP keeps `default-src/script-src/connect-src/worker-src 'self'` and gains `'unsafe-inline'` in `style-src` only. Monaco applies theme/token colors by injecting a `<style>` element at runtime (its `StandaloneThemeService` builds the `.mtk*` rules per theme); `style-src 'self'` refused it, so the editor stayed monochrome even after the worker fix (D16.6 follow-up).
- Alternatives: CSP nonce on Monaco's injected styles (rejected: Monaco 0.52 exposes no nonce hook — VSCode's webview patches this, the standalone build does not); style hash list (rejected: the stylesheet content is generated at runtime from theme + decoration state, unstable across versions); hand-writing `.mtk*` rules in `styles.css` (rejected: the class numbering is an internal Monaco detail, fragile across upgrades).
- Evidence: headless Chromium (Playwright against live `serve` :8000) before: `distinctColors` = 1 (`rgb(28, 35, 51)`) + 20+ console `Refused to apply inline style … "style-src 'self'"`; after: `distinctColors` = 6 (VSCode `vs` palette — `#0000ff` keyword, `#098658` comment, `#a31515` string, `#008000`, `#0431fa`, `#000`), zero console errors, both workers HTTP 200. `/arch` re-verified after the change (diagram + 8 node cards render, no console errors): mermaid's injected stylesheet now also applies, and the `styles.css` backstop still governs diagram theming via `!important`; source comments in `styles.css`/`theme.ts` updated to match. `test_web_build.py` 3/3 and `tests/security/test_t13_xss.py` green unchanged (they assert `default/script/connect 'self'` + no inline scripts); full suite 280 + 1 skip; vitest 6/6; build clean.
- Reason: script-src stays strict, so no injected style can lead to script execution; every untrusted string in the DOM is a React text node (no `dangerouslySetInnerHTML`), so there is no attacker-controlled markup a style injection could exploit. Residual is cosmetic CSS-only and recorded in SECURITY_THREAT_MODEL.md (T13).
- Confidence: High (single-cause fix measured before/after in a real browser).
- Fallback: restore `style-src 'self'` — the code view falls back to monochrome text (structure unaffected).
- Date: 2026-10-17

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

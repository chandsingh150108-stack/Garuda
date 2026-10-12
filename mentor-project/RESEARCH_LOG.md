# RESEARCH_LOG

Verification ledger copied from CODEBASE_MENTOR_EXECUTABLE.md v1.0 (Oct 2026). Status as of this pass.

| # | Claim | Status | Evidence | Consequence |
|---|---|---|---|---|
| V1 | RTX 5060 Laptop 8GB GDDR7 128-bit | VERIFIED | Notebookcheck Apr 2025, NVIDIA announcement | 8GB hard ceiling |
| V2 | 3,328 CUDA, 45-100W TGP, 384GB/s; aggregators conflict (3,840 cores/448GB/s/115W = desktop) | VERIFIED launch specs; CONFLICT in aggregators | Notebookcheck specs table | Phase 0 must read real device with nvidia-smi; machine TGP/VRAM override spec sheet |
| V3 | Groq free tier gpt-oss-120b: 30RPM/1000RPD/8K TPM/200K TPD, per-model per-org | VERIFIED via secondary repro Sep 2026 | Aggregators quoting console.groq.com/docs/rate-limits | Live check required before demo |
| V4 | Groq model qwen3.8-27b 1000RPD | UNVERIFIED, suspicious name, single source | Single aggregator | Do not hardcode; read live model list Phase 11 |
| V5 | Gemini free 15RPM/10K RPD/1M TPD Flash-class | UNVERIFIED likely STALE; per-project console now | Google rate-limits page | Remove numbers; read console Phase 11 |
| V6 | Gemini free prompts may train Google products | VERIFIED | Google pricing page free-tier column | Gemini forbidden for private code |
| V7 | OpenRouter :free 20RPM/50RPD (1K/day after $10) | VERIFIED two sources | 2026 audits | Emergency reserve only |
| V8 | Cerebras free = card-gated trial | CONFLICTING (some claim 1M/day free) | Mixed | Excluded either way |
| V9 | GitHub Models retired 30 Jul 2026 | UNVERIFIED single report | Report only | Excluded either way |
| V10 | CoREB arXiv 2605.04615: rerankers not net-positive; keyword collapse | VERIFIED paper exists/says this | arXiv abstract | Limits: LiveCodeBench CP problems, self-reported; fine-tuned reranker only consistent gainer; directional hint only |
| V11 | CodeGrep arXiv 2608.05886: precision band 0.45-0.68 | VERIFIED exists; WEAKLY SUPPORTED for us | Abstract+tables | 3 retrievers, SWE-Bench Verified, 14B searcher (no laptop fit); band is 3-point observation; Phase 5 measures own precision |
| V12 | cAST EMNLP25 arXiv 2506.15655: +4.3 Recall@5 RepoEval, +2.67 Pass@1 SWE-bench | VERIFIED correct | ACL Anthology, arXiv v2 | Adopt AST chunking |
| V13 | bge-m3 568M/1024d/8K MIT | VERIFIED in report, not re-fetched | FlagEmbedding repo | Fallback candidate |
| V14 | jina-embeddings-v2-base-code 161M/768d/8K Apache-2.0 | PARTIALLY VERIFIED; license check Phase 7 | Report | Candidate pending card check |
| V15 | jina-code-embeddings 0.5B/1.5B exist (Qwen2.5-Coder bases) | VERIFIED exist; converter card says CC-BY-NC-4.0 non-commercial | Jina pages + HF converter card | Report jina-code Apache refers to old v2; newer = non-commercial until source card says otherwise |
| V16 | Qwen2.5-Coder-7B Apache-2.0/128K/28 layers/GQA 4KV | VERIFIED | Model docs + spec sheets | Enables KV arithmetic Phase 8 |
| V17 | Qwen2.5-Coder-14B Q4 9.9GB/12GB coder | CORRECTED: GGUF Q4_K_M ~8.4-9GB | Community GGUF files | Still >8GB; conclusion holds, number was wrong |
| V18 | Ollama format JSON schema since 0.5.0 | VERIFIED, adherence not guaranteed; Qwen3.x issue Apr 2026 | Ollama docs + issues | Server validator + repair mandatory |
| V19 | fastapi/full-stack-fastapi-template MIT ~43.5K stars Jun 2026 (report said 45K) | VERIFIED | GitHub + snapshot | Primary demo candidate; high contamination risk (Phase 2) |
| V20 | Claude Sonnet 5 $2/$10 1M ctx | UNVERIFIED possibly outdated (5.5 lineup) | Report only | Paid path excluded; no change |
| V21 | Qdrant vs pgvector 9ms vs 51ms; 290MB vs 1.1GB | UNVERIFIED third-party blog | Blogs | Decision no longer depends on them (C1) |
| V22 | Sourcegraph dropped embeddings; Claude Code grep-first; WarpGrep numbers | NOT RE-VERIFIED; OBSERVED PRACTICE w/ caution | Company blogs | Directional support only |

Local probe 2026-10-08 (dev machine, NOT target): RTX 4050 Laptop 6GB, driver 581.57, Python 3.14.0, Node v24.19.0, Ollama client 0.34.0 (no daemon). Target RTX 5060 8GB probe pending. [INFERENCE: dev != target, Phase 8 must re-measure]

## Phase 2 research (2026-10-11, on target laptop)
- Target hardware (this machine): RTX 5060 Laptop GPU, 8151 MiB total / 7899 free, driver 610.74, power.max 100W (limit N/A). Confirms V1/V2 8GB ceiling; TGP max at top of 45-100W range. Python 3.14.0 (spec wants 3.12, deviation stands per D0.2); disk free 22.8GB (<30GB precondition, recorded risk); ollama/node not on PATH (not needed Phase 2). [OFFICIAL: nvidia-smi]
- Primary repo layout (pinned SHA `7257e60`, master): `backend/app/{api/routes/{users,login,items,private,utils},core/crud/models}`, `frontend/` (React+TS+Vite), `compose.yml`, `LICENSE`=MIT. Backend serves frontend from `app.frontend/`. API prefix `settings.API_V1_STR` (default `/api/v1`, confirm Phase 3). [OFFICIAL: repo itself]
- Signup route (code-read, not assumed): `backend/app/api/routes/users.py:146-147` `@router.post("/signup") def register_user`, router `prefix="/users"` (:29), `api_router` adds no prefix, app mounts at `API_V1_STR`. Full path `{API_V1_STR}/users/signup`. Related: `POST /users/` superuser-only (:54-57), `POST /private/users/` (private.py:23-24), login `POST /login/access-token` (login.py). [OFFICIAL: repo code]
- Candidate rubric (licences via GitHub API licence field + READMEs; counts local for primary only): FST MIT/152 files/flows/tests PASS + template-copy HIGH; Conduit-FastAPI licence NULL (blocked); Mealie AGPL-3.0 (non-permissive, large); PetClinic Apache-2.0 but Java-only; Express-Conduit licence NULL. Conclusion: secondary GATED, ask human on licence. [OFFICIAL: GitHub API + repo pages]
- Scanner tuning: unquoted `password=` matching FP'd on kwarg passing (`password=user_in.password`, `data["password"]`, `randomPassword()`) and excluded 14 source files incl. signup handler; narrowed to quoted literals -> 0 secret exclusions, canary still caught, manifest scanner-clean. [ENGINEERING JUDGMENT + measurement]

## Phase 3 research (2026-10-11/12)
- Toolchain (installed + probed live): `tree-sitter==0.25.2` runtime (MIT classifier), `tree-sitter-python==0.25.0` (MIT), `tree-sitter-typescript==0.23.2` (MIT, covers `typescript`+`tsx`), `PyYAML==6.0.3` (MIT). API: `Parser(Language(...))`, 0-based rows (line=row+1), `child_by_field_name`. Probed node shapes for imports/decorators/class-kwargs/TS-imports/exports/calls before writing extractors. [OFFICIAL: package METADATA + live probes]
- Routes (code-read): `@router.<method>("<path>")` decorators; `APIRouter(prefix="...")` literals same-file; `include_router` without literal prefix at api level; app mounts at dynamic `settings.API_V1_STR`. [OFFICIAL: repo code]
- Models: `class User(UserBase, table=True)` / `class Item(ItemBase, table=True)`, no `__tablename__` (table inferred = lowercase, per code comment). [OFFICIAL: models.py]
- Config layout (actual, differs from spec names): root `compose.yml` (+`compose.deploy.yml`, `compose.override.yml`) — not `docker-compose.yml`; no `.env.example`; `backend/pyproject.toml`, `frontend/package.json` (+root copies). Env in compose is list-form (`KEY=val`) and dict-form. [OFFICIAL: repo tree]
- RUNTIME DOWNGRADE finding: `tree-sitter==0.26.0` segfaults natively (0xC0000005 in python314.dll, Windows Event 1000) — `test_users.py` whole-file extract died ~12/12 (in-process + workers, hang-or-crash) while all parts parsed; identical fragment passed 3/5 and crashed 2/5 (proven non-determinism). 0.25.2 extracts both killer files 4/4; full CLI 152/152. Contributor: brand-new CPython 3.14.0 + 0.26.0 binding. [INFERENCE from measurement; recorded as D3.1 amendment]
- cAST principle (structure-aware units) retained from V12; extractors store exact ranges for Phase 4 chunking. [PRIMARY RESEARCH, V12]

## Phase 4 research (2026-10-12)
- FTS5 verified live on SQLite 3.50.4: `CREATE VIRTUAL TABLE ... USING fts5(chunk_id UNINDEXED, header, identifiers, text, tokenize='unicode61')`, `MATCH`, `bm25()`, column filters all work. Standalone (non-content-sync) FTS table chosen: explicit delete/insert per file keeps freshness (Phase 17) simple, no trigger pitfalls. [OFFICIAL: sqlite.org/fts5 + live probe]
- Token counting: chars//4 approximation (recorded D4.1). Identifier splitting: separators + camel/acronym/digit boundaries, original+parts indexed.
- Line-window budget fix (own measurement): fixed 80-line windows of long lines blew past 512 tokens (64 violations on .md/.yml). Windows now greedy-bounded by lines AND budget; single over-budget line = recorded exception. Final: max non-exception 512, 4 exceptions (email HTML minified lines, index.ts:4). [ENGINEERING JUDGMENT + measurement]
- Duplicate-span root cause (own logic): same-line AST children re-emitted their shared line once per descendant (index.ts: 130 identical spans -> UNIQUE violation). Single-line spans are atomic (line-granular model can't split columns); identical ranges deduped. [ENGINEERING JUDGMENT + measurement]

## Phase 5 research (2026-10-12)
- RRF formula + k=60 confirmed in the PRIMARY paper (Cormack/Clarke/Büttcher SIGIR 2009, cormack.uwaterloo.ca PDF): score(d) = Σ 1/(k+r(d)), k fixed in pilot, unaltered in validation, near-optimal but not critical. [PRIMARY RESEARCH]
- CodeGrep abstract verified live (arXiv 2608.05886, 6 Aug 2026): precision threshold BM25 0.375 (hurts) / Jina 0.445 (neutral) / CodeGrep 0.677 (helps) on SWE-Bench Verified; 14B searcher (no laptop fit, per V11). Operational file-P@10 defined for G3 on our gold set. [PRIMARY RESEARCH]
- Shell-quoting lesson: PowerShell backtick-escaping mangled a demo query (different analysis, different results) — implementation verified correct via single-quoted rerun + direct-API debug. Tests call `search()` directly, immune. [ENGINEERING JUDGMENT]

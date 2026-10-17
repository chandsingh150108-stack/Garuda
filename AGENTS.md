# AGENTS.md — Codebase Mentor repo guide

Read this file top to bottom before changing anything. It is the map; the docs listed in §9 hold the evidence.

## 0. What this repo is

**Codebase Mentor** — a local-first, $0-cost AI mentor that indexes ONE real open-source repo at a
pinned commit and answers newcomer questions with exact `file:line` citations, or **abstains** when
the code doesn't contain the answer. Not "ChatGPT over files": facts come from a deterministic
index, language comes from a small local LLM, trust comes from a deterministic validator.

- Spec (authoritative, wins on conflict): `CODEBASE_MENTOR_EXECUTABLE.md` (23 phases, A–L acceptance criteria)
- Research background: `Codebase Mentor Reassessment Report.md`
- Working project root: `mentor-project/` (PROJECT_ROOT for all phase work)
- Status: **Phase 22 PASSED 2026-10-17; project complete, pending final-acceptance review** (see `mentor-project/PROJECT_STATUS.md`)
- Primary repo: fastapi/full-stack-fastapi-template @ `7257e606cb94eada1dca40173e2b7f99dd549bc6` (constant `PINNED_SHA`, duplicated as a string literal in ~20 files — no shared constant)
- Secondary probe repo: scikit-learn@85593ca (BSD-3), under gitignored `mentor-project/data/repos/sklearn`

## 1. Repo layout

```
AGENTS.md, opencode.json                 <- workspace root (this level)
CODEBASE_MENTOR_EXECUTABLE.md            <- spec v1.0
Codebase Mentor Reassessment Report.md   <- research report
mentor-project/                          <- PROJECT_ROOT
  DECISIONS.md, PROJECT_STATUS.md, VALIDATION_REPORT.md, EVALUATION_RESULTS.md,
  RESEARCH_LOG.md, SECURITY_THREAT_MODEL.md, DEMO_RUNBOOK.md, PROJECT_BRIEF.md,
  README.md, future.md, sessions.md      <- control files (update per Global Rules)
  docs/ARCHITECTURE.md, bench/calibration JSON artifacts
  mentor/                                <- Python package (the product)
    config.py cli.py demo.py
    ingest/ index/ parse/ retrieve/      <- pipeline stages 1-4
    answer/ llm/                         <- stages 5-6 (contract/validator/gateway)
    features/ eval/                      <- arch, tours, why, tasks, precompute; gold/harness/metrics
    api/                                 <- FastAPI (loopback-only)
  tests/                                 <- 41 pytest files + tests/security/ (T1-T14) + golden/ fixtures
  evals/ gold/*.yaml tours/*.yaml study/ <- frozen 30-Q gold set, tour seeds, user-study protocol
  redteam/ PLAN.md attacks/ results/     <- 13 attack families + recorded results
  scripts/                               <- probe/bench/calibrate/demo/security_check scripts
  web/                                   <- React+TS+Vite UI (src/, e2e/, tests/); dist/ gitignored
  data/                                  <- ALL runtime artifacts (gitignored): repos/, indexes/,
                                            manifests/, parses/, cache/, demo_cache/, models/
```

`data/` is gitignored and must never be committed (Global Rule 8). `.venv/` lives in `mentor-project/`.

## 2. Pipeline (how a question gets answered)

```
Repo@SHA (untrusted, never executed)
 -> INGEST   mentor/ingest: acquire(SHA check) -> filters (allowlist exts, no symlink/submodule
            follow, 1MB cap, .env/keys excluded) -> regex secret scan (hash-only) -> manifest JSON
 -> PARSE    mentor/parse: tree-sitter Py/TS/TSX in isolated child procs (10s timeout, 1MB cap)
            -> symbols/imports/routes/models/config -> edges (resolved | likely by-name)
 -> INDEX    mentor/index: one SQLite+FTS5 file per repo. AST split-then-merge chunks (~512 tok),
            text (cited) stored apart from embed_text. Deterministic: no wall-clock, byte-comparable.
            index/freshness.py = incremental reindex (git diff + content hashes)
 -> RETRIEVE mentor/retrieve: analyze query -> FTS5 BM25 + exact/prefix symbol + path match
            -> RRF-60 fusion -> confidence {top_score, identifier_coverage, 2-retriever_agreement}
            (dense retrieval REJECTED at gate G1; no reranker — G4 not adopted)
 -> EVIDENCE mentor/answer/evidence.py: E1..En server-numbered, line-numbered, <=3000 tok,
            read from the INDEX (never the working tree)
 -> GATE     abstain.pre_gate: top_score < 0.02 -> abstain with NO model call. Bulk-dump questions
            refused BEFORE retrieval (T3).
 -> GATEWAY  mentor/llm: local llama.cpp 127.0.0.1:8080 (Qwen3-4B-Instruct Q4_K_M, temp 0) default;
            cloud Groq -> Gemini -> local behind a 6-condition gate (ALLOW_FREE_CLOUD=false default,
            LOCAL-OFFLINE vetoes, public-repo allowlist, manifest clean, redacted, 90%-budget stop)
 -> VALIDATE answer/validator V1-V9 + exactly ONE repair (always local) else ABSTAIN.
            Never loosen validation to pass.
 -> SERVE    api/routes.py: cache-first (validated answers only, never abstentions),
            _attach_hashes (stale detection), hash-only audit row
```

Data-flow siblings: **architecture** (deterministic from imports/routes → Mermaid generated by
`features/mermaid.py`, never by the LLM), **tours** (BFS from human-authored route seeds, hops
labelled resolved vs likely), **why** (git blame/log → H-blocks; causal claims need an H citation
or `kind=inference` — validator V9), **tasks** (4 offline signals → scored → validated → served),
**freshness** (content-hash stale badges, `<60s` reindex).

## 3. Non-negotiable invariants (enforced by tests)

1. **Local-first:** default NOTHING leaves the laptop. Loopback-only egress (`llm/egress.py`),
   loopback-only bind (`api/app.py`), `ALLOW_FREE_CLOUD=false`, cloud gate fail-closed.
   Tests: `test_egress`, `test_cloud_gating`, `test_offline`, `test_no_keys`, SocketGuard in `tests/socket_guard.py`.
2. **Never execute repo content:** no `shell=True`, no `eval`/`pickle`, parameterized SQL only,
   argv-list subprocess with timeouts. Verified by AST scans: `tests/security/test_t12_no_shell.py`,
   `test_t14_deserialization.py`.
3. **Model never writes paths/lines** — it emits evidence IDs; server expands ranges.
   Validator rules V1–V9 (`mentor/answer/validator.py`) are the enforcement layer for prompt
   injection (delimiting in the prompt only reduces it).
4. **Secrets:** values never stored/logged/sent — only sha256 line hashes. Redaction reuses the
   ingest scanner patterns before any cloud egress.
5. **Abstentions are never cached.** Cache key binds `repo_id + sha + INDEX_SCHEMA_VERSION +
   question + provider + model + prompt_version + k`.
6. **Pinned SHA everywhere.** Citations without a pinned commit are a failure condition.
7. **Determinism:** no timestamps in index artifacts; ties broken by stable sorts; gold sets frozen
   (sha256 recorded in DECISIONS.md; asserted in `test_gold.py`).
8. **Honest claims only** (Global Rule 11): every number must be measured and recorded in
   `EVALUATION_RESULTS.md` with n + Wilson CI. Never claim 100% semantic support — only citation
   validity by construction.

## 4. Module map (dependency direction: api/cli → answer → {retrieve, llm, index})

| Module | Key entry points | Notes |
|---|---|---|
| `mentor/config.py` | `active_mode()`, `cloud_enabled()`, `mode_banner()` | ALL tunables live here as constants, not env sprawl |
| `mentor/cli.py` | `python -m mentor.cli <index\|search\|ask\|serve\|arch\|tours\|tasks\|reindex\|precompute\|eval\|demo>` | CWD must be `mentor-project/` (paths are CWD-relative literals) |
| `mentor/demo.py` | `verify()` then `run()` — pre-browser index+cache check | returns 2 on verify failure |
| `answer/qa.py` | `ask(db, sha, query, ...)` — THE orchestrator | retrieve → gate → evidence → gateway → validate → 1 repair → answer/abstain |
| `answer/contract.py` | `Segment`, `Answer`, `ANSWER_SCHEMA` | shared by prompt, validator, cache, API |
| `answer/validator.py` | `validate(output, blocks) -> list[VError]` | V1 schema … V8 no `path:line`, V9 causal-claims-need-history |
| `answer/abstain.py` | `pre_gate`, `abstention`, `is_bulk_dump`; `TAU_SCORE=0.02`, `TAU_COV=0.0` (locked) | |
| `answer/evidence.py` | `build()`, `render()` | text from `chunks.text` at `snapshot_sha` only |
| `answer/cache.py`, `answer/audit.py` | `make_key/store/lookup`, `write()` | both live INSIDE the index SQLite (service tables) |
| `llm/gateway.py` | `generate()`, `check_cloud_allowed()` | transport retries only; schema failures are the validator's job |
| `llm/egress.py` | `check_url` (loopback-only), `check_cloud_url` (exact host allowlist) | |
| `retrieve/search.py` | `search(db, sha, query, k)` → `{hits, confidence, analysis}` | read-only DB; lexical+symbol+path, RRF |
| `index/store.py` | `build()`, `ensure_service_tables()` | `init_db` refuses to overwrite; rebuild = delete first |
| `index/freshness.py` | `reindex()`, `index_status()`, `content_stale()` | rollback rule = full rebuild |
| `parse/*` | `parse_many()` (worker pool), `build_edges()` | child-proc isolation; failures contained |
| `features/*` | `arch.extract`, `tours.build`, `tasks.collect/link_tours/rank/validate`, `why.history_blocks`, `precompute.run` | deterministic-first; LLM only behind validator gates |
| `eval/*` | `gold.load/validate`, `harness.run`, `metrics`, `stats.wilson` | baselines B1 (BM25) and B3 (fused) only |
| `api/routes.py` | `POST /api/repos`, `/index`, `/ask`; `GET /code|status|architecture|tours|tasks` | module-level `REGISTRY` is the test/demo injection seam |

## 5. Commands

```bash
# Python env (created once; Python 3.14 on this machine — spec wanted 3.12, deviation D0.2)
cd mentor-project && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# Build an index (manifest + parses must exist for the SHA)
python -m mentor.cli index --repo data/repos/fst --sha 7257e606... --out data/indexes/fst.sqlite
python -m mentor.cli serve --index data/indexes/fst.sqlite   # http://127.0.0.1:8000
python -m mentor.cli demo  # verify + 15-step runbook + serve (opens browser)

# Tests — run before claiming anything works
pytest tests/ -q                       # unit + integration + security
pytest tests/security -q               # T1-T14 threat-model tests
powershell -ExecutionPolicy Bypass -File scripts/security_check.ps1  # pytest sec + bandit + pip-audit + npm audit

# Web (web/)
npm test                # vitest (5 tests)
npm run build           # tsc + vite build -> dist/ (test_web_build.py gates the built HTML)
npx playwright test     # e2e; needs `mentor serve` running on :8000 (no webServer auto-start)
```

Many tests are **artifact-gated**: they `pytest.skip()` with the exact build command if
`data/indexes/fst.sqlite`, `data/parses/<SHA>.json`, etc. are absent. A fresh clone therefore runs
a reduced suite until artifacts are built. Live-model tests need `MENTOR_LIVE=1` or an operator-
started llama-server (`scripts/fetch_llm.py` downloads Qwen3-4B GGUF).

## 6. Conventions

- **Control-file discipline:** gates/decisions/measurements are recorded in `DECISIONS.md` /
  `VALIDATION_REPORT.md` / `EVALUATION_RESULTS.md` / `RESEARCH_LOG.md` before or with the change
  (Global Rules 1–15). A LOCKED decision changes only via a new DECISIONS entry, then code.
- **Commit style:** `phase-NN: <gate name>` for phase work; recent history also uses
  `perf-NN:`, `tasks-NN:` topic prefixes. One commit per phase/gate; tests green between phases.
- **Evidence labels** in RESEARCH_LOG: `[PRIMARY RESEARCH] [OFFICIAL] [INDEPENDENT BENCHMARK]
  [OBSERVED PRACTICE] [INFERENCE] [ENGINEERING JUDGMENT]`.
- **Python:** stdlib + pydantic/fastapi/tree-sitter only where needed; dataclasses for internal
  shapes; parameterized SQL; no TODO/FIXME markers exist — forward work lives in DECISIONS/future.md.
- **Tests:** one file per subsystem, docstrings name the phase gate; golden JSON fixtures in
  `tests/golden/`; never weaken a validator rule to make a test pass.
- **Web:** plain CSS design system (`src/styles.css` + CSS vars), no UI framework, no dangerouslySetInnerHTML
  (gate: `tests/test_web_build.py`), plain-text answers (XSS surface), strict CSP in `index.html`.

## 7. Current state (as of this file)

- Working tree has **uncommitted web work**: a D16.5 UX/theme refresh — new `web/src/theme.ts`
  (persisted light/dark, `cm:theme` CustomEvent), lifted `AskState` in `App.tsx` (so citation →
  back navigation preserves question/answer), `ProviderPill`/status-dot in StatusBar, nav/card/skeleton
  restyle, mermaid re-render on theme flip, one new e2e test in `smoke.spec.ts`. 9 modified files +
  `theme.ts` untracked + root `opencode.json` untracked. Also `mentor-project/web/src/styles.css`
  carries the D16.5 refresh.
- Last commits: `tasks-6` (calibration v2 + vendored exclusion), `ui refresh + tasks-5`,
  `tasks-4/3/2/1`, `perf-08…05`.
- Test suite: last recorded run had zero failures; red team summary `critical_open=0`, worst=medium.

## 8. Known bugs / review findings (found during a full read; NOT yet fixed)

Highest impact — verify each before fixing (line numbers may drift):

1. **SPA static handler path traversal** — `mentor/api/app.py` (~:65-73): `dist / path` without
   `resolve()`+`relative_to(dist)` confinement; absolute paths (`/etc/passwd`) and `..` escapes can
   serve arbitrary files. Loopback-only mitigates; no test covers this route (unlike `/api/.../code`).
2. **Cache key omits `why` flag** — `answer/cache.py:make_key` + `api/routes.py`: a `why=True`
   answer (with H-blocks) can be served to a non-`why` request and vice versa.
3. **Repair prompt omits the rejected output** — `answer/qa.py` `_repair_message`: model is told
   "your output was REJECTED" but never sees it → repair is a blind regeneration.
4. **`why` + `cloud` silently drops history blocks** — `qa.py:_serve_with_cloud` replaces blocks
   with redacted code-only blocks → V9 then rejects all causal facts.
5. **`retrieve/lexical.py` and `confidence.identifier_coverage` lack `snapshot_sha` filter** —
   cross-snapshot pollution on multi-snapshot indexes (inflates `top_score`, the tau gate signal).
6. **`parse/parse_worker.py` retry loop mis-indented** — lines ~285-289 sit outside the `for`;
   only the LAST file per pass is ever retried despite the docstring.
7. **Py extractor: `import a, b` records only `a`; nested functions never become symbols** (their
   call edges vanish). TS extractor has the mirror bug: nested calls double-attributed.
8. **`features/tasks.py:rank` drops ALL high-risk tasks** whenever safe tasks ≥ limit —
   contradicts "still listed, never hidden". `security-learn` verify command runs bandit on the
   nearest *test* file instead of the flagged file.
9. **`api/app.py` body cap is Content-Length-only** (chunked bypass); `register_repo` fails open
   (git failure → SHA check skipped; arbitrary path accepted).
10. **Web: Ask.tsx suggestion-click stale closure** overwrites the question text with the old one
    after the answer returns; `StatusBar staleCount` hardcoded `0` (always green); inline `style=`
    widths conflict with `style-src 'self'` CSP (skeleton/progress bars may render 0-width);
    `hostRef.innerHTML` in Architecture/Tours evades the `dangerouslySetInnerHTML` grep gate;
    duplicate provider label line in Ask.
11. Smaller: `register_repo` id path-injection (latent), audit misattributes provider on cache
    hits, demo verifies `data/demo_cache` while API reads `data/cache`, dead config
    (`LLM_FALLBACK_*`, `TAU_COV=0` branch), `arch.py` latent KeyError → 500, `tours.narrate`
    `IN ()` crash on empty evidence, `why.gh_pr` missing `encoding="utf-8"`,
    `metrics.file_precision_at_k` divides by k not len(top), no secondary indexes in
    `schema.sql` (retrieval p95 3.2s on 10k chunks — fix sketch in `future.md`, not implemented).

## 9. Docs index (where to look for what)

| Question | Read |
|---|---|
| What should I do next / is the phase done? | `mentor-project/PROJECT_STATUS.md` |
| Why is it built this way? Is it locked? | `mentor-project/DECISIONS.md` (A1-A18, G1-G4, D*), `docs/ARCHITECTURE.md` |
| Did a gate pass? Exact numbers? | `mentor-project/VALIDATION_REPORT.md`, `EVALUATION_RESULTS.md` |
| Sources for a research claim? | `mentor-project/RESEARCH_LOG.md` |
| Security threats / controls / residuals | `mentor-project/SECURITY_THREAT_MODEL.md`, `redteam/PLAN.md` + `redteam/results/` |
| How to demo | `mentor-project/DEMO_RUNBOOK.md`, `PROJECT_BRIEF.md` (judge cheat-sheet), `mentor/demo.py` STEPS |
| Eval gold / tours / study protocol | `mentor-project/evals/gold/v1.yaml`, `evals/tours/*.yaml`, `evals/study/protocol.md` |
| Future work / out-of-scope findings | `mentor-project/future.md`, spec "Future Work" |
| Rules I must follow while working | spec §Global Rules (§0 of this file summarizes the critical ones) |

## 10. Hard stops (Global Rule 15)

Stop and ask the human when: a licence is unclear; a benchmark contradicts a LOCKED decision;
a required hardware measurement is impossible; or user data would have to leave the laptop.
Never commit `data/` or secrets. Never mark a phase complete on code alone — the named gate must pass.

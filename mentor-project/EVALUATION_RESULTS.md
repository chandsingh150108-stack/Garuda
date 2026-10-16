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

## Phase 7 gate G1 (embedding decision, 2026-10-12, this laptop CPU-only)

Rule: adopt dense iff fused Recall@10 exceeds B3 by ≥5pp AND full CPU embed <30 min AND licence permits. Otherwise lexical-only ships (specified success).

| Candidate | Licence (source card) | Recall@10 vs B3 0.424 | Full CPU embed | Verdict |
|---|---|---|---|---|
| none (B3 floor) | n/a | 0.424 (baseline) | 0 min | SHIP |
| bge-m3 (568M/1024d) | MIT ✓ | unmeasured (moot) | ~80 min projected (319 chunks / 19.9 min measured) — FAIL | REJECT |
| jina-embeddings-v2-base-code (161M/768d) | Apache-2.0 ✓ | unmeasured (moot) | load BLOCKED (custom code vs transformers 5.x) — FAIL | REJECT |
| jina-code-embeddings-0.5b | non-commercial (V15) | not attempted | needs GPU + trust_remote_code — FAIL | REJECT |

Outcome: G1 REJECTED. `DENSE_MODEL = "none"`. dense.py remains a tested-but-disabled path (6 unit tests, fake encoder). Eval tooling (torch/ST) pinned in `requirements-eval.txt`, never in shipped `requirements.txt`. B3 R@10 0.424 stands as the floor for Phase 8+.

## Phase 9 answer eval (grounded QA, 2026-10-16, Qwen3-4B Q4_K_M via llamacpp-vulkan)

Validator: 12/12 invalid-output suite rejected with expected codes (100%), valid answer/abstain controls pass. Injection-in-evidence: injected instruction-following output rejected (V3+V6), qa serves abstention. Repair: invalid→valid yields validated answer with repairs=1; double-invalid abstains. Budget: evidence ≤3000 tok enforced (truncated flag).

τ calibration (seed 7, `scripts/calibrate_tau.py`, one live pass + offline grid): TAU_SCORE=0.02, TAU_COV=0.0 (coverage adds nothing beyond score on dev).

| Split | n | Correct | False-answer | False-abstain |
|---|---|---|---|---|
| dev (calibration) | 15 (9 ans / 6 abs) | 12 (0.800) | 0/6 = 0.000 [0.00, 0.39] | 3/9 = 0.333 [0.12, 0.65] |
| test (locked τ) | 15 (13 ans / 2 abs) | 10 | 1/2 = 0.500 [0.09, 0.91] | 4/13 = 0.308 [0.13, 0.58] |

Commands: `python scripts/calibrate_tau.py --out docs/calibration_p9.json`; `python -m mentor.cli eval answers --split dev|test --seed 7 --out docs/eval_answers_{dev,test}.json` (locked-τ confirmation matched simulation exactly).

Reading: pre-gate abstains cluster at top_score 0.01639 (=1/61, single-retriever rank-1 only). Residual false answer (q25 "billing", no billing code exists): model served a hedged confabulation citing 10 unrelated blocks — passes V1–V8 (valid shape, no checkable identifiers) but semantically unfaithful. This is the documented honest limit in action, not a validator bug; tightening τ further trades measured false abstains (dev grid already optimal).

## Phase 10 service smoke (live API, 2026-10-16, 4B via llamacpp-vulkan + uvicorn loopback :8000)

`mentor serve --index data/indexes/fst.sqlite --port 8000`; 5/5 questions completed, no unhandled errors, all responses contract-valid:

| Question | Expected | Got | Evidence |
|---|---|---|---|
| q01 registration (`register_user`) | answer | answer, 1 seg, repairs=0 | 6 blocks (users.py:103-161 top) |
| q03 password hashing | answer | abstain (pre-gate, score 0.01639) | closest 3 refs |
| q12 frontend pages/signup page | answer | answer, 1 seg, repairs=0 | 7 blocks |
| q20 delete own account | answer | abstain (pre-gate, score 0.01639) | closest 3 refs |
| q25 billing | abstain | answer (known Phase 9 residual) | 10 blocks |

Cache + audit rows landed in the gitignored index DB (runtime data, not committed). Bind refusal, path confinement, range cap, and 413 covered in `tests/test_api.py`.

## Phase 13 tours (precomputed 2026-10-16, 4B narration, validated per step)

`mentor tours precompute --narrate` over evals/tours (cache: gitignored `data/cache/tour_fst_*.json`):

| Tour | Steps (≥3) | LLM-narrated | Drops (all reasoned) | Sequence check |
|---|---|---|---|---|
| signup "What happens when a user signs up?" | 8 | 7 | 2 (HTTPException, select: external) | clean |
| login "How does login issue an access token?" | 6 | 5 | 6 (Depends param; HTTPException/timedelta/jwt/datetime/select external) | clean |
| crud "How is a new item created?" | 3 | 3 | 0 | clean |

Manual review (VALIDATION_REPORT.md): signup flow correct end-to-end (route → email lookup → validate → create → hash); login chain correct (route → authenticate → email+password verify → token); crud thin but honest — session.add/commit emit no call edges (parser recall limit), tour holds exactly the 3 evidenced steps, nothing invented. No wrong steps in any tour.

## Phase 14 why eval (4 gold why questions, --why with history, 2026-10-16, 4B)

`mentor eval answers --category why --why`: q21 answer, q22 abstain (pre-gate; false abstain), q23/q24 abstain (correct UNKNOWN). False-answer 0/2 [0.00, 0.66].

Manual audit (zero inferred-as-fact REQUIRED — met): q21 served one fact citing E1+H2 where H2 IS the gold commit 689d7105 ("constant time, to avoid enumeration attacks") — a genuine HISTORY-grounded causal answer (provenance defaulted to history). q22's open-registration rationale (commit 1f686689) exists in history but retrieval never surfaced the code (pre-gate abstain — retrieval floor, not a provenance failure). q23/q24 correctly UNKNOWN: commits record the change but no rationale, and the model abstained instead of fabricating.

## Phase 15 tasks (mined 2026-10-16, 20 candidates → ranked 10)

`mentor tasks --limit 10`: all validated (files exist, ranges in bounds, tour links resolve).

Top-five author judgment (REQUIRED ≥4/5 reasonable — met 5/5):
1. compose TODO marker (d=2.00) — reasonable: trivial, checkable, true starter.
2. tests for `emails_enabled` (d=2.69) — reasonable: tiny pure property, learns test layout.
3. tests for `custom_generate_unique_id` (d=2.69) — reasonable: pure helper, same shape.
4. tests for `get_datetime_utc` (d=2.69) — reasonable (borderline busywork, but a genuine gap and a safe first file-touch).
5. tests for `health_check` (d=2.69) — reasonable: route-test pattern every newcomer needs.

Tour linkage measured: models.py tasks → crud+login tours; security tasks → login+signup; scaffolding files → no link (none rather than wrong). Calibration deviation recorded in evals/tasks_calibration.md (security scope-small/risk-flagged split across axes by design).

## Phase 8 gate G2 (local-model decision, 2026-10-15, target laptop RTX 5060 8GB)

Backend `llamacpp-vulkan` (llama.cpp b11429 win-vulkan-x64, `-ngl 99 -c 8192 -np 1`); Ollama remains the documented default, CUDA re-measurement is future work (D8.0). Validity probe = Phase 9-contract-shaped `{status, segments[]}` on the 22 answerable gold items, no repair. Raw JSON: `docs/bench_7b.json`, `docs/bench_4b.json`.

| Model | Peak VRAM @8K (≤7.0 GB) | Schema validity, no repair (≥90%) | Sustained 10 min | Q latency mean / TTFT | Verdict |
|---|---|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct Q4_K_M (~4.7 GB, Apache-2.0) | 4814 MiB (4.70 GB) — idle-loaded 4793, 4K 4814, 8K 4814 ✓ | 22/22 = 1.000 [0.85, 1.00] ✓ | 288 it, 51.9 tok/s mean/p50 54.6, temp 68–86 °C, power ≤70.5 W (max 100 W), no throttle signal ✓ | 2.55 s / 0.10 s | QUALIFIED fallback |
| Qwen3-4B-Instruct Q4_K_M (~2.5 GB, Apache-2.0, `/no_think`) | 3658 MiB (3.57 GB) — idle-loaded 3642, 4K 3658, 8K 3658 ✓ | 22/22 = 1.000 [0.85, 1.00] ✓ | 345 it, 82.9 tok/s mean/p50 83.1, temp 54–87 °C, power 62–71 W, no throttle signal ✓ | 0.94 s / 0.13 s | G2 WINNER (tiebreak: lower VRAM) |

Commands: `python scripts/bench_llm.py --provider llamacpp --endpoint http://127.0.0.1:8080 --model qwen2.5-coder-7b-instruct-q4_k_m --ctx 8192 --gold evals/gold/v1.yaml --sustained-minutes 10 --timeout 300` (4B adds `--no-think-suffix /no_think`).

Rule applied (spec G2): both satisfy (a)+(b)+(c); validity tied at ceiling 1.000 → tiebreak lower peak VRAM → Qwen3-4B. `mentor/config.py`: `LLM_MODEL = "qwen3-4b-instruct-q4_k_m"`, `LLM_CTX = 8192`, `LLM_SYSTEM_SUFFIX = "/no_think"`.

Caveats (open for Phase 9 answer-quality eval): (1) validity probe checks shape only, not code-answer correctness — the code-specialized 7B may answer better; revisit with evidence if Phase 9 correctness comparison favors it. (2) 4B requires `/no_think`: without it, thinking tokens exhaust the budget and content arrives empty (measured 5.1 s + empty vs 0.3 s + valid JSON). (3) nvidia-smi read 0 MiB once with the 4B server idle-running (driver/Vulkan attribution quirk); in-bench readings under load (3642–3658) are the trusted numbers.

## Phase 17 reindex timing (2026-10-16, target laptop, SHA 7257e60)

Scripted scratch-file edit (`demo_live_edit_scratch.py`, untracked) + `FR.reindex` on tmp copies of the primary index/manifest/parses (pinned artifacts untouched, scratch reverted after):

| Changed | Reparsed | Index rows touched | Elapsed | Gate (<60 s) |
|---|---|---|---|---|
| added 1 file | 1 file | 1 file / 1 chunk / symbols | 0.68 s | PASS |

Command pattern: `python -m mentor.cli reindex --repo data/repos/fst --index <IDX> --manifest <M> --parses <P>`. Full-suite re-verification in `tests/test_freshness.py::test_reindex_primary_repo_under_60s` (same setup, asserts elapsed < 60).

## Phase 19 demo cache (2026-10-16, local 4B via loopback)

`mentor precompute --install` (manifest: `data/demo_cache/precompute_manifest.json`, git-ignored):

| Artifact | Result |
|---|---|
| arch | 8 nodes / 14 edges, mermaid check clean |
| tours | signup / login / crud, all ≥3 validated steps, installed to `data/cache` |
| tasks | 10 ranked + validated |
| answers | 8/10 validated + cache-warmed (q01 q04 q05 q10 q12 q15 q16 q17); q03 + q09 abstain pre-gate (retrieval floor, §Phase 6) |

Offline serving: `scripts/offline_check.py` → 8/8 demo answers cache-labelled, 0 non-loopback attempts under enforcing guard.

## Phase 20 study pre-registration (2026-10-16 — DEFERRED, n=0)

Protocol `evals/study/protocol.md` frozen at SHA-256
`2ddbe21611d38e28287e2e1182bb9d831762046912e00453726cfd59d7e8fe90`
(recorded in DECISIONS.md before any data collection). Tooling verified on
synthetic data only (`tests/test_study_analysis.py` 4/4: balanced 4-sequence
schedule, known-effect Wilcoxon reproduced, bootstrap CIs cover +
reproduce). Control condition (B6 no-retrieval, same rubric) defined in the
protocol, data pending.

| Item | Status |
|---|---|
| design / metrics / rubric / consent / schedule / analysis code | DONE, hashed |
| participants recruited | 0 — NO pool in this environment (recorded cause) |
| sessions run / scored | 0 (deferred) |
| metrics incl. nulls | pending data; will report all or pilot-flag |

Per the spec rollback rule this is reported as a pre-registered DEFERRED
study with limits stated — not as results. Phase 21 proceeds on the
explicit-deferral precondition.

## Phase 22 final red team (2026-10-17, SHA 7257e60, Qwen3-4B via llamacpp-vulkan)

Command: `python redteam/attacks/run_all.py --index data/indexes/fst.sqlite`
(+ `python redteam/attacks/family12_g3.py` for F12/G3, needs model server for B6).
Reproduced live 2026-10-17: worst=medium (F11 expected), critical_open=0.
Results: `redteam/results/f*.json` + `summary.json`.

| Family | Result | Severity |
|---|---|---|
| F01 hallucinated citations | 3/3 bad citations rejected | low (none) |
| F02 fake ranges | clamped 36-36; traversal 400 | low (none) |
| F03 stale | clean current, edited stale | low (none) |
| F04 injection | 20/20 payloads rejected; CF `User_cf` hit | low (none) |
| F05 exfil | 4/4 bulk refused; 0 secret-like chunks | low (none) |
| F06 access | traversal 400/404; unknown repo 404 | low (none) |
| F07 malicious | symlink refused/binary skipped/nesting contained | low (none) |
| F08 quota | 429 falls back labelled-local | low (none) |
| F09 model failure | TRANSPORT abstain, no partial | low (none) |
| F10 indexing | corrupt file contained, build completes | low (none) |
| F11 unanswerable | 8/18 gated pre-model; 10/18 reach model | medium (documented residual: validator + Phase 9 FA 1/2 backstop) |
| F13 drift | signup tour stale=False | low (none) |

### G3 file-precision (CodeGrep definition, n=22 answerable, 2026-10-17)

| Index | B1 mean file-P@10 | B3 mean file-P@10 |
|---|---|---|
| fst (original) | 0.059 | 0.050 |
| fst-cf (counterfactual) | 0.055 | 0.050 |

Reading: an order of magnitude below the CodeGrep help-band (0.45-0.68; BM25 0.375 hurts / Jina 0.445 neutral). G3 NOT ADOPTED — stay hybrid RAG. At n=22 / mean 0.05 no benefit claim can exclude zero.

### F12 contamination (B6 no-retrieval, 6 items q01/q03/q05/q09/q10/q15, must_include keyword hit)

| Copy | Keywords hit | Items |
|---|---|---|
| original fst | 1/20 | q09 1/3, rest 0 |
| counterfactual fst-cf | 1/20 | identical rows |

Reading: no memorization signal — the 4B model knows neither copy (identical floor). B3-recall parity (Phase 6: R@10 0.424 both) shows retrieval is structure-grounded. Grounding value = B3 0.424 vs B6 0.05.
Raw: `redteam/results/f12_contamination.json`.

### G4 reranker: NOT ADOPTED (no vetted candidate run; reason in DECISIONS.md G4).

### Support sample (entailment-style manual grade, n=8 cached demo answers)

| Answer | Claim in brief | Cites | Verdict |
|---|---|---|---|
| q01 register_user | checks email, creates user w/ email+password+name | users.py:103-161 + test | supported |
| q04 login tokens | authenticate, sign w/ sub+exp, return token | login.py:1-52 | supported |
| q05 create_item | ItemCreate validate + save w/ owner | items.py:61-113 + crud.py:45-68 | supported |
| q10 models | SQLModel/Postgres, user+item tables, id/owner_id/old_id | 3 alembic versions | supported |
| q12 signup page | React form + validation at /signup | signup.tsx:1-73 | supported |
| q15 signup e2e | page -> validate -> registerUser POST /api/v1/users/signup | sdk.gen + signup.tsx | supported |
| q16 login e2e | login page POST /api/v1/login/access-token form data | sdk.gen + login.py | supported |
| q17 create-item e2e | ItemsService.createItem POST /api/v1/items/ | sdk.gen:260-324 | supported |

Support rate on this sample: 8/8 = 1.000 [0.68, 1.00] (Wilson n=8 — wide by design).
Known residual OUTSIDE this sample: q25 billing confabulation (Phase 9 test FA 1/2) — valid shape (V1-V8 pass), semantically unfaithful. This is the honest limit in action, not a validator bug.
Tau re-check: TAU_SCORE=0.02 / TAU_COV=0.0 stand; pre-gate abstains still cluster at 0.01639; the 0.02-on-observed-score grid artifact is re-recorded, unchanged for lack of contrary evidence.

## perf-00 index-build micro-benchmarks (2026-10-17, target laptop, `scripts/bench_index_costs.py`)

| Probe | Result |
|---|---|
| Spawn tax (`run_isolated` vs in-process `parse_bytes`, `sklearn/ensemble/_forest.py`, n=5) | spawned 0.28–0.34s vs in-process 0.009–0.01s — spawn ≈ 30x the parse; ~0.6s spawn tax per code file (parse + chunking phases) |
| 11 parse-timeout files, in-process | `parse_bytes` 0.009–0.038s + `extract_py` 0.024–0.118s each (all <0.16s total) — NOT slow; grammar pathology ruled out |
| Same 11 via `run_isolated`, 10s then 120s | all expire (deterministic, servers stopped) — true hang in spawned context only |
| Hung child CPU over 14s wall | 0.2s — blocked, not spinning (deadlock signature) |
| Pickled result sizes, all 1045 parses | 11 failures 64–119KB; 1034 passes ≤63KB; zero overlap — ~64KB pipe-buffer cliff |

Reading: `run_isolated` (`mentor/parse/parse_worker.py:29-44`) joins-then-reads; results above the pipe buffer deadlock the feeder because the parent never drains during `join` (it only `get_nowait`s after). No finite timeout escapes; the `"timeout"` label is a misdiagnosis. Same landmine under `chunker.plan_file`. Spawn tax (~0.3s/spawn, ~1,800 spawns for sklearn) is the dominant total-time term.

## perf-05 gate: plan pruning NOT ADOPTED (measured 2026-10-17)

`plan_file` via the persistent pool on sklearn's biggest files: estimator_checks.py (215KB) 0.52s, _classification.py 0.10s, _data.py 0.13s, _forest.py 0.11s. Full-tree plan build + pickle + transfer is linear and small next to the (now removed) spawn tax. Pruning to top-level-only plans would save ~0.05s typical / ~0.4s worst-case per file while risking chunk-identity drift on oversized units (line-split fallback changes `chunk_id`s, invalidating caches/tours/audit). Rejected: ~5% gain cannot justify identity risk. The deadlock fix + worker reuse already removed the two binding costs.

## perf acceptance: sklearn probe (2026-10-17, `scikit-learn@85593ca`, BSD-3-Clause)

All seven perf steps landed (perf-00–perf-07). End-to-end proof on a 1,124-file repo:

| Stage | Result |
|---|---|
| clone + pin | full clone, HEAD `85593ca`, clean tree, LICENSE verified BSD-3-Clause on the checkout |
| manifest | 1,856 entries: 1,124 indexed (1,038 py, 16.7MB), 732 skipped by extension (`.pyx`/C++/media — expected coverage limit) |
| parse | **1045/1045 (100.0%), failed=0** (pre-fix: 1034/1045 with 11 deadlock-burns). Progress ticks every 100 files |
| index | **1124 files / 10,113 chunks / 12,060 symbols / 8,857 imports / 55,211 edges, failed=[] in 123.2s** (~0.11s/file steady, progress every 50 files). Pre-fix: stalled indefinitely, aborted twice |
| identifier probe | 4/5 definition chunks top-3 (`RandomForestClassifier`, `cross_val_score`, `ColumnTransformer`, `StandardScaler` HIT; `check_array` MISS — `estimator_checks.py` outranks the `validation.py` definition on pure lexical frequency) |
| retrieval latency (n=15, cold AND warm identical) | p50 ~1.1s / p95 ~3.2s — breaches the 200ms gate. Profiled: lexical 2–10ms, **symbol retriever 0.4–2.8s**, rest <1ms. Root cause found (see below), fix proposed as follow-up, NOT in this batch |
| live asks (local 4B) | symbol-precise (`RandomForestClassifier`): validated answer, repairs=0, cites `_forest.py:1590-1618` etc. Conceptual ("How does a random forest classify?"): honest abstain (closest refs are junk — the documented lexical-only floor) |
| tasks | 10 ranked TODOs validate clean |
| arch | 0 nodes / 0 edges — BY DESIGN (D12.2 component rules are fst-path-specific; new repos need their own mapping). Side effect found: `arch` CLI hardcodes the `data/cache/arch_fst.mmd` out path and clobbered the demo cache twice; restored via deterministic regen (8n/14e verified). Recommend a `--out` default scoped by repo id |
| tours | not run (seed definitions are fst-specific; needs a sklearn seed file) |
| serve :8001 | status OK (`sklearn@85593ca`, 1,124 files, 10,113 chunks). Note: registry id is hardcoded `fst` in `cmd_serve` (pre-existing demo shortcut); `dirty=True` shown despite a clean tree — worth a look, not a blocker |

New finding (out of scope, recorded for follow-up): `schema.sql` has **zero secondary indexes** — every symbol/path lookup is a full scan of wide TEXT rows. Measured consequence above. Fix sketch: `symbols(snapshot_sha,name)`, `symbols(snapshot_sha,qualname)`, `chunks(snapshot_sha,path,start_line,end_line)` covering indexes → schema v3 + rebuild (per the schema rule). Same latent cliff exists for edge traversal (tours) and task collection at this scale.

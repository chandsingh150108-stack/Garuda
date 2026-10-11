# Codebase Mentor — Evidence-Driven Reassessment (Oct 2026)

> Role: principal AI research scientist + software architect + security architect + devtools researcher.
> Fixed product constraint: AI mentor that reads a repo and helps newcomers understand it quickly, every answer grounded in actual code. Capabilities: architecture overview, guided tours (e.g. signup flow), how/why answers with exact files+lines, starter tasks, optionally docs that stay fresh. Outcomes: works on a real OSS repo, every answer cites code, small user test shows faster understanding.
> Everything else was treated as hypothesis. This report **replaces** the attached `Codebase Mentor Architecture & Research Report.md` where evidence disagrees with it.
> Evidence labels: **[Research]** papers/independent benchmarks, **[Official]** official docs/cards, **[Observed Practice]** production systems, **[Inference]** derived, **[Engineering Judgment]** recommendation.
> Research date: Oct 2026. All versioned claims verified live in this session unless marked otherwise.
> **Revision 2 (zero-budget):** total spend = $0. No paid APIs/VMs/managed DBs. Assumptions: no-card signups (Google AI Studio + Groq) acceptable; free-cloud touches the **public demo repo only** (hard-pinned); **Groq primary**, Gemini Flash fallback. Local Ollama 7B is the default/private path. Free-tier quotas re-checked Oct 2026 and must be re-verified demo week (providers change them often).

---

## 1. Executive Summary

1. **The attached report is ~70% right in shape, wrong in three load-bearing defaults.** Keep: evidence-ID citations + validator + abstention; hybrid retrieval; Tree-sitter AST chunking; custom thin pipeline (no LangChain); Postgres + dedicated vector store; Docker Compose; Mode A/B behind an adapter. Change: (a) embedding default cannot be `bge-m3` — 2026 code-retrieval evidence favors small **code-specialized** embedders (jina-code-class / C2LLM-class) over general multilingual encoders, and leaderboard scores do not transfer — measure recall@10 on your repo; (b) **reranker is NOT a default** — CoREB May 2026 shows no off-the-shelf reranker is net-positive across tasks (up to −22% on code-to-text) [Research]; make it conditional/Stage 3; (c) **local-model default cannot be 14B on the RTX 5060 Laptop** — it has **8 GB GDDR7** [Official], and Qwen2.5-Coder-14B Q4 needs ~9.9–12 GB [Official/community]. Comfortable laptop model is **7B-class Q4 (≈5.7 GB)**; 14B is a lab-server tier, 32B/Qwen3-Coder-MoE/gpt-oss-20b (16 GB min) do not fit 8 GB.
2. **The core technical problem is not "RAG".** It is *verifiable repository question-answering*: deterministic facts (files, symbols, imports, routes, config, tests) from static analysis + probabilistic narration from an LLM, with a **system-level grounding guarantee** (IDs + schema + validator + abstention), because prompts alone are unreliable and up to 57% of citations in attributed QA are post-rationalized (correct-looking but unfaithful) [Research].
3. **Biggest 2026 shift since the attached report: agentic search > single-pass RAG for code.** Claude Code uses grep, not embeddings [Observed Practice]; CodeGrep (Aug 2026) shows iterative grep/glob/read agents beat BM25/Jina only above a precision threshold (~0.45–0.68), otherwise retrieval hurts [Research]; Morph/Cognition report 3–4 turn, 8-parallel-call loops with isolated subagent context as the production pattern [Observed Practice]. Recommendation: **constrained agentic retrieval** (orchestrator calls search tools, model never gets arbitrary shell) — not pure RAG, not free-form agent.
4. **What to build with 4 people / 1.5 weeks at $0 (local-first + free-tier boost):** single-repo, Python+TS first; Tree-sitter cAST-style chunks + file summaries; hybrid BM25 (Postgres FTS) + code-specialized vectors + symbol lookup, RRF, **no reranker in MVP**; **local Qwen2.5-Coder-7B Q4 via Ollama as default** + optional free-tier cloud (Groq `qwen3`/`gpt-oss-20b`, Gemini Flash fallback) enabled ONLY for the public demo repo via `allow_free_cloud` flag (default false); evidence-ID JSON + validator + abstention; React+Vite+Monaco+Mermaid; 3 precomputed + cached tours; static-signal starter tasks; webhook-diff stale badge; localhost demo (no paid hosting), pre-indexed + precomputed night-before. Defer: paid cloud LLMs, SSO, K8s, precise call graphs, runtime tracing, GraphRAG communities, entailment-in-prod, multi-repo federation.

---

## 2. Fixed Problem Statement

> Build an AI mentor that reads a code repository and helps a newcomer understand it quickly, with every answer grounded in the actual code. Architecture overview; guided tours ("what happens on signup?"); how/why with exact files+lines; starter tasks; optionally docs that stay fresh. Works on real OSS repo; every answer cites code; small user test shows faster understanding.

## 3. What the Existing Report Got Right

- Evidence-first answering (IDs, structured output, validator, abstention) — aligns with 2025 findings that correctness ≠ faithfulness and validators must live outside the model [Research].
- Hybrid > vector-only for code (identifiers/literals/routes) — confirmed by CodeRAG-Bench and Sourcegraph's BM25+signals stack [Research][Observed Practice].
- Tree-sitter as primary parser (uniform, error-tolerant, exact lines) + LSP enrichers later — correct; cAST (EMNLP 2025 Findings) uses tree-sitter for chunking and gains +4.3 Recall@5 on RepoEval [Research].
- Custom thin pipeline over LangChain; Postgres + Qdrant; FastAPI+Pydantic; React+Vite+Monaco+Mermaid; Docker Compose — all defensible.
- Two deployment modes behind adapter; honest "self-hosted ≠ secure" + ACL-inside-query + egress test — matches OWASP LLM01 2025 mitigations [Official].
- Content-hash incremental indexing; gold question set with unanswerables; crossover user study with limits stated.

## 4. What the Existing Report May Have Wrong (and fixes)

| # | Report claim | Verdict | Fix |
|---|--------------|---------|-----|
| 1 | `bge-m3` default embedder | **Overturned** | Start with code-specialized small model (jina-code-class 161M/768d/8k Apache-2.0 [Official], or C2LLM-0.5B-class per CoREB); bge-m3 (569M/1024d/8k MIT [Official]) is fallback generalist. Decide by on-repo recall@10, not MTEB. |
| 2 | `bge-reranker-v2-m3` as near-default | **Overturned** | CoREB: no off-shelf reranker net-positive; 12-pt swing; −22% worst case [Research]. MVP: no reranker. Stage 3: conditional rerank for code-to-code only, or fine-tuned reranker. |
| 3 | Qwen2.5-Coder-14B default local, 32B server | **Infeasible on 8 GB laptop** | 7B Q4 (5.7 GB) = laptop [Official/community]; 14B Q4 (9.9–12 GB) = 12 GB+ lab box; 32B Q4 (20–23 GB) = 24 GB workstation; gpt-oss-20b needs ≥16 GB [Official]; Qwen3-Coder-30B-A3B/Next (30–80B total) need far more despite 3B active. |
| 4 | Single-pass hybrid RAG as final | **Insufficient** | Move to constrained agentic retrieval (orchestrator + grep/symbol/read tools, 3–4 iterations, parallel calls, isolated context) per 2026 agent-search evidence. |
| 5 | Qdrant + Postgres both from day 1 | **Over-scoped for 1.5 wks** | MVP: Postgres (FTS+meta) + **one** vector store. Qdrant if ACL filtering is demo-critical; else pgvector-only to ship faster, migrate later. Chroma = prototype-only. |
| 6 | Full call-graph tours via tree-sitter | **Over-claimed precision** | Tree-sitter gives approximate name-based edges; label "likely calls". Precise graphs need LSP/compiler APIs per language (Future). |
| 7 | "Why" from code alone | **Epistemically unsafe** | Code proves what/how, not intent. Why-requires git history (PRs/issues/blame); else say "unknown". |

---

## 5. State of the Art in 2026

- **Sourcegraph Cody:** remote Sourcegraph index + local IDE context; BM25-adapted ranking + learned signals + RRF; query rewriting, filename/symbol detection; **dropped embeddings for Enterprise chat** (stale vectors, OpenAI embedding egress, >100k-repo scale) in favor of native search platform; code-graph for autocomplete; RBAC + context filters [Official eng blogs 2024, docs 2026]. Lesson: at scale, keyword+graph+freshness beats vectors; embeddings remain useful single-repo but are not mandatory.
- **Claude Code / Anthropic multi-agent:** grep-based exploration in isolated subagent contexts; lead context stays clean (+90% win attributed to context hygiene, per Morph synthesis of Anthropic reports) [Observed Practice]. Lesson: context hygiene > raw retrieval power.
- **Cursor/Windsurf (WarpGrep/SWE-grep pattern):** RL-trained search subagents, 8 parallel grep/glob/read calls × 3–4 turns, ~2.5–2.8k tok/s, 2–8 s searches; WarpGrep 0.73 F1 in 3.8 steps vs Haiku 0.72 in 12.4 [Observed Practice]. Cognition: parallelism 4→8 cuts turns 6→4 [Observed Practice].
- **CodeGrep (arXiv Aug 2026) [Research]:** 14B RL retriever (grep/glob/read, JSON file+line output) on SWE-Bench Verified 500: +1.2pp resolve (25.8→27.0%), −15% rounds, −19% tokens on resolved; BM25 (P 0.375) **hurts**, Jina (0.445) neutral, CodeGrep (0.677) helps → **precision threshold** between 0.45–0.68. Implication: bad retrieval is worse than none; measure precision before enabling agentic injection.
- **SWE-agent / OpenHands:** tool-using agents average 23 rounds / 631k tokens per resolved issue, dominated by search [Research]. Lesson: search efficiency is the bottleneck, not patching.

**"Chat with files" vs true repo intelligence:** former = chunk embed + prompt + unverified cites; latter = symbol/import/call indexes + query planning + iterative tool search + hierarchical summaries + evidence-validated answers + freshness + ACLs. Only the latter is defensible to judges.

## 6. Competitive Landscape (technical strategies, not features)

| System | Indexing | Retrieval | Context selection | Key lesson |
|--------|----------|-----------|-------------------|------------|
| Cody Enterprise | Sourcegraph remote index, re-indexed | keyword/BM25-adapted + signals + RRF, code-graph | top-N snippets by length budget + local IDE tabs | Freshness + ACL + scale without embeddings |
| Claude Code | live FS, no embeddings | agentic grep/glob/read, subagents | subagent returns spans only | Context hygiene wins |
| Cursor/Windsurf | embeddings + AST | hybrid + trained searcher | parallel fan-out, 3–4 turns | Latency via parallelism |
| Continue/Aider | local embeddings optional | file/symbol + LLM | repo maps | Repo map > raw chunks for arch |
| Greptile/CodeRabbit | PR diff index | review-specific retrieval | diff + related files | Task-specific retrieval beats generic |

## 7. Technical Problem Decomposition

**Deterministic (parser/index):** files, symbols (def/class/fn), imports, routes/decorators, config keys, SQL schema, test↔source links, file hashes, blame/PR links. **Probabilistic (LLM):** component naming, summarization, intent/why, step narration, difficulty estimates.
**Rule:** facts come from index; language comes from model; trust comes from validator. Never let LLM invent a path, line, or API that the index did not issue.

Subproblems: (a) code search, (b) repo understanding (multi-hop), (c) navigation (tours), (d) docs generation + invalidation, (e) grounding/attribution, (f) access control. This is a **repository-understanding + grounded-QA system with iterative retrieval**, not vanilla RAG.

## 8. Repository Understanding

Required model per repo@SHA: file tree + language; symbols (name/kind/range/parent/signature/docstring); imports (resolved where possible); routes/entrypoints (framework decorators); config facts (ports, services, env keys, CI jobs); schema (tables/cols per migration); tests (is_test + covers-heuristic); summaries (file→dir→repo); dependency edges (import + likely-call). Coverage: files 100%, symbols ~95% for Py/TS via tree-sitter, imports ~90%, calls approximate (~60–70% precision name-based) — label confidence.

## 9. Code Parsing

- **Tree-sitter [Engineering Judgment, primary]:** one API, all languages, error-tolerant, exact byte/line positions, fast Python bindings; powers GitHub navigation/Neovim/Zed [Observed Practice]. Limit: syntactic only — no type resolution, cross-file calls approximate.
- **LSP (pyright/tsserver/jdtls):** precise defs/refs/hover but per-language servers, needs buildable project, heavy for hackathon. Use as Future enricher.
- **SCIP/LSIF:** precise indexed code intelligence (Sourcegraph scale) — overkill for single-repo MVP; revisit for multi-repo enterprise.
- **CodeQL/Joern/Semgrep/JavaParser/TS compiler API:** precise call/data-flow or query-based vuln detection; excellent for tours/vuln tasks but per-language cost. Joern CPG `callOut/callee/reachableByFlows`, CodeQL `CallGraph:callEdge*` are the right Stage-3 tour primitives [Official docs].
- **Recommendation:** tree-sitter primary + regex/YAML/JSON/SQL parsers for config; optional `dependency-cruiser` (TS) / `pydeps` for import graphs; LSP/CodeQL only as enrichers.

## 10. Code Representation

```
Repo@SHA → dirs/modules → files (+file summary chunk)
  → symbols (fn/class/method, exact lines, signature+docstring header)
  → relationships (imports, likely-calls, test-links, route→handler)
  → summaries (file→dir→repo map-reduce) → arch model (components+edges)
```
Store original text + ranges separately from header-augmented embedding text so headers never pollute citations.

## 11. Retrieval

- **Lexical (BM25/Postgres FTS):** essential for identifiers, error strings, routes. Split camel/snake, path boosting. Cody kept this; CodeRAG-Bench shows dense often wins but lexical still critical for exact tokens [Research][Observed Practice].
- **Semantic (dense code embeddings):** fuzzy intent. Must be code-trained; general encoders lose ~2× on code-to-code [Research].
- **Structural (symbol/import/call):** cheap exact-name lookup + 1-hop expansion; highest precision for "where is X".
- **Hybrid:** parallel lexical+dense+symbol → RRF → ACL filter inside query → dedupe → budget. 2026 SOTA for single-pass.
- **Agentic (recommended final):** orchestrator plans → parallel grep/symbol/read (4–8 calls) → reason → re-query (≤3–4 turns) → assemble. Follows handler→service→DB chains RAG cannot. Cost: 2–8 s, more tokens, larger injection surface → constrain tools to read-only, validate all cites.

## 12. RAG vs Long Context vs Agents

| Criterion | Chunk RAG | Long-context stuff | Agentic search | Winner for us |
|-----------|-----------|--------------------|----------------|---------------|
| Arch questions | weak (top-k) | good if repo fits | good (summaries+drill) | agent+summaries |
| Flow tracing | weak | medium (lost-in-middle) | strong (follows calls) | agent |
| Citations | validator-friendly | hard (spans huge) | validator-friendly (spans returned) | RAG/agent |
| Latency/cost | low | high (1M ctx $$$; local impossible) | medium (2–8 s) | RAG < agent < long |
| Local 8 GB | feasible | infeasible (>32k KV OOM) | feasible (7B + tools) | RAG/agent |
| Privacy/determinism | good (top-k auditable) | poor (whole repo to cloud) | good if tools read-only | RAG/agent |
| Impl complexity | low | low but $$ | medium | RAG first, agent stretch |

**Decision [Engineering Judgment]:** ship hybrid RAG in MVP (deterministic, auditable, fast); add constrained agentic loop (no shell, only grep/read/symbol/graph tools) as Stage-3 upgrade; use long-context only as eval baseline, never primary (cost, lost-in-middle, no ACL granularity, impossible locally).

## 13. Embeddings (2026, verified)

| Model | Params/dims/ctx | Code training | License | Self-host/VRAM | Verdict |
|-------|-----------------|---------------|---------|----------------|---------|
| `BAAI/bge-m3` | 569M / 1024 / 8k [Official] | general multilingual | MIT [Official] | ~2.3 GB, CPU OK | Fallback generalist; NOT code-SOTA |
| `jina-embeddings-v2-base-code` | 161M / 768 / 8k [Official] | GitHub-code + 150M QA/docstring pairs | Apache-2.0 [Official] | ~0.3 GB, CPU/GPU trivial | **MVP default candidate** — tiny, fast, code-trained |
| C2LLM-0.5B / 7B, Jina-code 0.5/1.5B, F2LLM | 0.5–7B | code-specialized | verify per-checkpoint (mostly Apache/MIT) | 0.5B fits anywhere; 7B needs GPU | CoREB Pareto frontier; prefer 0.5B-class for laptop |
| Qwen3-Emb 0.6/4/8B | 0.6–8B | general | Apache-2.0 (verify) | 8B needs GPU | Loses to code-specialized at same size |
| Voyage-code-3, GemEmb-2, OpenAI | cloud | strong | proprietary | N/A private | Mode A only; cost + egress |
| MiniLM-L6-v2 | 22M/384/512 | none | Apache-2.0 | trivial | Baseline only |

**Benchmarks:** CoIR (10 datasets, in-domain), CodeRAGBench (retrieval→generation, RepoEval/SWE-bench), **CoREB v2026-03 (contamination-limited, graded, 5 langs, 3 tasks)** — most relevant for search quality; none measures onboarding Q&A directly. CoREB findings: specialized > scale; keyword queries collapse all models (~0 nDCG); rerank asymmetric [Research]. **Action:** 30-question on-repo recall@10 experiment (measure, don't trust leaderboards); pin model name+dim in index (change = full re-index).

## 14. Reranking — Is It Worth It?

No. Not in MVP. CoREB: 12-pt swing, no off-shelf reranker net-positive, code-to-text −3 to −22% [Research]. General RAG lore (+15–25 nDCG) does not transfer to code. **[Engineering Judgment]:** skip reranker for 1.5-week build; Stage 3 only if on-repo eval shows code-to-code gain with Qwen3-Reranker-0.6B or fine-tuned CoREB-reranker; budget GPU +300 ms.

## 15. Citation / Groundedness — Can We Guarantee?

**No prompt can guarantee; a system can make failures detectable.** Distinguish: (1) exists, (2) real file, (3) real lines, (4) relevant, (5) supports claim. Layers: index-time SHA-keyed ranges; evidence IDs (model never writes paths; server expands); JSON schema (`segments[{text, evidence[]}], insufficient_evidence`); validator (IDs exist in-request, sub-range inside, every factual segment cited, quote-check identifiers appear in cited text); one repair retry else degraded answer; UI chips → Monaco@range + SHA + stale badge; optional NLI (AlignScore/RoBERTa) or LLM entailment in eval/strict mode.
**Faithfulness caveat:** correctness ≠ faithfulness; up to 57% citations post-rationalized (Command-R+ study, ICTIR 2025) [Research]; franq/AwF framework separates factuality vs faithfulness with AwF precision/recall [Research]. Our validator enforces correctness+support; faithfulness approximated by quote-check + sufficiency gating + no-retrieval baseline in eval. Claim: 100% citation *validity* achievable; *support* measured and reported, never 100% claimed.

## 16. Abstention / "I Don't Know"

Pre-generation gate (top score < τ OR no query identifiers in top-k → abstain with closest evidence) + in-generation `insufficient_evidence:true` as rewarded first-class output + post-generation validator fail → abstain. Calibrate τ on ~6 unanswerable / 30 total. Report false-answer vs false-abstain rates; AwF precision/recall [Research]. Include intentionally unanswerable set (e.g. "where is billing?" in repo without billing; future-version questions).

## 17. Architecture Reconstruction

Static-first, LLM-second: entrypoints (routes, main, compose services, package scripts) → import graph (dependency-cruiser/ts-morph, pydeps) → fan-in/out + dir clustering (Bunch/ACDC-style, or simple dir+edge density) → role classify (controllers/services/models/migrations) → external systems (ORM/DB drivers, queues, env keys) → LLM names/groups from structured model + summaries (not raw repo) → Mermaid flowchart/C4 + React Flow, every node click→file:line@SHA. Cache `diagram.mmd + context.md` per component (oh-my-mermaid pattern) [Observed Practice]. Validate Mermaid syntax with mermaid-cli (LLMs hallucinate brackets).

## 18. Guided Flow Tours (hardest feature)

Graph-constrained LLM tour (feasible): retrieve seeds (`signup|register|create_user` + route tables) → BFS on def/call index from handler, depth 3–5, fan cap → ordered candidate symbols with ranges → LLM to `{steps[{title, explanation, evidence[]}]}` → validator drops evidenceless steps → stepper UI + sequenceDiagram; mark ambiguous hops "not sure". Precompute 3–5 flows (signup, login, main CRUD, background job). Runtime tracing (OTel) = ground truth but requires runnable app + collector + seed traffic → **Future** (optionally verify tour by running a test and capturing stack). Static-only risks framework-magic misses; LLM-only hallucinates; static+runtime ideal but out of scope.

## 19. "Why Does This Exist?"

Code shows what/how, not intent. Tiers: provable (call sites, config) → inferred design (label "likely") → historical (needs commits/PRs/issues/blame) → unknown. Include lightweight history in MVP: `git blame + log --follow` age/author + top-3 commits per symbol; PR/issue bodies via `gh api` if network allowed, else "unknown — no PR found, low confidence". **Never present inference as fact** — provenance line (SHA/PR#/author/date) mandatory; separate UI section "Inferred rationale".

## 20. Starter Task Generation

Signals ranked: `good first issue / help wanted` labels (best, via GitHub API) > missing tests (public fn, 0 test refs; coverage if available) > TODO/FIXME/HACK age-graded (todocheck/todoaudit pattern) > lint/Semgrep/CodeQL unused findings > validation gaps (handler without Pydantic/schema) > docs gaps > a11y. Scoring: `difficulty=f(files, LOC, fan-in, modules, tests?)`, `risk=f(fan-in, DB/security keywords, public API?)`, prerequisites (ORM/async/auth). LLM writes description+acceptance from evidence; validator confirms files/lines. Present 5–10 sorted easy→hard with "read these files first" (tour links). No hour estimates.

## 21. Incremental Documentation

Every artifact stores `(commit_sha, [source hashes])`. Triggers: GitHub/Lab webhook `push` (demo) > CI step calling ingest (private, no inbound) > post-merge hook (local) > poll fallback (air-gap). Pipeline: `git diff --name-status old new` → re-parse/re-chunk changed files → compare content hashes → re-embed only new/changed → delete removed vectors → update symbols/edges → invalidate dependents (artifacts whose dep-set ∩ changed ≠ ∅ + 1-hop importers) → lazy regen summaries/arch/tours (re-validate cites first; regen only on fail) → UI badge "verified @SHA" + docs diff; optional bot PR. Full re-index only on embedder change. Webhook receiver: verify HMAC, dedupe ID, async enqueue, fast 2xx, DLQ.

## 22. Privacy / Government / Enterprise Deployment

| Model | Code leaves? | Fit |
|-------|--------------|-----|
| Cloud-only | yes (top-k only, redacted) | demo/MVP |
| Private cloud/VPC | to customer VPC LLM | enterprise default |
| On-prem | no | bank/gov data center |
| Self-host/air-gap | no, offline weights+wheels | defense/lab; webhooks→CI-push/manual sync |
| Hybrid | evidence→cloud, embeddings local | transition; must flag per-repo |

Egress = only model-gateway; Mode B compose `internal:true`, pre-pulled weights, telemetry off, blocked-egress CI test. Embeddings are NOT anonymized (inversion research) → same protection as source [Research].

## 23. Security Threat Model (repo = untrusted)

| ID | Threat | Mitigation (P/D/C) |
|----|--------|--------------------|
| T1 | Code to wrong destination (cloud on by accident, telemetry) | P: gateway hard-fail if cloud adapter in private mode; egress-blocked net; no analytics. D: outbound test in CI + audit provider per answer |
| T2 | Prompt injection in comments/README/docstrings | P: data-never-instructions delimiting + structured JSON only + **no tools/side-effects in Q&A path** (capability minimization per OWASP) + injection-pattern flag. D: guardrail-model screen (Llama Guard/ShieldGemma/Granite Guardian) + RAG-triad check. C: validator rejects uncited segments. Note: delimiting reduces, never eliminates [Official] |
| T3 | Exfil by crafted Q ("dump passwords") | P: ACL-inside-query + top-k cap + per-answer line cap + bulk-dump refusal + rate limits. D: audit anomaly alerts. C: redact secrets in prompts/UI |
| T4 | ACL bypass via cache/summary | P: deny-default, filter-in-query, derived artifacts inherit most-restrictive ACL, cache key includes permission hash, per-user memory. D/C: two-user/two-repo leak tests |
| T5 | Hallucinated cites | P/D/C: evidence IDs + validator + quote-check + abstention (§15–16) |
| T6 | Malicious repo (bombs, symlinks, submodules, parser DoS) | P: sandbox clone, no secrets, CPU/mem/time/size caps, no symlink escape, no submodule fetch default, **never execute repo code**, parser in separate process. D: resource logs. C: quarantine |
| T7 | Secrets in repo/history | P: gitleaks/detect-secrets pre-index, exclude `.env/keys/certs`, redact, refuse to quote. D: admin warn. C: purge on delete. Note: index tree only; history scan separate |
| T8 | Supply chain (libs, safetensors) | P: pin+hash, safetensors over pickle, vetted sources, Trivy, SBOM (Future) |
| T9 | Index tampering | P: auth on Qdrant/PG, isolated nets. D: chunk hash vs git blob at cite time. C: re-index |
| T10 | Stale answers | D: SHA on every answer + stale badge. C: lazy regen |

Secrets, disk (LUKS/KMS), TLS everywhere (Caddy/Traefik), OIDC/Keycloak prod (argon2 local demo), short JWTs, append-only audit (user/time/repo/q-hash/chunks/cites/provider/verdict; no full answers by default), TTL + purge path.

## 24. Local / On-Prem AI (2026, verified)

| Engine | License | Best for | 8 GB laptop verdict |
|--------|---------|----------|---------------------|
| **Ollama** (llama.cpp-based, GGUF) | MIT | single-user dev, 2-min setup, native Win/Mac/Linux, CPU offload | **MVP choice**: `qwen2.5-coder:7b` Q4 (~4.7–5.7 GB) |
| llama.cpp `llama-server` | MIT | max control, widest HW, GGUF 1.5–8bit | alt to Ollama; more flags |
| **vLLM** 0.24–0.30 | Apache-2.0 | multi-user serving (PagedAttention, 10–20× concurrent vs Ollama; RedHat 793 vs 41 tok/s) | **Not laptop**: 90–92% VRAM pre-alloc, WSL2-only on Win, needs 24 GB+; use for team server |
| **SGLang** 0.5.x | Apache-2.0 | agents/RAG prefix-reuse (RadixAttention, +29% H100, up to 6.4× TTFT on shared prefix) | same as vLLM — server tier |
| TensorRT-LLM 1.2 | Apache-2.0 | Blackwell NVFP4 max throughput, per-model compile (~28 min cold) | server/vendor-tuned only |

All expose OpenAI-compatible endpoints → one adapter covers them. Blackwell FP4 (NVFP4/MXFP4) needs Blackwell; on Ada/Hopper FP4 = weight-only via Marlin (no compute speedup).

## 25. RTX 5060 Feasibility (binding constraint)

**Specs [Official NVIDIA, May 2025]:** 8 GB GDDR7, 128-bit, 384 GB/s, 3328 CUDA, 572 AI TOPS, 45–100W, PCIe5/DP2.1a/DLSS4. Notebookcheck: GB206, slightly above 4060, VRAM is the ceiling.

| Model | Q4 weights + overhead | +KV 4–8k | +embed/rerank | 8 GB verdict |
|-------|----------------------|----------|---------------|--------------|
| Qwen2.5-Coder-7B Q4_K_M | ~5.7 GB [community/Ollama] | +0.5–1.5 GB | +0.5 GB (161–569M embed on CPU) | **Fits — comfortable default**; keep ctx 4–8k, `OLLAMA_NUM_PARALLEL=1`, embed on CPU |
| Qwen2.5(-Coder)-14B Q4 | 9.9 GB base / 12 GB coder | +1–2 GB | — | **Does NOT fit** — needs 12 GB+ box; lab-server tier |
| Qwen2.5-Coder-32B Q4 | 20–23 GB | — | — | 24 GB workstation only |
| gpt-oss-20b MXFP4 | ≥16 GB min [Official] | — | — | No (CPU-offload only, slow) |
| Qwen3-Coder-30B-A3B / Next-80B / 480B | 30–80B total weights (active 3–35B ≠ VRAM) | large | — | No (server/multi-GPU) |
| Embedders (jina-code 161M, bge-m3 569M) | 0.3–2.3 GB | — | — | **CPU-feasible**; keep off GPU when LLM loaded |
| Reranker 0.6B cross-enc | ~1–2 GB | — | — | skip in MVP (quality + VRAM) |

**Modes:** laptop-dev (7B Q4, ctx 4096, 1 user, ~30–60 tok/s, TTFT ~65–130 ms); lab-server (14B Q4/Q8, vLLM, multi-user); enterprise (32B+/MoE, multi-GPU, SGLang/vLLM). Never claim laptop serves teams — Ollama serializes (c1≈c8 throughput) while vLLM batches [Research].

## 26. Model Comparison (cloud + local, verified)

| Model | Ctx | Price / license | Strength for us | Concern |
|-------|-----|-----------------|-----------------|---------|
| Claude Sonnet 5/5.5 | 1M, 128k out [Official] | $2 in / $10 out per MTok; cache read $0.20; batch −50% [Official Aug 2026] | best cite-or-abstain discipline + structured output; long ctx | egress; cost (~$0.01–0.03/query at 5–10k in + 1k out) |
| GPT/Gemini-class | 128k–1M | similar $$ | comparable | same privacy |
| Qwen2.5-Coder-7B | 128k (32k YaRN-stable) [Official] | Apache-2.0 [Official] | **laptop fit**, strong code | weaker instruction-following; test abstention |
| Qwen2.5-Coder-14B/32B | same | Apache-2.0 (3B/72B = Qwen lic, verify) | quality↔VRAM steps | 12 GB / 24 GB min |
| Qwen3-Coder-30B-A3B / Next | 256k–1M | Apache-2.0 (verify per variant) | agentic coding SOTA-open | VRAM prohibitive locally |
| gpt-oss-20b/120b | 128k | Apache-2.0 [Official] | reasoning+tools, CoT+structured | 16 GB / 80 GB min |
| DeepSeek-V3-class MoE | 128k+ | verify (non-Apache history) | strong | host size + license |
| Llama-3.x 8B/70B | 128k | Community lic w/ conditions | ecosystem | less code-tuned; 70B server-only |

**Selection rule:** faithfulness-to-context + JSON-schema reliability > HumanEval. Run same 30-Q set on every candidate.

## 26b. Zero-Budget Cloud: Free Tiers (verified Oct 2026, re-verify demo week)

> Rule: free-cloud touches the **public demo repo only** (`allow_free_cloud=false` default; private repos hard-pinned to local). Free tiers train on prompts (Gemini states this explicitly [Official]) and quotas change often — precompute + cache tours/summaries night-before; local 7B is the graceful-degradation path on 429s.

| Provider | Free offer | Quota (official/do-not-exceed) | Card? | Role in $0 design |
|----------|-----------|-------------------------------|-------|-------------------|
| **Groq (primary free)** | Free dev tier [Official limits page] | 30 req/min, **1,000 req/day**; e.g. gpt-oss-20b/120b, qwen3.8-27b: **8K TPM / 200K TPD** [Official] | No | Expensive calls (arch summaries, tour narration) via OpenAI-compatible adapter; ~25–30 answers/day at 6k-in/1k-out — enough for judges + n≈10 study if cached |
| **Google Gemini API (fallback)** | Free tier: **free in+out tokens** [Official pricing] | Per-project RPM/TPM in AI Studio console; Flash-class ≈ 15 RPM / 10K req/day / 1M tok/day class (verify in console) | No | Frontier-quality fallback; same quota discipline; NEVER for private code (training-use + commercial-restriction terms [Official]) |
| OpenRouter `:free` | Free slots, one key | 20 req/min, **50 req/day** (1K/day after buying ≥10 credits) [Oct-2026 audit] | No | Emergency reserve only (~1 demo session) |
| Cloudflare Workers AI | 10k Neurons/day | Neuron-metered | Varies | Tiny-model edge alt; weak reasoning |
| HF Inference Providers | **$0.10/mo** credits, "subject to change" | Then paid | No | Eval sampling only |
| Cerebras | **$5 trial, 30 days, card required**, then pause [Official inference-docs] | 5 RPM / 30K TPM trial | **Yes** | **Excluded** from $0 plan (card required); old "1M/day free, no card" blogs are stale |
| GitHub Models | **Retired 30 Jul 2026** | — | — | Excluded |

**Quota math (Groq binding constraint is TPM, not req/day):** 200K TPD ÷ ~7k tokens/answer ≈ 28 answers/day. Plan: precompute 3 tours + arch + file summaries once (~10–15 calls), cache to disk, serve judges from cache + local Q&A. Retry/backoff on 429 → instant local-7B fallback (same evidence blocks, same validator, so output contract is unchanged).

## 27. Infrastructure Comparison

- **Backend:** Python 3.12 + FastAPI [Judgment] — tree-sitter/sentence-transformers clients, async SSE, Pydantic reused for LLM-schema validation + OpenAPI. Flask lacks async/validation; Node splits ML ecosystem.
- **Search lexical:** Postgres FTS (tsvector, fewer services) for MVP; OpenSearch/Tantivy only at scale.
- **Vector:** **Qdrant** (Apache-2.0, single container, payload filtering folded into HNSW traversal, int8/binarization → 290 MB vs 1.1 GB pgvector at 50k×1536, p95 9 vs 51 ms filtered [independent bench]) when ACL filtering matters; **pgvector 0.8** (HNSW + `hnsw.iterative_scan=strict_order` + `ef_search≥100`, else recall 0.41→0.94) when already on Postgres and <200k chunks; Chroma = prototype-only (no compression/sharding, L2 default trap); LanceDB = embedded disk-efficient alt (10M×1536 ≈ 60 GB disk, working-set RAM); Milvus/Weaviate = heavy/overbuilt for students.
- **RAG framework:** custom thin pipeline (`sentence-transformers`, `qdrant-client`, Pydantic). LlamaIndex OK as Stage-1 baseline lib; LangChain rejected (churn, opaque prompts — privacy audit pain).
- **Queue:** Postgres job table / FastAPI background worker; Redis/RQ only if needed.
- **Frontend:** React+TS+Vite + Tailwind + Monaco (line ranges) + Mermaid (text-diffable) + React Flow (interactive graph) + SSE streaming. Next.js unnecessary; CodeMirror alt.
- **DB:** PostgreSQL (users/repos/ACLs/chunks/FTS/symbols/edges/audit/jobs). SQLite demo-only.
- **Deploy:** Docker Compose (api/worker/pg/qdrant/ollama/web/proxy). K8s/Helm Future.
- **Auth:** local argon2 demo; OIDC/Keycloak prod.

## 28. Technology Stack Comparison (summary)

Covered in §27; full per-layer table is §36.

## 29. Licensing (verify before slides — all checked Oct 2026)

| Dep | License | Commercial |
|-----|---------|------------|
| Python/FastAPI/Pydantic | MIT/BSD | yes |
| tree-sitter + grammars | MIT (most grammars MIT) | yes; check per-grammar |
| bge-m3 / FlagEmbedding | MIT | yes |
| jina-code-v2 | Apache-2.0 | yes |
| Qwen2.5-Coder 0.5/1.5/7/14/32B | Apache-2.0; **3B+72B = Qwen License** [Official Ollama/HF] | yes except Qwen-licensed sizes (conditions) |
| Qwen3-Coder variants | Apache-2.0 (verify per size on HF) | yes if Apache |
| gpt-oss-20b/120b | Apache-2.0 [Official] | yes |
| Llama-3.x | Community (conditions, attribution) | conditional |
| Codestral | non-production restriction history | **verify — likely blocks commercial on-prem** |
| Voyage-code | proprietary API | cloud-only |
| Qdrant / LanceDB / Chroma / vLLM / SGLang / llama.cpp / Ollama | Apache-2.0 / MIT | yes |
| Postgres | PostgreSQL License (permissive) | yes |
| React/Vite/Monaco/Mermaid | MIT | yes |
| full-stack-fastapi-template / RealWorld | MIT | yes (demo fine) |

Distinguish **open-source (OSI) vs open-weights (weights available, use-limited) vs source-available**. Never say "open source LLM" for Apache-2.0 weights without noting weights≠code.

## 30. Repository Candidates (from scratch; contamination-aware)

Principle: small-medium app, auth/CRUD flows, tests+docs, permissive license, index in minutes.

| Candidate | Why | Risk | License |
|-----------|-----|------|---------|
| **fastapi/full-stack-fastapi-template** (45k★, MIT) [Official] | Py+React, auth/signup, SQLModel/PG, Docker, tests | very popular → memorized; template-clean (less pain) | MIT |
| **RealWorld Conduit FastAPI** (`borys25ol/fastapi-realworld-backend`, Py3.12/FastAPI/SQLA) | spec-standardized (cross-lang comparable), auth/articles | small; quality varies | verify (MIT-class) |
| **Mealie** (Py+Vue) | real product, domain flows | AGPL-3.0 (demo OK, redistribution caution), larger | AGPL-3.0 |
| Spring PetClinic | tiny, Java test | overexposed; less real | Apache-2.0 |
| Gitea/Forgejo, Mattermost, Superset | real pain | 100k+ LOC, too big for 1.5 wks | mixed |

**Recommendation [Judgment]:** primary = full-stack-fastapi-template (matches stack, fastest indexing); stress = Conduit-Express or Conduit-Spring (second language). **Contamination controls:** no-retrieval baseline; questions on recently-changed/less-known paths; file:line golds the model cannot guess; report delta (with-vs-without retrieval).

## 31. Evaluation (benchmarks — what transfers)

SWE-bench (issue→patch, agent efficiency), RepoBench/RepoEval (retrieval+pass@1), CrossCodeEval (multilingual), CodeRAGBench (retrieval→generation gap), CoIR (10-dataset retrieval), **CoREB (graded, contamination-limited search+rerank)**. None measures onboarding Q&A (arch/flow/why/starter-task). Use them for component choice (chunking, embedder), not product proof. Product proof = own gold set + user study (§33).

## 32. Baselines (minimum meaningful set for 1.5 wks)

B1 keyword/BM25-only; B2 vector-only; B3 hybrid (MVP); B4 free-tier long-context stuff (1–2 queries, quota-capped); B5 constrained agent (Stage 3); B6 no-retrieval local-7B-only (contamination check). Report recall@k + citation validity/support + correctness + false-answer rate. Expect B6 surprisingly strong on famous repos — that is the point (proves grounding value = B3−B6 gap).

## 33. Design Our Own Evaluation

- **Gold set (30, written before tuning):** 8 where/how, 6 arch, 6 flow, 4 why (2 answerable w/ history, 2 unanswerable-without-history), 6 unanswerable/no-evidence. Each: question, gold files+lines@SHA, rubric (correct/partial/wrong), required cites.
- **Retrieval:** recall@5/10, MRR, symbol-hit rate. **Grounding:** validity (must be 100%), relevance, support (NLI/judge), unsupported-claim rate. **Answering:** correctness, completeness, hallucination rate. **Abstention:** false-answer vs false-abstain. **Onboarding (crossover, n=8–12 newcomers, counterbalanced A/B, 6 tasks/condition):** time/question, correctness, file-location accuracy, arch-draw rubric, confidence 1–5 + calibration, SUS + free text, cite-click rate. **Limits:** n≈10 detects only large effects (Wilcoxon/effect sizes, report CIs); novelty + author-task bias; mitigate with pre-written rubric + blind scoring where possible.

## 34. Failure Modes (try to break it)

- Arch questions miss (top-k too narrow) → hierarchical summaries + drill-down, not bigger k.
- Why invented → history-or-unknown rule; separate inference UI.
- Line cites drift after commit → SHA-keyed + stale badge + re-validate.
- Weak local 7B rambles/ignores schema → JSON-mode + validator + repair-retry + cloud fallback; present quality gap honestly.
- Graph expansion adds noise (CodeGrep threshold!) → cap 1 hop, measure precision; disable if <0.45.
- Agent prompt-injected via code → read-only tools + validator + guardrail screen; red-team with injected comments.
- Docs go stale → hash invalidation, not timestamps.
- Scope explosion (all langs, K8s, SSO, OTel) → freeze: Py+TS, Compose, local-auth, static tours.
- Judge: "just RAG wrapper?" → answer: verified-grounding system + structure-aware index + measured abstention + incremental freshness; publish B3−B6 delta.

## 35. Scope Analysis (4 people, 1.5 weeks, $0 budget)

Must-ship: clone@index one repo, cAST chunks, hybrid+RRF+symbol, **local-7B Q&A default** + free-tier (Groq/Gemini) boost gated by `allow_free_cloud` (public repo only), validator+abstention, chat+Monaco cites, Mermaid arch, 30-Q harness, 3 precomputed+cached tours, static tasks, webhook-diff badge, ACL-basic + audit, egress-blocked test + free-tier kill-switch test (429 → local fallback). Stretch: on-demand tours, bot PR. Cut: paid APIs/VMs, SSO/SCIM, K8s/HA, precise LSP graphs, OTel runtime, multi-repo, entailment-in-prod, more langs. **Cost: $0** — electricity only; demo on localhost, no paid hosting.

## 36. Proposed Revised Architecture

```
Git repo ─▶ [Ingest worker: clone@SHA → filter → secret-scan → tree-sitter cAST parse]
                     │ chunks+symbols+imports+routes+hashes ─┬─▶ Postgres (text/FTS/symbols/edges/ACL/audit/jobs)
                     │                                       └─▶ Qdrant (vectors+repo/path/ACL payload; payload index BEFORE vector build)
                     │                                       └─▶ Summaries (file→dir→repo) + arch model
User ─▶ UI ─▶ API (authN/Z) ─▶ query analysis (identifiers/paths/routes)
   ─▶ hybrid retrieve (ACL INSIDE query) ─▶ RRF ─▶ [Stage3: 1-hop graph + conditional rerank/agent loop ≤4 turns]
   ─▶ evidence blocks [E1..En] (line-numbered, SHA-keyed)
   ─▶ Model gateway (local Ollama qwen2.5-coder:7b DEFAULT | free-tier Groq/Gemini iff allow_free_cloud=true, public repo only) ◀── ONLY egress point (hard-fail when private/local-only; kill-switch on 429 → local)
   ─▶ structured JSON {segments[{text, evidence[]}], insufficient_evidence}
   ─▶ VALIDATOR (IDs∃, ranges⊆, cited∀factual, quote-check) ─▶ repair-retry ×1 ─▶ answer+chips→Monaco@range ─▶ audit log
Push/CI webhook ─▶ diff ─▶ re-embed changed chunks ─▶ mark dependents stale ─▶ lazy regen + badge
```

**Trust boundaries:** browser↔API (authN/Z); API↔gateway (only code-exit; disabled in Mode B); worker↔repo (hostile, sandboxed, never-exec); tenant/repo isolation in stores (row+payload filters). **Model boundary:** only top-k evidence + query, redacted; never whole files/repo. **Storage:** PG (source text is secret-grade) + Qdrant (embeddings = secret-grade) + clones + cache (permission-hashed keys).

## 37. Proposed Revised Stack

| Layer | Recommended | Alternatives | Why | Evidence |
|-------|-------------|--------------|-----|----------|
| Backend | Python 3.12 + FastAPI | Flask, Node | parsing/ML eco, SSE, Pydantic schema reuse | Judgment |
| Parsing | tree-sitter (+config parsers) | LSP/SCIP/CodeQL | multi-lang, error-tolerant, exact lines | cAST/Observed |
| Chunking | cAST split-then-merge + summaries | fixed/line-only | +4.3 R@5 RepoEval, +2.7 SWE-bench | Research (EMNLP25) |
| Lexical | Postgres FTS | OpenSearch/Tantivy | fewer services | Judgment |
| Vectors | Qdrant (payload index first) | pgvector-only (simpler), Chroma (proto), LanceDB (embedded), Milvus/Weaviate (heavy) | filter-aware HNSW, int8 (290 MB vs 1.1 GB), p95 9 ms | Independent bench 2026 |
| RDB | PostgreSQL | SQLite demo | relational+FTS+audit | Judgment |
| Pipeline | custom thin | LlamaIndex (baseline lib) | cite/ACL/egress control | Judgment + Cody lesson |
| Embed | jina-code-class (verify latest) else bge-m3 | Voyage (cloud) | code-trained, 0.3 GB CPU | CoREB/Official |
| Rerank | none in MVP | Qwen3-0.6B/CoREB-tuned (Stage 3) | off-shelf hurts | CoREB Research |
| Cloud LLM | Free-tier Groq (`qwen3`/`gpt-oss-20b`, 30rpm/1K-day, 8K TPM/200K TPD) primary-free; Gemini Flash fallback (free in+out, verify quota in AI Studio) — public-repo ONLY, default OFF | Claude/GPT paid (excluded at $0) | $0 within quotas; OpenAI-compatible so one adapter; re-verify quotas demo week | Official rate-limit + pricing pages, Oct-2026 audit |
| Local LLM | Qwen2.5-Coder-7B Q4 via Ollama (DEFAULT) | Qwen3-4B/8B dense (test) | only comfortable 8 GB fit; graceful fallback on 429 | Official VRAM math |
| Serving | Ollama (laptop, default) | vLLM/SGLang (server only, out of $0 scope) | DX vs throughput; WSL2-only vLLM on Win | Bench 2026 |
| Diagrams | Mermaid + React Flow | D2/Cytoscape | text-diffable, LLM-friendly | Observed |
| Frontend | React+TS+Vite+Monaco | Next/CodeMirror | ranges + streaming | Judgment |
| Auth | local argon2 → OIDC/Keycloak | Authentik | private-deploy fit | Judgment |
| Deploy | Docker Compose, localhost demo (no paid hosting) | K8s Future | $0; pre-indexed volumes + Ollama model cache shipped on disk | Judgment |
| Secrets | gitleaks + Docker secrets (no Vault SaaS) + redact-before-free-cloud | detect-secrets | pre-embed scan; free-tier trains on prompts so redact | Observed |
| Cost | **$0 total** (electricity only) | — | no paid tokens/VMs/DBs; quotas: Groq ~28 answers/day, OpenRouter 50/day reserve; cache-first demo | §26b |

## 38. Decision Matrix

| Decision | A | B | C | Winner | Reason |
|----------|---|---|---|--------|--------|
| RAG vs agentic | pure RAG | free agent | **constrained agent (orchestrated tools)** | C | follows chains, cites stay valid; CodeGrep/Morph |
| Vector-only vs hybrid | vector | **hybrid+symbol** | hybrid+graph | hybrid now, graph Stage 3 | identifiers need lexical; graph needs precision gate |
| Tree-sitter vs semantic | **tree-sitter primary** | LSP-only | SCIP/LSIF | tree-sitter (+enrich later) | uniform, tolerant, exact lines |
| Graph vs no graph | none | **1-hop import/symbol** | full GraphRAG | 1-hop Stage 3 | full KG expensive/unstable |
| Local vs cloud | paid cloud-only | local-only | **local-default + free-tier boost (public repo only)** | C ($0) | privacy + quota honesty; kill-switch to local |
| Rerank vs none | rerank default | **none (MVP)** | conditional | none→conditional | CoREB harm |
| Custom vs framework | **custom thin** | LangChain | LlamaIndex-full | custom (+LI baseline) | audit + cite control |
| PG vs separate search | PG-only | **PG+Qdrant** | +OpenSearch | PG+Qdrant (or PG-only if time) | ACL filtering wins; PG-only acceptable cut |
| Qdrant vs pgvector | **Qdrant** | pgvector | Chroma/LanceDB | Qdrant (filtering); pgvector if <200k + PG-shop | bench 2026 |
| Local LLM | 7B Q4 | 14B Q4 | 20B+ MoE | **7B Q4 laptop** | 5.7 vs 12 vs 16+ GB |
| Embedding | **code-small** | bge-m3 | cloud | code-small, bge fallback | CoREB specialization |

## 39. Stage 1 Plan (presentation)

Problem/personas, arch diagram, grounding story (IDs+validator+abstention+faithfulness caveat), dual-mode privacy (egress point + ACL-inside-query), 5-Q spike results, repo pick + contamination plan, 1.5-wk scope + NOT-build list. Mock/recorded demo + live cite-click if ready.

## 40. Stage 2 Plan (online prototype, 4 people × 1.5 wks)

1. Clone/filter/secret-scan (0.5d). 2. cAST chunks + ranges + PG schema (2d). 3. Embed (jina-code, CPU) + Qdrant (or pgvector-only to cut scope) + FTS + RRF + ACL filter (2d). 4. Gateway (**local-7B first**, free-tier Groq/Gemini behind `allow_free_cloud`, OpenAI-compatible) + evidence assembly + JSON schema (1.5d). 5. Validator + abstention + 30-Q harness + baselines B1/B2/B3/B6 (+B4 = free-tier long-context, 1–2 queries) (2d). 6. UI chat+stream+chips+Monaco + arch page (3d, parallel). 7. Localhost demo: pre-index + precompute/cache tours, no arbitrary upload, quota test + 429→local kill-switch test + egress-blocked test (1d). Total ≈ 12 person-days + buffer; parallelize UI vs index.

## 41. Stage 3 Plan (finale; prep before clock)

Pre-built: tours + tasks + incremental pipeline + local fallback + study protocol/consent. During: polish 3 tours + tasks, live commit→stale→regen demo, 6–10 person crossover study, results + B-deltas. Recorded backup + cached tours for network failure.

## 42. Implementation Order

Clone→filter→scan → parse/chunk (unit-test line map) → PG → embed/Qdrant+FTS → hybrid+RRF+ACL → gold set + recall@k → gateway → evidence+prompt+schema → validator+abstention → UI → arch/Mermaid → auth/audit → tours → tasks → incremental → private-packaging + study.

## 43. What NOT to Build (essential)

SSO/SAML/SCIM, per-dir ACL sync, K8s/HA, precise LSP call graphs, runtime/OTel tracing, multi-repo federation, air-gap signed bundle/SBOM, fine-tuned embedder/reranker, arbitrary-repo public upload, more than Py+TS initially, entailment-in-prod, hour-accurate difficulty.

## 44. Novelty / Differentiation (honest)

Common: chunk+RAG chat, Mermaid diagrams. Interesting combo: parser-facts + hybrid + verified cites + measured abstention + hash-freshness + dual-mode with stated boundaries. Potentially novel: newcomer-calibrated explanations with per-step evidence + uncertainty + starter-task→tour linkage; AwF-style faithfulness reporting on code QA. Research-worthy: precision-threshold-gated agentic retrieval for onboarding; faithfulness (not just correctness) metrics for code cites. Do not claim "novel RAG" — claim **verifiable onboarding**.

## 45. Risks

Over-scope (high) → freeze scope; weak 7B quality (med) → small-context prompts + per-step calls + precomputed cache + honest gap; free-tier 429/quota change (med) → cache-first + local fallback + re-verify quotas demo week; free-tier trains on prompts (high for private code) → public-repo-only flag + redact + banner; demo net fail (med) → pre-index + offline local + recording; privacy over-claim (med) → egress test; contamination (med) → B6 + recent-change Qs; tiny biased study (high) → crossover + limits; tree-sitter call noise (med) → "likely" labels; infra time-sink (med) → Compose-first + CI smoke.

## 46. Judge Questions (34)

1. Why not ChatGPT+RAG? → Ours: SHA-keyed IDs, validator, abstention with measured rates, ACL-inside-query, freshness — publish B3−B6 gap.
2. Why not stuff whole repo in 1M ctx? → quota (Groq 8K TPM/200K TPD free; Gemini per-project caps), lost-in-middle, no ACL granularity, impossible on 8 GB local; useful only as B4 baseline (1–2 queries).
3. Why embeddings at all (Cody dropped them)? → single-repo + offline + symbol-boost; Cody scale ≠ our scale; we keep lexical+symbol so we degrade gracefully.
4. Why not embeddings-only? → identifiers/literals need lexical; CoREB keyword collapse.
5. Why graph? → 1-hop only, precision-gated (CodeGrep threshold); full GraphRAG deferred as expensive/unstable.
6. Guarantee cites? → 100% validity by construction (IDs+validator); support measured (quote-check+NLI sample), never claimed 100%; 57% post-rationalization caveat disclosed.
7. Answer not in code? → abstain + closest evidence + missing-desc; false-answer rate reported.
8. Leak confidential code? → top-k redacted only via gateway; Mode B egress-blocked + tested; embeddings treated as secret; permission-hashed caches.
9. Malicious comment injection? → data-not-instructions + no-tool Q&A + validator + guardrail screen; red-team set; OWASP LLM01 controls; delimiting ≠ proof.
10. Why trust for gov? → boundaries named (retrieval ACL, gateway egress, no-exec worker), audit log, TTL/purge, reproducible egress test — not "self-hosted = secure".
11. Code changes? → hash invalidation + 1-hop regen + SHA badge; demo live commit.
12. Arch diagram correct? → built from import/routes facts; LLM only names; nodes click to code; syntax-validated.
13. Infer why? → we don't, without history; blame/PR links or "unknown, low confidence".
14. 1M LOC? → sharded index, summaries, Qdrant scale; laptop demo is single mid-size repo; server tier for large.
15. Offline? → Mode B: 7B + local embed + Qdrant + PG, pre-pulled, no egress (quality gap disclosed).
16. Weak local model? → local 7B is DEFAULT (small ctx + JSON-mode + validator + repair-retry + abstain); free-tier Groq/Gemini boosts public-repo quality; side-by-side eval shows gap honestly.
31. Free tier trains on our code? → yes (Gemini states it) — hence public-repo-only flag, redact-before-send, banner, audit of what left the network; private repos hard-pinned local.
32. Free quota runs out mid-demo? → cache-first (tours/summaries precomputed night-before); 429 → instant local fallback, same output contract; Groq ~28 answers/day suffices with caching; OpenRouter 50/day reserve.
33. Why Groq primary, not Gemini? → code-model lineup (qwen3/gpt-oss) + OpenAI-compatible + fastest free inference; Gemini = fallback (frontier quality, 1M ctx, but training-use terms).
34. What's genuinely novel? → not RAG — verifiable onboarding: validated cites + abstention metrics + tour↔task linkage + freshness proofs.
17. Why this model? → on-repo 30-Q faithfulness+schema test, not leaderboard; VRAM math shown.
18. Why this DB? → filtered p95/recall bench (Qdrant 9 ms/0.96 vs pgvector-tuned 51 ms/0.94 vs default 0.41); PG-only acceptable cut <200k.
19. Why this parser? → uniform + tolerant + exact lines (cAST +4.3 R@5); LSP precise but heavy.
20. Why no LangChain? → opaque prompts hurt privacy audit; custom = control cites/ACL/egress.
21. Why no reranker? → CoREB harm (−22%); enable only if on-repo gain.
22. Reranker GPU cost? → +1–2 GB +300 ms; skipped in MVP.
23. 14B on 8 GB? → No — 9.9–12 GB needed; 7B only comfortable; math shown.
24. gpt-oss-20b locally? → No on 8 GB (16 GB min, MXFP4).
25. Qwen3-30B-A3B "only 3B active"? → active ≠ VRAM; 30B total weights must load.
26. Embedding inversion? → vectors = secret-grade, same protections.
27. Cross-user leak via summary/cache? → most-restrictive ACL inheritance + permission-hashed keys + leak tests.
28. Bulk dump ("list passwords")? → line caps + refusal + rate limits + top-k structural limit.
29. Training contamination? → B6 baseline + recent-change Qs; delta proves grounding.
30. What's genuinely novel? → not RAG — verifiable onboarding: validated cites + abstention metrics + tour↔task linkage + freshness proofs.

## 47. Final Recommendation

**Build the constrained-pipeline system in §36 with the stack in §37 at $0: embedder = code-specialized small (jina-code-class, bge-m3 fallback, CPU), no reranker, local Qwen2.5-Coder-7B/Ollama DEFAULT + free-tier Groq (primary) / Gemini Flash (fallback) gated by `allow_free_cloud` for the public demo repo only, repo = full-stack-fastapi-template (+ Conduit stress), eval = 30-Q gold (local) + crossover n≈10, demo = localhost precomputed-cache-first.** Paid Claude/GPT, Cerebras (card-gated trial), GitHub Models (retired) are excluded. This is the only configuration that (a) costs $0, (b) fits 8 GB, (c) respects 2026 retrieval evidence, (d) meets the grounding requirement with measurable honesty, and (e) ships in 1.5 weeks with 4 people. Everything else is Stage-3 or Future.

---

### Sources (selected, accessed Oct 2026)

- NVIDIA 50-series laptop specs (8 GB GDDR7 5060, 384 GB/s) + May-2025 availability — nvidia.com; Notebookcheck GB206/100W.
- Qwen2.5-Coder HF cards (sizes, 128k ctx, Apache-2.0, vLLM advice); Ollama library sizes; canitrun VRAM table (7B 5.7 GB, 14B-Coder 12 GB, 32B 23 GB Q4).
- Qwen3-Coder HF/GitHub (480B-A35B, 30B-A3B, Next-80B-A3B, 256k) — huggingface.co/Qwen, github.com/QwenLM/Qwen3-Coder.
- OpenAI gpt-oss (20b ≥16 GB, 120b 80 GB, MXFP4, Apache-2.0) — openai.com, github.com/openai/gpt-oss, cookbook run-locally.
- Claude pricing/context (Sonnet 5 $2/$10, 1M ctx, cache $0.20, batch −50%) — platform.claude.com docs + Aug-2026 rate card.
- bge-m3 (569M/1024/8k, MIT) — HF + FlagEmbedding GitHub; jina-code-v2 (161M/768/8k, Apache-2.0, 30 langs) — HF + jina.ai.
- cAST EMNLP-2025 Findings (tree-sitter, +4.3 R@5 RepoEval, +2.7 SWE-bench) — aclanthology.org.
- CoREB May-2026 (specialized 0.5B > general 8B, keyword collapse, rerank harm) + CodeRAG-Bench (limitations on SWE/RepoEval) — arxiv + github hq-bench/coreb.
- CodeGrep Aug-2026 (RL retriever, precision threshold 0.45–0.68, 23 rounds/631k tok baseline) — arxiv 2608.05886; SWE-agent/OpenHands repos; Agentic RAG survey 2501.09136; Morph agentic-search 2026-02.
- Sourcegraph Cody (BM25-adapted+RRF, dropped embeddings for Enterprise, RBAC/filters) — sourcegraph.com/blog + docs.
- Qdrant vs pgvector vs Chroma vs LanceDB (filter-aware HNSW, iterative_scan fix 0.41→0.94, int8 290 MB vs 1.1 GB, p95 9 vs 51 ms) — 4xxi Mar-2026, iotdigitaltwinplm Aug-2026, drpranayjha Jul-2026, pythondatabench Jul-2026, salttechno Feb-2026.
- Serving (Ollama single-user vs vLLM/SGLang 10–20× concurrent, 90% VRAM pre-alloc, WSL2-only vLLM, Blackwell NVFP4) — marti.ai Aug-2026, joshua8.ai Jan-2026, Kuo Apr-2026, insiderllm Feb-2026, eurokommerz Sep-2026, qdna.fr 2026.
- Citation faithfulness (57% unfaithful, correctness≠faithfulness ICTIR-2025; franq; AwF precision/recall; error-tolerant attribution) — dl.acm.org, arxiv 2505.21072, aclanthology 2025.
- OWASP LLM Top-10 2025 (LLM01 injection, RAG does not fix) + prompt-injection cheat sheet (delimiters≠boundary, least-privilege, HITL) — genai.owasp.org, owasp.org PDF, cheatsheetseries.
- Arch/tours/tasks/docs (ARCADE/Bunch, dependency-cruiser, CodeQL CallGraph, Joern CPG, OTel, blame+PR pattern, todocheck/todoaudit, webhook ISR) — subagent synthesis + official docs.
- full-stack-fastapi-template (45k★ MIT) + Conduit-FastAPI — github.com.
- Free tiers (Oct 2026): Groq rate limits (30rpm/1K-day, 8K TPM/200K TPD) — console.groq.com/docs/rate-limits; Gemini free-tier pricing (free in+out, training-use note) + rate-limit/billing docs — ai.google.dev/gemini-api/docs/{pricing,rate-limits,billing}; Cerebras trial ($5/30d/card, no permanent free) — inference-docs.cerebras.ai + cerebras.ai/pricing; GitHub Models retired 30 Jul 2026 + 6-provider free-tier audit (Oct-3-2026) — freellm.today; no-card free-API ranking (Sep-26-2026) — opengpuradar.com; flywheel free-tier analysis (May-2026) — wetheflywheel.com.

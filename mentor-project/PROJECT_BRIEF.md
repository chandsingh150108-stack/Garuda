# Codebase Mentor — Project Brief (Student Cheat-Sheet)

> Read this once and you can demo + defend the project to any judge.
> Status Oct 2026: Phases 0–22 DONE, project COMPLETE pending final-acceptance review in `mentor-project/`. Spec: `../CODEBASE_MENTOR_EXECUTABLE.md` v1.0 (wins on conflict). Research history: `../Codebase Mentor Reassessment Report.md`. Pinned repo: `full-stack-fastapi-template@7257e60`.

## 1. 30-second pitch

"Codebase Mentor is a local-first AI mentor that reads ONE real open-source repo at a pinned commit and helps a newcomer understand it — with every answer citing exact `file:lines`. If the code doesn't contain the answer, it abstains instead of hallucinating. It runs for $0, offline, on a student laptop."

Say this early: **facts come from a deterministic index, language comes from the model, trust comes from a validator.** We are NOT 'ChatGPT over files'. We are verifiable onboarding.

## 2. Problem → solution

- **Problem:** newcomers drown in a new repo. Generic chatbots invent paths/lines. Tutorials go stale after one commit.
- **Users:** student joining an OSS project; judge checking grounding.
- **Solution (5 parts):**
  1. Grounded Q&A — ask anything, get segments each tied to evidence IDs.
  2. Architecture overview — deterministic component diagram, click node → code.
  3. Guided tours — e.g. "what happens on signup?" as validated steps.
  4. Why-answers with provenance — PROVEN / HISTORY / INFERRED / UNKNOWN.
  5. Starter tasks + freshness — 5-10 beginner tasks linked to tours; stale badge after edits.

## 3. Demo story (memorize these 5 beats = covers fixed 15-step runbook)

1. **"Pinned and current."** `mentor demo` → server on `127.0.0.1`, mode `LOCAL`, repo `full-stack-fastapi-template@<SHA>`, status current. This SHA is why cites are checkable.
2. **"Architecture from facts, not vibes."** Show Mermaid diagram (6+ components: entrypoint, api-layer, model-layer, frontend, db, config). Click a node → Monaco opens exact lines. Say: "LLM only wrote short labels; structure came from imports/routes."
3. **"Ask + click the proof."** Ask "How does signup work?" → answer has chips `[E1] [E2]` + provider label `LOCAL`. Click 3 chips → code view at exact range + SHA banner. If asked impossible ("where is billing?") → abstain panel with missing-evidence list, no fake cite.
4. **"Tours + Why + Tasks."** Open signup tour → stepper + sequenceDiagram, hops labelled `calls` (resolved) vs `likely calls, by name`. Ask Why → segments labelled; history shows `SHA/author/date` from blame/log or `UNKNOWN`. Show Tasks → sorted easy→hard, each with files+lines + "read this tour first".
5. **"Fresh + private."** Run scripted edit → old cite shows stale badge (hash mismatch). `mentor reindex` → <60s, only changed files re-parsed. Disconnect network → same question still answers as `LOCAL`. Show audit log: hashes + evidence IDs, no question text.

Fallback line: "If live inference fails, we serve precomputed cache labelled as cache. If browser fails, backup recording plays."

## 4. How it works (pipeline — draw this on board if asked)

```
Repo@SHA (untrusted, never executed)
 → INGEST: acquire --sha check → filters (allowlist exts, skip node_modules/.git/dist, >1MB, .env/keys) → secrets regex → manifest (path/size/sha256)
 → PARSE WORKER: child process, 10s timeout, 1MB cap → tree-sitter Py/TS (symbols/imports/routes/models) + YAML/TOML/JSON config → edges (resolved | likely)
 → INDEX: one SQLite file per repo (FTS5) — files/symbols/imports/edges/routes/chunks/artifacts/audit. Chunks = AST split-then-merge (cAST, ~512 toks), store text (cited) apart from embed_text (header+text). chunk_id = sha16.
 → RETRIEVE: analyze query (identifiers, /route/paths) → FTS5 BM25 identifier-split + symbol exact/prefix + path match → RRF-60 fusion → confidence (top score, identifier coverage, 2-retriever agreement)
 → EVIDENCE: E1..En server-numbered, line-numbered (`  12 | code`), ≤3000 toks, read from index not file
 → GATEWAY: llama-server 127.0.0.1 Qwen3-4B-Instruct Q4_K_M /no_think (G2 winner: 3.57GB, 22/22 valid, 82.9 tok/s) + Ollama adapter (documented default) (temp 0, JSON schema via format) | Groq/Gemini ONLY if allow_free_cloud + allowlisted_public + clean scan + redacted + budget — else CLOUD_BLOCKED → local
 → VALIDATOR V1-V9 + repair×1 → answer | abstain → API (FastAPI 127.0.0.1 only) + Web (React) → audit (hashes only)
FRESHNESS: git diff + content hashes → re-chunk changed files → invalidate dependents → lazy regen → stale badge
```

Key rules: model never writes paths/lines (server expands IDs); validator rejects uncited facts, bad IDs, `path:line` strings, URLs/HTML; one repair retry else abstain; abstention also pre-generation (low score/coverage) + pre-retrieval T3 `is_bulk_dump` refusal (no model call).
MODES: `MENTOR_MODE` LOCAL (default) / LOCAL-OFFLINE (cloud vetoed) / CLOUD-PUBLIC-DEMO (flag + allowlist). Demo cache: `mentor precompute` warms 8/10 answers + arch/tours/tasks (q03/q09 abstain on retrieval floor, never faked); offline 8/8 labelled.
REDTEAM (Ph-22): 13 families run, worst=medium F11 residual (10/18 reach model, validator + abstention backstop), 0 critical; G3 NOT ADOPTED (file-P@10 0.05 vs 0.45-0.68 band); G4 NOT ADOPTED; F12 B6 1/20 both copies (no memorization); support 8/8.

## 5. Tech-stack (all $0 — say this table from memory)

| Layer | Pick | Why | Cost |
|---|---|---|---|
| Lang/API | Python 3.12 + FastAPI + Pydantic, loopback only | parsing/ML eco, schemas reused for LLM validation | $0 MIT |
| Parse | tree-sitter Py/TS + PyYAML/tomllib | error-tolerant, exact lines, no build needed | $0 MIT |
| Chunk | cAST AST split-then-merge | cites align to syntax (+4.3 R@5 RepoEval, EMNLP25) | $0 |
| Store | SQLite + FTS5, one file/repo | zero daemon, native Windows, BM25 built-in | $0 public domain |
| Retrieve | FTS5 BM25 + symbol + path → RRF-60 | identifiers/routes need lexical; deterministic | $0 |
| Dense | OFF by default (G1 decides: bge-m3 MIT vs jina-v2-code) | leaderboards don't transfer; lexical is floor | $0 CPU |
| Reranker | NONE (G4 only) | CoREB: off-shelf hurts code (-22% worst) | — |
| LLM | Qwen3-4B-Instruct Q4_K_M via llama-server Vulkan (/no_think, 3.57GB peak @8K, 82.9 tok/s) + Ollama adapter | G2 winner on VRAM tiebreak over Qwen2.5-Coder-7B (4.70GB, 51.9 tok/s); both 22/22 valid; 7B stays qualified fallback | $0 Apache-2.0 |
| Serve | llama-server Vulkan single-user + `mentor serve` loopback-only | vLLM/SGLang need 24GB+ server, WSL2 on Win; Ollama remains documented adapter default | $0 MIT |
| UI | React+TS+Vite + Monaco readonly + Mermaid + plain CSS, plain-text answers + CSP | line ranges, no HTML XSS | $0 MIT |
| Cloud opt | Groq primary / Gemini fallback, default OFF | $0 boost for public demo only; quotas re-check demo week | $0 free-tier |
| Test/sec | pytest + Playwright + Bandit + pip-audit + npm audit, regex scanner required | free, auditable | $0 |

NOT used: Qdrant/Postgres (overkill single-user), LangChain (opaque prompts), 14B/32B (no VRAM fit), Tailwind/Next/Markdown-render (extra surface). G3 NOT ADOPTED (file-P@10 0.05 vs 0.45-0.68 band — stay hybrid RAG).

## 6. Grounding, privacy, eval — one-liners judges love

- **Grounding:** 100% citation *validity* by construction (IDs+validator, tested); *support* measured on sample, never claimed 100% (57% post-rationalization caveat).
- **Anti-memorization:** counterfactual repo (20 renames + 5 routes) + no-retrieval baseline B6; delta B3-B6 proves grounding.
- **Privacy:** default NOTHING leaves laptop; cloud only for allowlisted public repo after redaction; Gemini free trains on prompts → never private code; embeddings = secret-grade.
- **Security:** repo = hostile; no exec/eval/shell, no symlink/submodule follow, parameterized SQL, `realpath` confinement, `shell=False`, JSON cache (no pickle).
- **Eval:** 30-Q frozen gold (8 how / 6 arch / 6 flow / 4 why / 6 unanswerable) + Wilson intervals; study n=8-12 crossover, detects large effects only — report nulls.
- **Limits (say honestly):** Py+TS only; `likely` hops may be wrong; framework magic missed; 4B weaker than frontier (7B qualified fallback, uncompared on answer quality); file-P@10 0.05 conceptual floor; validator proves validity/containment, never entailment (q25 billing residual); 10/18 adversarial unanswerables reach model (validator + abstention backstop); study deferred n=0; free quotas volatile; history shallow → UNKNOWN; single-user isolation by files.

## 7. Judge Q&A (15 must-know)

1. **Why not RAG wrapper?** SHA-keyed IDs + validator + abstention rates + freshness + B3-B6 delta. 2. **Why not 1M ctx stuffing?** Groq 8K TPM cap, lost-in-middle, no ACL granularity, impossible on 8GB. 3. **Why embeddings at all (Cody dropped)?** Single-repo offline; we degrade to lexical gracefully. 4. **Why SQLite not Qdrant?** One user/repo, no daemon, FTS5 BM25; migrate only on failed latency gate. 5. **Why 4B not 7B/14B?** 14B Q4 ~8.4-9GB >8GB; G2 measured both 22/22 valid — 4B 3.57GB/82.9 tok/s beats 7B 4.70GB/51.9 tok/s on VRAM tiebreak; 7B stays qualified fallback. 6. **Why no reranker?** CoREB harm; G4 NOT ADOPTED (no vetted candidate, VRAM spent). 7. **Why no LangChain?** Opaque prompts hurt egress/ACL audit. 8. **Guarantee cites?** Validity 100% by construction; support sampled rate. 9. **Not in code?** Abstain + closest evidence + missing list. 10. **Leak private code?** Loopback, default-off, redaction, permission-hashed cache, egress-blocked test. 11. **Injection in comments?** Delimit + schema-only + no tools + validator + 20-payload corpus; delimiting reduces, not eliminates. 12. **Code changes?** Hash invalidation + stale badge + lazy regen. 13. **Offline?** LOCAL-OFFLINE + demo_cache, zero non-loopback proven. 14. **Contamination?** Counterfactual + recent-change Qs. 15. **Novel?** Not novel RAG — verifiable onboarding: validated cites + measured abstention + tour↔task linkage + freshness proofs.

## 8. Closing lines + don't-claims

- Close: "Largest permissive coder that fits the laptop, smallest infra that proves grounding, honest about what we don't prove."
- NEVER say: enterprise-grade / fully secure / self-hosted = secure / 100% faithful / hour-accurate difficulty.
- Point to: `DECISIONS.md` (A1-A18, G1-G4), `VALIDATION_REPORT.md`, `EVALUATION_RESULTS.md`, `SECURITY_THREAT_MODEL.md`, `docs/ARCHITECTURE.md`.

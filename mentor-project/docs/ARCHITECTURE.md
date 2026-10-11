# ARCHITECTURE (Phase 1 — matches DECISIONS A1-A18)

Product: verifiable repository onboarding (A1). Facts from deterministic index; language from model; trust from validator.

## Component diagram

```
Git repo@SHA (untrusted) ─▶ INGEST (acquire→filters→secrets→manifest)
  ─▶ PARSE WORKER (child proc, 10s timeout, 1MB cap; tree-sitter Py/TS + YAML/TOML/JSON) [A2]
  ─▶ INDEX (one SQLite/FTS5 per repo: files/symbols/imports/edges/routes/models/config/chunks/artifacts/audit) [A3/A4]
  ─▶ RETRIEVE (FTS5 BM25 identifier-split + symbol + path → RRF-60 → confidence signals; dense only if G1) [A5/A6]
  ─▶ EVIDENCE (E1..En server-numbered, line-numbered, ≤3000 tok) [A11]
  ─▶ GATEWAY (Ollama 127.0.0.1 Qwen2.5-Coder-7B Q4 default [A8/A17]; Groq/Gemini only if allow_free_cloud + allowlisted_public + clean scan + redaction + budget [A10])
  ─▶ VALIDATOR V1-V8 (+V9 Phase 14) → repair x1 → answer|abstain [A11/A12]
  ─▶ API (FastAPI 127.0.0.1 only) + WEB (React/Vite/Monaco-readonly/Mermaid/plain-text/CSP) [A15/A16]
FEATURES: arch (deterministic Mermaid) [A13] · tours (BFS d≤3 fan≤8, resolved|calls vs likely) · why (blame/log + PROVEN/HISTORY/INFERRED/UNKNOWN) · tasks (signals+scoring) · freshness (diff+hashes, lazy regen, stale badge) [A14]
```

Data flow per question: ask → analyze → lexical/symbol/path + RRF → confidence gate (tau) → evidence → gateway (JSON schema) → validator → server-expand cites → provider label + SHA + audit (hashes).

## Gates
- G1 embedding Phase 7 · G2 model Phase 8 · G3 agent Phase 22 · G4 reranker Phase 22. Procedures in DECISIONS.md.

## Honest limit (pre-Phase 9 placeholder, finalized Phase 9)
Validator guarantees citations exist, point to supplied evidence, quoted identifiers appear in cited text. It does not prove semantic entailment. Support measured separately, never claimed 100%.

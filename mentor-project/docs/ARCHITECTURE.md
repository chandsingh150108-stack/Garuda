# ARCHITECTURE (Phase 1 — matches DECISIONS A1-A18)

Product: verifiable repository onboarding (A1). Facts from deterministic index; language from model; trust from validator.

## Component diagram

```
Git repo@SHA (untrusted) ─▶ INGEST (acquire→filters→secrets→manifest)
  ─▶ PARSE WORKER (child proc, 10s timeout, 1MB cap; tree-sitter Py/TS + YAML/TOML/JSON) [A2]
  ─▶ INDEX (one SQLite/FTS5 per repo: files/symbols/imports/edges/routes/models/config/chunks/artifacts/audit) [A3/A4]
  ─▶ RETRIEVE (FTS5 BM25 identifier-split + symbol + path → RRF-60 → confidence signals; dense only if G1) [A5/A6]
  ─▶ EVIDENCE (E1..En server-numbered, line-numbered, ≤3000 tok) [A11]
  ─▶ GATEWAY (loopback-only; Qwen3-4B Q4_K_M @8192 via llamacpp-vulkan per G2, Ollama documented default [A8/A17]; Groq/Gemini only if allow_free_cloud + allowlisted_public + clean scan + redaction + budget [A10])
  ─▶ ANSWER LAYER p9v1 (evidence → contract → validator V1-V8 → 1 repair → answer|abstain; pre-gate τ_score=0.02) [A11/A12/D9.4]
  ─▶ API (FastAPI 127.0.0.1 only) + WEB (React/Vite/Monaco-readonly/Mermaid/plain-text/CSP) [A15/A16]
FEATURES: arch (deterministic Mermaid) [A13] · tours (BFS d≤3 fan≤8, resolved|calls vs likely) · why (blame/log + PROVEN/HISTORY/INFERRED/UNKNOWN) · tasks (signals+scoring) · freshness (diff+hashes, lazy regen, stale badge) [A14]
```

Data flow per question: ask → analyze → lexical/symbol/path + RRF → confidence gate (tau) → evidence → gateway (JSON schema) → validator → server-expand cites → provider label + SHA + audit (hashes).

## Gates
- G1 embedding Phase 7 · G2 model Phase 8 · G3 agent Phase 22 · G4 reranker Phase 22. Procedures in DECISIONS.md.

## Honest limit (Phase 9, LOCKED — spec wording)
The validator guarantees that citations exist, point to supplied evidence, and that identifiers quoted by the model appear in the cited text. It does not prove that the cited code semantically entails the claim. Support is measured separately in Phase 22 by an entailment-style judge on a sample, and reported as a rate, never as 100%.

Why this limit is structural: ICTIR 2025 (Wallat et al.) shows correctness ≠ faithfulness — up to 57% of citations in attributed QA are post-rationalized (genuine-looking but unfaithful). Our validator enforces citation validity (existence, containment) by construction; faithfulness is approximated by the quote-check (V4), the sufficiency gate (abstention), and the no-retrieval baseline — never guaranteed. NLI-style entailment checks cannot close the gap either: factual support routinely holds without semantic entailment (FactRel/StarSEM 2024: 84% of factually-supporting pairs are not NLI entailment), and retrieved premises break NLI's reference-determinacy assumption (RefNLI 2025).

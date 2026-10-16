# Codebase Mentor (mentor-project)

Local-first AI mentor: indexes one OSS repo at pinned SHA, grounded Q&A with exact file:line cites, abstention, tours, tasks. Runs for $0.

- Spec: `../CODEBASE_MENTOR_EXECUTABLE.md` (v1.0 wins on conflict)
- Research: `../Codebase Mentor Reassessment Report.md`
- PROJECT_ROOT: this folder (`mentor-project/`)
- Zero-cost (evidence: `DECISIONS.md` A-G gates, `VALIDATION_REPORT.md`, `EVALUATION_RESULTS.md`): Python venv + SQLite FTS5 + llama-server + Qwen3-4B-Instruct Q4_K_M (G2 winner, Apache-2.0, fits 8 GB); no paid APIs, VMs, or hosted DBs required. Cloud (Groq/Gemini free tiers) is opt-in, public-repo-only, default OFF.
- Local-first (evidence: `tests/test_offline.py`, `tests/test_no_keys.py`, `scripts/offline_check.py`): default NOTHING leaves the laptop; `MENTOR_MODE=LOCAL-OFFLINE` vetoes cloud unconditionally; demo runs from precomputed cache (`mentor precompute`, 8/10 answers cached + labelled).
- Status: Phase 22 PASSED 2026-10-17 (all 23 phases; red team worst=medium, 0 critical; G3/G4 NOT ADOPTED; support 8/8; study pre-registered DEFERRED n=0). See `PROJECT_STATUS.md`.
- Known limitations (honest, measured): Py+TS only; `likely` call-hops may be wrong (labelled); file-P@10 0.05 — conceptual questions often miss (lexical floor); validator proves citation validity/containment, never semantic entailment (q25 billing residual); 10/18 adversarial unanswerables reach the model (validator + abstention are the backstop); user study deferred (no pool); free-cloud quotas volatile (re-verify demo week).

## Quick start (target laptop)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m mentor.cli index --repo data/repos/fst --sha 7257e606cb94eada1dca40173e2b7f99dd549bc6 --out data/indexes/fst.sqlite
python -m mentor.cli serve --index data/indexes/fst.sqlite
```

Model weights (one-time, free): `python scripts/fetch_llm.py` (Qwen3-4B GGUF + llama-server Vulkan build into `data/models/`).
Demo cache (one-time, local inference): `python -m mentor.cli precompute --install`.
Offline proof: `python scripts/offline_check.py` (expect 8/8 cached, 0 non-loopback).

## Modes

| `MENTOR_MODE` | Network | Cloud | Use |
|---|---|---|---|
| `LOCAL` (default) | loopback only | iff `ALLOW_FREE_CLOUD=true` + allowlisted public repo | daily use |
| `LOCAL-OFFLINE` | loopback only | never (vetoed) | venue demo, private code |
| `CLOUD-PUBLIC-DEMO` | loopback + pinned providers | armed only with flag + allowlist | public-repo quality boost |

## Tests

```
pytest tests/ -q                      # full suite (unit + integration + security)
cd web && npm test                    # vitest (chip + answer rendering)
cd web && npx playwright test         # e2e (needs `mentor serve` + model server)
powershell -ExecutionPolicy Bypass -File scripts/security_check.ps1
```

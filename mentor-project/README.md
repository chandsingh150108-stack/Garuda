# Codebase Mentor (mentor-project)

Local-first AI mentor: indexes one OSS repo at pinned SHA, grounded Q&A with exact file:line cites, abstention, tours, tasks. Runs for $0.

- Spec: `../CODEBASE_MENTOR_EXECUTABLE.md` (v1.0 wins on conflict)
- Research: `../Codebase Mentor Reassessment Report.md`
- PROJECT_ROOT: this folder (`mentor-project/`)
- Zero-cost: Python venv + SQLite FTS5 + Ollama + Qwen2.5-Coder-7B Q4; no paid APIs required.
- Status: Phase 0 in progress. See `PROJECT_STATUS.md`.
- Evidence: `RESEARCH_LOG.md`, `DECISIONS.md`, `VALIDATION_REPORT.md`, `EVALUATION_RESULTS.md`.

## Quick start (target laptop)
```
python -m venv .venv
.venv\Scripts\activate
python scripts/probe_env.py > docs/hardware_probe.json
pytest tests/test_probe.py -q
```

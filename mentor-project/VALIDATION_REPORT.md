# VALIDATION_REPORT

| Date | Phase/Gate | Command | Result | Notes |
|---|---|---|---|---|
| 2026-10-08 | Phase 0 probe | `python scripts/probe_env.py` | PASS | Dev RTX 4050 6GB (6141 MiB, free 5858), driver 581.57, power.limit N/A / max 75W, Python 3.14.0, Node v24.19.0, Ollama client 0.34.0 no daemon, disk 51.82GB free. NOT target (RTX 5060 8GB pending). |
| 2026-10-08 | Phase 0 | `pytest tests/test_probe.py -q` | PASS 1/1 | Valid JSON, all 14 keys present |
| 2026-10-08 | Phase 1 | `pytest tests/test_decisions.py -q` | PASS 3/3 | 18 A-entries with status/evidence/reason/confidence/fallback; G1-G4 name procedure + results file |
| 2026-10-08 | Phase 1 security | paid-dependency check | PASS | No LOCKED decision requires paid API/DB/VM; cloud (A10) optional default-off with local fallback |

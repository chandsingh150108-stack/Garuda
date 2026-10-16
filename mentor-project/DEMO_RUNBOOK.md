# DEMO_RUNBOOK (Phase 21 — complete; sequence fixed by D21.1)

Setup (once): `pip install -r requirements.txt` · `python scripts/fetch_llm.py`
(weights + llama.cpp into `data/models/`) · `python -m mentor.cli index …`
· `python -m mentor.cli precompute --install` (model server up once) ·
`cd web && npm install && npm run build`.

Run: `python -m mentor.cli demo` (verifies, prints steps, opens `/ask`,
serves loopback). Pre-flight: `python scripts/demo_check.py` (gate: 9/9).
Timings below are measured on the target laptop (RTX 5060 8 GB).

| # | Step | Expected | Timing |
|---|---|---|---|
| 1 | `mentor demo` | server on 127.0.0.1:8000, `mode=LOCAL`, index verified @7257e606cb94 | serve boot ~2 s |
| 2 | Open repo | name `fst`, SHA banner, status `current` | <0.5 s |
| 3 | Architecture | 8-component diagram; node click → code | <0.5 s (cached model) |
| 4 | Ask signup | 1 segment, 6 evidence chips, `LOCAL` | ~1 s live / <0.1 s cached |
| 5 | Signup tour | 8 validated steps + sequence diagram, resolved/`likely` hops | <0.5 s (precomputed) |
| 6 | Click 3 chips | code view at exact lines + `@ 7257e606cb94` | <0.5 s each |
| 7 | Ask why (auth) | HISTORY segment with commit cite (or INFERRED section) | ~1–3 s live |
| 8 | History provenance | `689d7105`-style SHA + author + date | with step 7 |
| 9 | Ask billing (impossible) | abstain + missing list + closest; NO fake cite | pre-gate <0.5 s or honest residual |
| 10 | Starter tasks | 10 tasks easy→hard, files+lines + tour links | <0.5 s |
| 11 | `demo_live_edit.py` | edited citation → `stale` badge | edit instant |
| 12 | `mentor reindex` | 1 file re-parsed (measured 0.68 s scratch case) | <60 s gate |
| 13 | Refreshed answer | new cite at new lines | ~1 s |
| 14 | `MENTOR_MODE=LOCAL-OFFLINE` | same contract, provider `LOCAL` | 0 non-loopback (checked) |
| 15 | Audit log | hashes + evidence IDs + ranges; no question text | <0.5 s |

## Failure table (recovery for every listed failure)

| Failure | Recovery |
|---|---|
| Model server down / 429 | labelled cache serves (`· cached`); uncached → honest abstain; never faked (D21.2) |
| Browser fails to open/attach | `--no-browser` + backup recording plays (`docs/demo_recording.md`) |
| Port 8000 busy | `--port 8001` (loopback only; CORS origin unchanged for :8000 — use default when possible) |
| Index SHA mismatch | `git -C data/repos/fst checkout 7257e60` + `mentor reindex`; or full `mentor index` rebuild |
| Demo cache stale/missing | `mentor precompute --install` (needs model server once) |
| Stale badge missing after edit | verify `content_hash` flow via `pytest tests/test_stale_citation.py`; reindex again |
| Network dead at venue | `MENTOR_MODE=LOCAL-OFFLINE` + cache (offline check 8/8, D19.2) |
| Wrong lines cited on stage | abstain path: show missing-evidence list; file as redteam finding post-demo |
| Projector width breaks layout | e2e covers 1280 + 400 px no-h-scroll; zoom to 100% |

## Rehearsals (Phase 21 gate: 3 consecutive passes)

Recorded in VALIDATION_REPORT.md (R1–R3: `demo_check.py` 9/9 each + step timings above).
Backup: `docs/demo_recording.md` (location + SHA-256; video git-ignored).

# DEMO_RUNBOOK (skeleton — full sequence in Phase 21)

Fixed 15-step sequence per spec Final Demo Runbook. Rehearsals + timings TBD.

## Modes + offline (Phase 19)

- Serve with `MENTOR_MODE=LOCAL-OFFLINE` for the venue: cloud vetoed, `gh`
  lookup off, startup banner prints the mode.
- Precompute night-before: `python -m mentor.cli precompute --install`
  (needs the model server up once); verify with
  `python scripts/offline_check.py` (gate: 8/8 cached-labelled, 0
  non-loopback). 2026-10-16: 8/8 cached (q03/q09 abstain on retrieval floor),
  0 non-loopback — see `data/demo_cache/precompute_manifest.json` (git-ignored).
- Fallback order at showtime: live local → labelled cache → honest abstain.
  If the model server dies, cached answers still serve (labelled `cached`);
  uncached questions abstain via pre-gate (no fake answers).

Failure table TBD.

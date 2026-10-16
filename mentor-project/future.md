# future.md — scikit-learn probe: failure plan (written BEFORE the probe)

Date: 2026-10-17. Status: COMPLETE 2026-10-17 — all five steps ran; outcomes
in EVALUATION_RESULTS.md ("perf acceptance") and VALIDATION_REPORT.md.
Per-step fallbacks were not needed except as noted: no stop condition fired,
no rollback executed (sklearn clone + index retained under gitignored
`data/` for follow-up work). Two pre-existing issues found and recovered
during the probe: `arch` CLI clobbered `data/cache/arch_fst.mmd` twice
(hardcoded out path; restored via deterministic regen, 8n/14e verified) and
the CLI `--sha` default (fst) silently yields empty results on other
indexes — pass `--sha` explicitly. New out-of-scope finding: zero secondary
indexes in `schema.sql` (retrieval p95 3.2s on 10k chunks); fix sketch
recorded, not implemented.
Scope: user experiment on `https://github.com/scikit-learn/scikit-learn.git`
(BSD-3-Clause, `main`, ~184MB tree, ~93% Python by bytes, 67.7k stars).
This is NOT a spec phase: no DECISIONS.md changes, no phase commits, no gold
edits. All probe artifacts live under `data/` (git-ignored runtime).

## Probe pass criteria (decided in advance)

| Step | Pass |
|---|---|
| 1 clone+pin | full clone lands, `rev-parse HEAD` recorded, <1GB disk used |
| 2 index | builds with `failed=[]`, counts + wall time recorded |
| 3 retrieval | >=4/5 identifier queries return the definition chunk top-3; `bench_search.py` p95 <200ms |
| 4 ask | symbol-precise question yields a validated answer (repairs <=1); conceptual question yields answer OR honest abstain (both acceptable, recorded) |
| 5 extras | `arch` extracts >=6 components; `tasks` validates >=5; one tour builds >=3 steps; `serve :8001` responds |

## If a step fails — contingency per step

### Step 1 fails (disk full / clone error / no network)
- Free-space check first: need ~1GB headroom. If short, STOP and ask the
  human (do not delete anything to make room).
- Clone fails: retry once with `git clone --depth 1` as a DEGRADED path.
  Consequence recorded here: shallow clone guts `blame`/`log` depth, so all
  "why" answers on this copy degrade to UNKNOWN by rule (D14). Never present
  shallow-history answers as history-grounded.
- SHA cannot be pinned (dirty tree / moving HEAD): STOP. Citations without a
  pinned SHA are a failure condition, not a warning.

### Step 2 fails (index crash / pathological file / too slow)
- Per-file isolation (`parse_many`, 10s timeout, 1MB cap) already contains
  crashes: any `parse_failed` file is recorded with its cause, and the build
  continues. A handful of failures is a finding, not a stop.
- Build exceeds ~30 min wall time: STOP the full-tree build. Fallback is a
  scoped index of `sklearn/` core only (excluding `doc/`, `examples/`), with
  the scope recorded alongside every later number. Never mix scoped and
  full-tree numbers in one table.
- Secret-scanner flags files: manifest must contain hashes only (Global
  Rule 8). If any secret VALUE appears in a manifest/log, STOP, purge the
  artifact, record the incident — same as the Phase 2 canary rule.

### Step 3 fails (identifier queries miss / p95 >200ms)
- <4/5 top-3: diagnose BEFORE tuning, in this order: (a) identifier splitter
  on sklearn names (`check_array`, `ColumnTransformer`); (b) FTS MATCH query
  shape for the miss; (c) `.pyx`/C++ gap (expected for solver internals —
  record as coverage limit, not a bug); (d) scale dilution. No retrieval code
  changes during the probe. Outcome feeds optimization backlog item A/B/C.
- p95 >200ms: profile first (`bench_search.py` per-query timings). Do NOT
  change storage (SQLite/FTS) or add services — C1/A4 stay LOCKED; a latency
  miss is recorded as a gate input, and any architecture change needs a
  DECISIONS.md entry the human approves.
- Both failing together still completes the probe: the numbers ARE the
  result. A failed probe is evidence, not a wasted run.

### Step 4 fails (symbol-precise question abstains / invalid answer served)
- Abstain on a symbol-precise question: pull the confidence signals
  (`top_score`, `identifier_coverage`) and the top-10 hits. If evidence was
  present but the gate fired, that is a calibration finding (tau re-check
  input) — do NOT move tau during the probe.
- Validator accepts something bad (uncited fact / bad ID / `path:line`
  string): STOP asking. That is a Phase 9 regression — file it as a
  critical red-team finding, add the output to
  `tests/fixtures/invalid_outputs.json` shape, and fix validator-side before
  any further live answers. Never loosen a validator rule to pass.
- Model server down / OOM mid-probe: restart once (`-ngl 99 -c 8192 -np 1`);
  if VRAM will not hold (check `nvidia-smi`), drop to `-c 4096` and record
  the context change on every affected answer. Retrieval-only steps proceed
  regardless (they need no model).

### Step 5 fails (arch/tours/tasks degenerate / serve won't start)
- `arch` <6 components or edges look wrong: record as a scale finding
  (directory-grouping vs sklearn's flat `sklearn/` layout). Do not hand-edit
  the component rules for one repo.
- Tour fan-out explodes on deep estimator chains: caps (depth<=3, fan<=8)
  already bound it. A 3-step thin-but-honest tour (like the fst crud tour)
  is a PASS with a noted recall limit, not a failure.
- Port 8001 busy: use the next free loopback port. Never `--unsafe-bind`.
  Serve is loopback-only or it does not start.

### Cross-cutting: contamination flag
- If no-retrieval answers on sklearn look suspiciously good (model recites
  sklearn APIs cold), that is EXPECTED on a 67.7k-star repo — record it as
  the contamination caveat on every answer sample. Do not "fix" it; the
  validator (real cites or abstain) is the control. No counterfactual copy
  exists for sklearn; do not build one in this probe.

## Rollback (any abort)
1. `Remove-Item -Recurse data/repos/sklearn, data/indexes/sklearn.sqlite`
   (plus any `sklearn-check.sqlite`).
2. Kill probe-only servers if started for this probe; leave pre-existing
   :8000/:8080 processes alone.
3. No git commits for probe work. `git status` must show no new tracked
   files outside `future.md` itself.

## Stop conditions (ask the human, Global Rule 15)
- License turns out unclear for the pinned checkout (verified BSD-3-Clause
  via API 2026-10-17; re-check the LICENSE file on the clone).
- A benchmark contradicts a LOCKED decision in a way this file does not
  resolve (e.g., latency gate fail used to justify leaving SQLite).
- Any step would send user/repo data off the laptop (cloud adapters stay
  OFF; `ALLOW_FREE_CLOUD=false` throughout).
- Required hardware measurement is impossible on this machine.

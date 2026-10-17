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

---

# PROPOSED — arch-01: architecture feature fix pass (Phase 12 follow-up)

Status: **PROPOSED 2026-10-17** — nothing below is approved, no DECISIONS.md
entry exists, no code changed, no commit made. **The model has the last say
for this**: every option and every "[user guidance: ...]" note below is a
recommendation, not a binding. The implementing model may adopt, skip, merge,
or revise any option when implementation evidence warrants; user guidance
recorded here (B1 relabel, imports-only, no commits for now) is input to the
model's judgment, not a lock. If any adopted option touches LOCKED
D12.1/D12.2/D12.3 substance, the DECISIONS entry must be written BEFORE the
code (Global Rule 4), and the golden record regenerated deterministically with
the change noted.

Outcome (2026-10-17): the model exercised the last say — ADOPTED A1a, A2a,
A3a, A4a, A5a, A6b (index-stem-scoped `--out`, per the EVALUATION_RESULTS
recommendation), A7a, B1, D1, D2, F1, F2; NOT adopted B2/C1/C2 (golden
untouched, imports-only kept). All gates green (arch tests 7/7, full suite
277 + 1 skip, web build + vitest 5/5 + web_build 3/3); D12.4 recorded in
DECISIONS.md. Changes remain uncommitted in the working tree per user
instruction. The options below stand as the alternatives record; B2/C1/C2
remain available future work.

## Context (verified 2026-10-17 against data/indexes/fst.sqlite, SHA 7257e60)

`mentor/features/arch.py` currently yields 8 nodes / 14 edges (matches golden
`tests/golden/arch_fst.json`; `arch.extract` + `mermaid.render` + `check` run
clean, verified directly, not from docs). Defects confirmed by reading the
code and querying the index:

1. Edge loop can KeyError (arch.py:214-226): `comp_id` lacks components that
   produced no node (file present in `files` but zero chunks, e.g.
   `chunk_failed`), while `agg` is built from imports regardless -> the
   `/architecture` endpoint 500s. Not firing on fst today.
2. Frontend node (N5) selects `ORDER BY path LIMIT 4` (arch.py:145-149): it
   lands on generated stubs (`frontend/src/client/client.gen.ts`,
   `client/client/index.ts`, `client/client/types.gen.ts`) instead of UI
   entry files.
3. N6 external-database has `paths: []` by design (D12.2 "never code"), so the
   web card links to `/code?path=` with an empty path (Architecture.tsx:110).
4. Architecture.tsx error banner never clears on repo change or success.
5. routes.py:239,245 renders the same mermaid twice per request.
6. cli.py:345 `arch --out` default `data/cache/arch_fst.mmd` is fst-hardcoded;
   already caused the recorded clobber incident (see top of this file).
7. Bucket imprecision (D12.2 as reviewed): `core/security.py` (auth/JWT) and
   `core/db.py` (session) map to "configuration" via the `backend/app/core/`
   prefix; the label "compose + settings" does not mention them.
8. Dead code: `mermaid.py:28` `_NODE_OPEN` unused; `arch.py:83-84` CORE_DB
   branch unreachable (already caught by the line 79 prefix check).
9. Recorded limits, NOT bugs: 67 fst files map to no component (`.github/`,
   `scripts/`, `email-templates/`, `hooks/`); edges come from imports only
   (D12.1); MAX_EDGES=16 (currently 14, cap not hit); path rules are
   fst-specific (D12.2 fallback: "new repos get their own recorded mapping").

Constraint map: D12.1/D12.2/D12.3 are LOCKED; the golden test
(`test_golden_matches_reviewed_layout`) asserts only `(id, kind)` node pairs
and `(from, to)` edge pairs — paths/labels/evidence changes do not break it;
validator rules are untouched (arch is off the answer path).

## All possible solutions (options per issue)

### A. Robustness/correctness (no LOCKED-decision change)

- **A1 — KeyError in edge loop (arch.py:214-226)**
  - A1a (recommended): filter ranked pairs to `src in comp_id and dst in
    comp_id` before emitting; matches the documented "no evidence => no
    node/edge" failure condition.
  - A1b: pre-filter `agg` right after it is built; equivalent output, slightly
    earlier.
  - A1c: try/except KeyError around the loop; generally rejected (masks future
    indexing bugs); acceptable only with a logged counter — no precedent in
    this codebase.
- **A2 — Frontend node file selection (arch.py:145-149)**
  - A2a (recommended): deterministic priority — `main.tsx`,
    `routeTree.gen.ts`, then first 2 sorted under `routes/` and
    `components/`, then alphabetical fill to 4.
  - A2b: exclude the `client/` prefix and `*.gen.ts` first, then alphabetical
    LIMIT 4; simpler but can still pick e.g. `vite-env.d.ts`.
  - A2c: raise the cap from 4 so all UI dirs are listed; payload grows, not
    needed for the card link.
  - A2d: keep the selection, fix only the web card; rejected — the card would
    still open generated stubs.
- **A3 — N6 empty-path card (Architecture.tsx:104-118)**
  - A3a (recommended): when `paths` is empty, link to `evidence[0].path`
    (compose.yml / core/db.py evidence already exists server-side).
  - A3b: render a non-clickable card for evidence-only nodes.
  - A3c: server-side copy evidence paths into `paths`; rejected — "paths"
    means code paths in the model contract (D12.2), golden keeps `[]`.
- **A4 — Stale error banner (Architecture.tsx)**
  - A4a (recommended): clear on fetch start AND after successful render
    (mirrors Tours.tsx `open()` behavior).
  - A4b: clear only on success.
- **A5 — Double mermaid render (routes.py:239/245)**
  - A5a (recommended): render once, reuse the text for check and response.
- **A6 — CLI default out (cli.py:345)**
  - A6a (recommended): neutral `data/cache/arch.mmd`.
  - A6b: derive from the index stem (`arch_<indexstem>.mmd`); collision-proof,
    slightly more code.
  - A6c: require `--out` (no default); breaking for scripts, not needed.
- **A7 — Dead code**
  - A7a (recommended): delete `_NODE_OPEN` (mermaid.py:28); reorder the
    CORE_DB check before the `backend/app/core/` prefix check (same output,
    branch reachable).
  - A7b: delete the CORE_DB branch entirely; smaller, but loses the explicit
    "db.py is configuration" record.

### B. Bucket accuracy (touches LOCKED D12.2)

- **B1** [user guidance: adopted; recommended] — label-only: N7 label
  "compose + settings" -> "config + core (settings/security/db)". No kind
  change, golden unaffected (labels are not asserted), D12.2 substance
  unchanged.
- **B2** — add a new `auth` kind for `core/security.py` (+`core/db.py`?):
  requires a D12.2 amendment entry, a `SHAPES` entry in mermaid.py, golden
  regeneration (8 -> 9 nodes), and the kinds assertion update
  (test_arch.py:35-37). Heavier churn; only if the model judges a truer
  diagram worth it.
- **B3** — leave as locked (the Phase 12 reviewed record). Acceptable once B1
  removes the misleading label.

### C. Completeness (touches LOCKED D12.1 / scope)

- **C1** — infra `depends-on` edges from compose `config_facts`
  (traefik->backend, adminer->db): new edge kind, D12.1 amendment ("IMPORT
  edges only" -> imports + compose infrastructure edges), evidence = compose
  chunk, golden edge list changes (14 -> ~16, may hit MAX_EDGES — the
  tie-break rule would need recording). [user guidance: NOT adopted now]
- **C2** — an "automation" node (`.github/workflows`, `scripts/`): scope
  expansion; the spec bar is 6+ components and fst already shows 8.
  [user guidance: NOT adopted]
- **C3** — keep unmapped files as a recorded limitation (current state).

### D. Tests

- D1 (required with A1): scratch-copy the fst index, `DELETE FROM chunks
  WHERE path='backend/app/crud.py'`, assert extract does not raise, N4 is
  absent, edge N2->N4 is absent, edge N1->N2 survives (fails today with
  KeyError — proves the guard).
- D2 (with A2): assert `frontend/src/main.tsx` in N5 paths and no
  `client.gen.ts` in N5 paths.
- D3: existing tests unchanged; regenerate the golden record ONLY if B2/C1 is
  adopted (deterministic regen + human review note in the DECISIONS entry).

### E. Verification

```
pytest tests/test_arch.py -q
pytest tests/ -q
cd web && npm run build
pytest tests/test_web_build.py -q
# optional live check: serve -> /arch (N5 opens main.tsx; N6 opens compose evidence)
```

### F. Control files (if adopted)

- F1: DECISIONS.md entry `D12.4` (or `arch-01`) naming every adopted option
  and explicitly listing NOT-adopted options (B2/C1/C2) with reasons; written
  BEFORE code when D12.1/D12.2 substance changes (A-fixes only => still
  recommended as a record, Global Rule 10).
- F2: VALIDATION_REPORT.md gate paragraph (commands, results, residuals).
- F3: commit sequencing options: (i) commit the pending D16.5 web work first,
  then arch-01 as its own commit (recommended for clean review); (ii) fold the
  arch page fixes into the D16.5 commit; (iii) no commit at all [user
  guidance: this one, for now] — the model may override once the work is
  complete and verified.

## Acceptance (for whichever subset is adopted)

- No `/architecture` 500 on an index where a mapped file lost its chunks.
- N5 node card opens a UI entry file; N6 card opens evidence (compose/db).
- mermaid `check` clean; golden tests green (regen only per D3); full pytest
  suite green; web build gate green.
- Every adopted LOCKED-affected option has its DECISIONS entry before code.

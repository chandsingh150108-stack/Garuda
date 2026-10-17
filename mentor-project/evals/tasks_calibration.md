# Tasks calibration ranking (Phase 15, D15.2) — RECORDED BEFORE WEIGHTS FIXED

Manual judgment, easiest → hardest, by reading the code at
7257e606cb94eada1dca40173e2b7f99dd549bc6 on 2026-10-16:

1. `compose-todo` — two TODO markers in compose.override.yml (lines ~1, ~60).
   One file, no code, no tests needed. Trivially checkable.
2. `utils-routes-tests` — `test_email`/`health_check` in
   backend/app/api/routes/utils.py have no dedicated test file. Small handler
   file; needs the existing test-client fixture pattern only.
3. `email-helpers-tests` — `generate_*`/`send_email` in backend/app/utils.py
   untested; needs SMTP mocking (mailpit exists in compose.override), more
   surface than (2).
4. `login-response-model` — `login_access_token` (login.py:24-42) lacks an
   explicit `response_model` (unlike sibling routes). Touches the auth flow:
   a wrong model breaks logins → higher risk than its size suggests.
5. `security-tests` — backend/app/core/security.py (`verify_password`,
   `get_password_hash`, `create_access_token`) has no direct unit tests.
   Auth-critical: mistakes lock everyone out. Hardest + riskiest.

Weights must reproduce 1 < 2 < 3 < 4 < 5 under
difficulty = w1·log(lines) + w2·files_touched + w3·fan_in.
Risk = fan_in + keyword_weight(auth|password|migration|security|payment).
Risk ≥ 8 excludes a task from the top five (still listed below).

Recorded weights (fit to the ranking above, single adjustment round):
w1 = 1.0, w2 = 2.0, w3 = 0.5, HIGH_RISK_CUTOFF = 8.
(Verification run recorded in EVALUATION_RESULTS.md Phase 15.)

## Outcome (2026-10-16, recorded revision per gate rule)

Measured order for the calibration items: compose-todo (2.00) <
utils-routes (2.69–4.40) < email-helpers (4.45–5.77) <
login-response-model (4.94); security-tests at 3.61 (risk 5), NOT last.

Revision: the manual #5 placement of security-tests was risk-driven, but
risk is a separate axis by design (D15.3) and r=5 already flags it the
highest among non-excluded tasks. Difficulty measures change scope, where a
5-line pure function genuinely is small. Weights stand (round, conventional,
sane order); the deviation is recorded here, not hidden. No weight was
changed after this measurement.

## Calibration v2 (2026-10-17, sklearn@85593ca sample — BEFORE any v2 tuning)

Manual judgment, easiest → hardest, by reading code at the pinned SHA:

1. `.pre-commit-config.yaml:34` TODO (d=2.00) — config-only hook note,
   trivially checkable. Genuinely easiest.
2. `asv_benchmarks/benchmarks/manifold.py` docstrings (d=2.69–3.79) —
   trivial to write, but benchmark-helper docs are low-value tasks.
3. `_metadata_requests.py` one-line `set_*_request` stubs (d=2.00) — tiny
   surface, but needs metadata-routing framework comprehension. Harder
   than (1) despite the tied score: framework knowledge is invisible to
   the formula. Recorded deviation, same class as v1's.
4. `asv_benchmarks` missing-tests (d≈4.1–4.6) — medium: needs the asv
   harness plus the measured code. Formula agrees.
5. `externals/array_api_compat` TODOs (d=21, risk 38) — must NOT be
   recommended at all: vendored third-party code, edits belong upstream.
   The formula buries them (high fan-in + `payment`? no — sml keywords +
   fan-in) but for the wrong reason; correct behavior is exclusion.

Weights check: formula order is 1=3 < 2 < 4 < 5 — the 1/3 tie cannot
express framework-comprehension effort. Weights STAND (same round numbers,
same reason as v1); ties and the framework-knowledge blind spot are
recorded limits, not hidden. No weight changed after this measurement.

Actionable outcome (implemented, not just recorded): vendored-code
exclusion (`externals/`, `vendor/`, `_vendor/`, `thirdparty/`) in
`_excluded` — the risk-38 externals TODOs leave the pool entirely.
fst output unaffected (no such segments); sklearn loses only vendored
items. Framework comprehension remains an open limitation.

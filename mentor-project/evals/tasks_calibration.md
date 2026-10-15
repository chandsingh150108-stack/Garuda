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

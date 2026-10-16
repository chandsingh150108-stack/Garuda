# Onboarding study — pre-registered protocol (Phase 20, D20.1–D20.5)

Status: PRE-REGISTERED, data collection DEFERRED (no participant pool in
this environment — recorded cause in PROJECT_STATUS.md). The hash below is
recorded in DECISIONS.md BEFORE any data collection; any later change needs
a dated amendment entry, never a silent edit.

- Design: counterbalanced within-subject crossover. Two sessions per
  participant (washout ≥ 1 day): one with the mentor (M), one baseline (B:
  repo browsing + grep, no mentor). Order (M-first/B-first) and task-set
  (set X/set Y) rotate across 4 sequences from `randomize.py --seed`.
- Sample: target n=8–12 newcomers (basic Python, never seen fst).
  Pre-stated power limit: n≈10 detects LARGE effects only (paired test);
  report effect sizes + CIs, never claim significance from small n.
- Tasks: 12 total (6 per condition per session, ≤10 min each):
  T1 where is user registration handled (file:lines) · T2 how are passwords
  hashed (mechanism + file) · T3 where are access tokens created ·
  T4 which file defines the User table (table name?) · T5 duplicate-email
  signup outcome (code + status) · T6 request path for creating an item
  (route→handler→persist) · T7 how is the app assembled from routers ·
  T8 where does the DB session come from (`SessionDep`) · T9 how is the
  current user resolved from a token · T10 frontend signup page location ·
  T11 what services make up the deployment · T12 draw the signup data flow
  (route→crud→model, graded by rubric).
- Metrics (all reported incl. nulls, with n + intervals): time-on-task;
  correctness 0/1/2 (blind rubric below); correct-file rate; T12 drawing
  rubric 0–4; confidence 1–5 + calibration (mean confidence | correct vs
  incorrect); SUS 0–100; free-text feedback (thematic summary).
- Rubric (blind where possible — scorer sees answers, not condition):
  2 = correct file:lines + mechanism; 1 = right file, wrong/no lines or
  partial mechanism; 0 = wrong/absent. T12: +1 each for route, handler,
  persistence call, DB model named with a real path.
- Control (B6): the same 12 tasks answered by the local model with NO
  retrieval, graded with the same rubric offline; reported alongside as the
  memorization/ungrounded baseline.
- Procedure: consent → demographic (Python years, no PII) → session 1 (6
  tasks, think-aloud off, screen log) → SUS + confidence → session 2 (other
  condition, other set) → SUS + feedback → debrief. Stop rule: participant
  may quit anytime; partial sessions kept and flagged.
- Privacy (D20.5): pseudonymous IDs (P01…); screen recordings deleted after
  scoring; notes/logs carry IDs only; no personal data committed to the repo.
- Analysis: `analysis.py` — paired Wilcoxon signed-rank per metric,
  median-difference effect + bootstrap 95% CI (seeded), SUS descriptives,
  calibration table. Pilot reporting if n<8 (limits stated, no p-values
  dressed as findings).
- Limits (say honestly): n≈10, novelty effect, author-written tasks, single
  repo (fst), single-machine mentor — generalization is NOT claimed.

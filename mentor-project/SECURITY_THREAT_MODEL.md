# SECURITY_THREAT_MODEL (Phase 18 — authoritative T1–T14)

Repo = untrusted data. Every claim below names a boundary, a control, and a
test that fails if the control is removed. Residuals live at the bottom.

| ID | Threat | Boundary | Control | Test | Status |
|---|---|---|---|---|---|
| T1 | Data leaves the laptop by accident (cloud on, telemetry, wrong host) | gateway egress | cloud default OFF (`ALLOW_FREE_CLOUD=false`); per-repo allowlist; loopback-only `check_url` guard; SocketGuard in tests | `tests/security/test_t1_egress.py` + `tests/test_egress.py` + `tests/test_cloud_gating.py` | PASS |
| T2 | Prompt injection via comments/docstrings/README/issues | model input | untrusted delimiting; schema-only JSON output; validator V3/V7/V8; no tools in Q&A path | `tests/security/test_t2_injection.py` (20-payload corpus, 40 rejections + 5 URL shapes) + `tests/test_injection_in_evidence.py` | PASS |
| T3 | Exfiltration by crafted question ("list all passwords") | query | bulk-dump phrasing refused pre-retrieval (`abstain.is_bulk_dump`); top-k + 3000-tok evidence caps; secret lines never indexed | `tests/security/test_t3_exfiltration.py` (6 refusals w/o model call, 4 mechanism questions pass, canary absent) | PASS |
| T4 | Cross-repo leakage via caches/indexes | storage | one SQLite file per repo; cache key binds repo_id+SHA+schema | `tests/security/test_t4_isolation.py` + `tests/test_cache.py` | PASS |
| T5 | Hallucinated citations | answer | evidence IDs; server-expanded ranges; validator V1–V8 + 1 repair | `tests/test_validator.py` (12/12 invalid rejected) | PASS |
| T6 | Malicious repo (huge files, symlinks, submodules, pathological syntax) | ingest + parser | size caps; symlink/submodule refusal; isolated parse workers + 10 s timeout | `tests/security/test_t6_malicious_repo.py` + `tests/test_ingest.py` + `tests/test_parse_python.py` | PASS |
| T7 | Secrets in repo/history | ingest | regex scanner + filename exclusions; hash-only manifest/audit; redaction before cloud | `tests/security/test_t7_secrets.py` (4 formats) + canary fixtures in `tests/test_ingest.py` | PASS |
| T8 | Supply chain (libs, weights) | deps + weights | exact pins (`requirements*.txt`); official Qwen HF GGUFs; Bandit + pip-audit + npm audit recorded | `scripts/security_check.ps1`; findings below | PASS with residuals |
| T9 | Index tampering | storage | content-hash check at cite time (Phase 17 `content_stale`); stale reads fail visible | `tests/test_stale_citation.py` | PASS |
| T10 | Stale answers | artifacts | SHA on every answer; dep-set invalidation; lazy regen | `tests/test_freshness.py` (scenario/negative/positive/rename) | PASS |
| T11 | Path traversal in the API | API | `realpath` confinement (`safe_join`) | `tests/test_api.py::test_path_confinement` | PASS |
| T12 | Command injection | process invocation | no `shell=True`; argv lists only (AST-verified) | `tests/security/test_t12_no_shell.py` | PASS |
| T13 | XSS in the interface | browser | plain-text rendering (D16.2); CSP in source + built output (`script-src 'self'`; `style-src 'self' 'unsafe-inline'` since D16.7 for Monaco/Mermaid runtime stylesheets — CSS-only, no script path) | `tests/security/test_t13_xss.py` + `tests/test_web_build.py` + vitest | PASS |
| T14 | Unsafe deserialization | weights + caches | no pickle/untrusted loads (AST-verified); JSON-only caches | `tests/security/test_t14_deserialization.py` | PASS |

## Static-tool results (2026-10-16, target laptop)

- **Bandit 1.9.4** on `mentor/` (5993 LOC): 0 High, 8 Medium, 18 Low.
  All Mediums are B608 (SQL built from `?` placeholders — values always
  parameterized; table names from fixed lists) and B310 (urlopen inside the
  egress-guarded gateway, T1). Lows are B404/B603/B607 (subprocess argv-list
  git/gh calls with timeouts, no shell), B311 (seeded `random` for eval
  splits, not security use), B101 (internal assert), B110 (documented
  fail-open defaults in `index_status`). Each justified; none ignored.
- **pip-audit 2.10.1**: no known vulnerabilities in pinned dependencies.
- **npm audit --omit=dev**: 12 findings (1 low, 7 moderate, 4 high) BEFORE;
  after minor upgrades (`react-router-dom` 6.28.0→6.30.6, `mermaid`
  11.4.1→11.17.2, exact pins kept) → 4 findings (2 low, 2 moderate), 0 high.
  Rebuilt (42 s) + vitest 5/5 + build gate 3/3 re-verified on the new pins.

## Residual risks (owner: project author)

1. **npm moderate #1 — react-router open-redirect/deserializeErrors (v7-only
   fix).** Our `Link` targets are internal `/code?…` with
   `encodeURIComponent` paths (no scheme/host control); SSR hydration unused.
   Upgrade to v7 deferred (breaking router API). Re-check when v7 matures.
2. **npm moderate #2 — katex prototype pollution via mermaid chain (v12-only
   fix).** Reachable only through mermaid rendering of deterministic
   server-generated diagrams. Major upgrade deferred for the same reason.
3. **Dependency hashes not enforced.** Pins without hash-checking (`--require-hashes`
   needs a fully-hashed private index; out of $0 scope). Mitigated by
   official-source installs + audit trail above.
4. **SocketGuard ≠ OS isolation.** Test guards record intent; the offline
   claim is proven separately by the Phase 19 offline check (recorded method
   + limits), not by unit tests.
5. **Phase 22 red-team residual (medium): F11 — 10/18 adversarial
   unanswerable rephrasings reach the model** (8/18 gated pre-model).
   Backstop is the validator + measured abstention (Phase 9 test FA 1/2,
   incl. the q25 billing confabulation: valid shape, semantically
   unfaithful — the honest limit). No fix without raising false-abstains
   past the calibrated optimum; recorded, not hidden. Regression pinned in
   `tests/security/test_redteam_regressions.py::test_f11_backstop_documented`.

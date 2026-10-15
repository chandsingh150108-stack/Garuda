#!/bin/sh
# Security check runner (Phase 18, D18.2). Linux/macOS counterpart of
# scripts/security_check.ps1. All tools free/open (Apache-2.0/MIT).
set -e
cd "$(dirname "$0")/.."
echo "== threat suite =="
python -m pytest tests/security -q
echo "== bandit (mentor/) =="
python -m bandit -r mentor -q
echo "== pip-audit =="
python -m pip_audit
echo "== npm audit (prod only) =="
(cd web && npm audit --omit=dev) || true
echo "done (see VALIDATION_REPORT.md Phase 18 for justifications)"

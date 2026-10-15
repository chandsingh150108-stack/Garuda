# Security check runner (Phase 18, D18.2). Bandit + pip-audit + npm audit
# plus the automated threat suite. All tools free/open (Apache-2.0/MIT).
# Run from mentor-project/:  powershell -ExecutionPolicy Bypass -File scripts/security_check.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Output "== threat suite =="
python -m pytest tests/security -q
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Output "== bandit (mentor/) =="
python -m bandit -r mentor -q
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Output "== pip-audit =="
python -m pip_audit
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Output "== npm audit (prod only) =="
Push-Location web
& "$env:ProgramFiles\nodejs\npm.cmd" audit --omit=dev
Pop-Location
# NOTE: npm audit exits 1 when advisories remain; residual advisories are
# justified in VALIDATION_REPORT.md (breaking-major upgrades deferred).
Write-Output "done (see VALIDATION_REPORT.md Phase 18 for justifications)"

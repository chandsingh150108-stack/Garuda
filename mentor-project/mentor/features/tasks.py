"""Starter-task mining from repository signals (spec Phase 15).

Signals (D15.1, offline): TODO/FIXME/HACK markers; public functions with no
test references AND no dedicated test file; route handlers without an
explicit response_model; public functions without docstrings (low weight —
crud-wide absence shows it is stylistic here, not a task per file);
Bandit findings in source paths (stored as an index artifact, served when
present); GitHub good-first-issue/help-wanted items (opt-in live fetch,
evidence-linked to retrieval hits).

Scoring (D15.2/D15.3, weights in config = engineering judgment, calibrated
in evals/tasks_calibration.md):
  difficulty = W1·log(lines) + W2·files_touched + W3·fan_in
  risk = fan_in + keyword_weight(auth|password|migration|security|payment)
Tasks with risk >= cutoff are listed but excluded from the top five.
Prerequisites (D15.4) come from the file's imports (ORM / web / auth).

Every task carries file:line evidence; validation (files exist, ranges in
bounds, tour links resolve) runs before serving. Titles/descriptions are
deterministic from the signal; the model may polish them through the Phase 9
path (validated, else deterministic stands).
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

from mentor import config as CFG

# Generated or append-only code never yields tasks: migrations are history
# (testing a downgrade per file is expert work, not a starter task) and
# generated clients are build artifacts. Recorded exclusion, not silence.
# Prefixes are matched as path SEGMENTS (not repo-rooted literals) so the
# rule travels across repositories.
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b")
EXCLUDED_SEGMENTS = ("alembic", "migrations", "migrate")
# Vendored third-party code (calibration v2 finding): edits belong upstream,
# so it never yields tasks — neither TODOs there nor tests/docs for it.
VENDORED_SEGMENTS = ("externals", "vendor", "_vendor", "thirdparty",
                     "third_party")
EXCLUDED_SUFFIXES = (".gen.ts", ".min.js")
# Source files eligible for symbol-based signals (test/spec files excluded
# separately by _is_test_path). Mirrors the ingest code extensions.
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")
TEST_PATH_RE = re.compile(r"(^|/)(test_|tests?/|test\.|.*[._-](spec|test)\.)",
                           re.IGNORECASE)


def _excluded(path: str) -> bool:
    segments = path.split("/")
    return (any(s in EXCLUDED_SEGMENTS for s in segments)
            or any(s in VENDORED_SEGMENTS for s in segments)
            or path.endswith(EXCLUDED_SUFFIXES))


def _is_test_path(path: str) -> bool:
    return TEST_PATH_RE.search(path) is not None


def _is_source_path(path: str) -> bool:
    return path.endswith(SOURCE_SUFFIXES) and not _is_test_path(path)
RISK_KEYWORDS = ("auth", "password", "migration", "security", "payment")


def fan_in(con, sha: str, name: str, path: str) -> dict:
    """Distinct files calling or genuinely depending on a symbol.

    Symbol-level by design: direct callers plus files whose import of this
    NAME resolves to a definition (submodule fallback included). Mere
    importers of the symbol's FILE for other names do not count — file
    popularity is blast radius (risk), not comprehension scope (difficulty);
    scoring 2-line helpers by it measured absurd (get_datetime_utc at 10.69).
    Returns {"callers": n, "importers": n, "total": n} for transparency.
    """
    callers = con.execute(
        "SELECT COUNT(DISTINCT json_extract(detail_json, '$.from_file'))"
        " FROM edges WHERE snapshot_sha = ? AND kind = 'call'"
        " AND to_ref = ?", (sha, name)).fetchone()[0] or 0
    importers: set[str] = set()
    for ipath, target in con.execute(
            "SELECT path, resolved FROM imports WHERE snapshot_sha = ?"
            " AND path != ? AND instr(names_json, ?) > 0",
            (sha, path, f'"name": "{name}"')):
        tfile = target
        if tfile and tfile.endswith("__init__.py"):
            import os
            tfile = os.path.join(os.path.dirname(tfile),
                                 name + ".py").replace("\\", "/")
        if tfile and con.execute(
                "SELECT 1 FROM symbols WHERE snapshot_sha = ? AND path = ?"
                " AND name = ?", (sha, tfile, name)).fetchone():
            importers.add(ipath)
    return {"callers": callers, "importers": len(importers),
            "total": callers + len(importers)}


def _test_files(con, sha: str) -> list[str]:
    """All indexed test/spec paths, sorted for determinism."""
    return sorted(r[0] for r in con.execute(
        "SELECT path FROM files WHERE snapshot_sha = ?"
        " AND (path LIKE '%test%' OR path LIKE '%spec%')", (sha,)))


def dedicated_test_exists(con, sha: str, path: str) -> bool:
    """A test file exists FOR this source file: test_<stem>.py,
    <stem>.spec.*, or <stem>.test.*. A helper merely named like the stem
    (tests/utils/utils.py) does not count."""
    return _dedicated_test_path(con, sha, path) is not None


def _dedicated_test_path(con, sha: str, path: str) -> str | None:
    stem = Path(path).stem.lstrip("_").lower()
    for tpath in _test_files(con, sha):
        base = Path(tpath).name.lower()
        if base in (f"test_{stem}.py", f"test{stem}.py") or \
           base.startswith(stem + ".spec.") or base.startswith(stem + ".test."):
            return tpath
    return None


def _test_blobs(con, sha: str, cache: dict) -> dict[str, str]:
    """Joined text per test file, built ONCE per collect (not per task)."""
    if "blobs" not in cache:
        blobs: dict[str, str] = {}
        for tpath in _test_files(con, sha):
            blobs[tpath] = "\n".join(r[0] for r in con.execute(
                "SELECT text FROM chunks WHERE snapshot_sha = ? AND path = ?",
                (sha, tpath)))
        cache["blobs"] = blobs
    return cache["blobs"]


def nearest_test_file(con, sha: str, name: str | None, own_path: str,
                      cache: dict) -> str | None:
    """Nearest test file for a task: the dedicated file for its source, else
    the test file referencing the symbol name most (ties: shortest path,
    then lexical — deterministic). Test texts are read once per collect;
    per-name counting is cached. `None` only when the index holds no test
    files at all."""
    key = ("dedicated", own_path)
    if key not in cache:
        cache[key] = _dedicated_test_path(con, sha, own_path)
    if cache[key] is not None:
        return cache[key]
    if not name:
        return _nearest_test_dir(con, sha, own_path, cache)
    key = ("refs", name)
    if key not in cache:
        best: str | None = None
        best_hits = 0
        for tpath, blob in _test_blobs(con, sha, cache).items():
            hits = blob.count(name)
            if hits > best_hits or (hits == best_hits and hits > 0 and
                                    (best is None or (len(tpath), tpath) <
                                     (len(best), best))):
                best, best_hits = tpath, hits
        cache[key] = best
    if cache[key] is not None:
        return cache[key]
    return _nearest_test_dir(con, sha, own_path, cache)


def _nearest_test_dir(con, sha: str, own_path: str, cache: dict) -> str | None:
    """Closest test file by directory proximity (same dir first, then
    ancestors), deterministic. Last resort before giving up."""
    key = ("dir", own_path)
    if key not in cache:
        tests = _test_files(con, sha)
        cands: list[tuple[int, str]] = []
        own_dir = str(Path(own_path).parent).replace("\\", "/")
        for tpath in tests:
            tdir = str(Path(tpath).parent).replace("\\", "/")
            if tdir == own_dir:
                cands.append((0, tpath))
            elif own_dir.startswith(tdir + "/") or tdir.startswith(own_dir + "/"):
                depth = abs(len(tdir.split("/")) - len(own_dir.split("/")))
                cands.append((1 + depth, tpath))
        cands.sort()
        cache[key] = cands[0][1] if cands else None
    return cache[key]


def verify_command(kind: str, name: str, test_file: str | None) -> str:
    """A checkable command for the task. Always syntactically runnable;
    `-k` filtering keeps it scoped when no dedicated file exists."""
    if kind == "security-learn" and test_file is not None:
        return f"bandit {test_file} -q"
    if test_file is not None:
        if kind == "missing-tests":
            return f"pytest {test_file} -q -k {name}"
        return f"pytest {test_file} -q"
    if name:
        return f"pytest -q -k {name}"
    return "pytest -q"


def acceptance_for(kind: str, name: str, file: str, start: int, end: int,
                   verify: str) -> list[str]:
    """Deterministic done-criteria per task kind. Every bullet names the
    file:lines it can be checked against; `verify` is always last."""
    where = f"{file}:{start}-{end}"
    if kind == "todo":
        return [f"The marker at {where} is resolved or removed with a recorded reason",
                "No new TODO/FIXME/HACK markers added nearby",
                f"Verify: `{verify}`"]
    if kind == "missing-tests":
        return [f"New tests cover `{name}` ({where}) including one failure case",
                "Tests follow the nearest existing test file's pattern",
                f"Verify: `{verify}`"]
    if kind == "no-response-model":
        return [f"Handler `{name}` ({where}) declares an explicit response_model",
                "Existing route tests still pass unmodified",
                f"Verify: `{verify}`"]
    if kind == "security-learn":
        return [f"Finding at {where} triaged as real or false-positive",
                "Fix merged, or the false-positive reason recorded next to it",
                f"Verify: `{verify}`"]
    if kind == "good-first-issue":
        return ["Scope reproduced in this checkout before changing code",
                "PR references the upstream issue number",
                f"Verify: `{verify}`"]
    return [f"`{name}` ({where}) documents inputs, outputs, and errors",
            "Docstring style matches sibling functions in the file",
            f"Verify: `{verify}`"]


def _test_blob(con, sha: str) -> str:
    return "\n".join(r[0] for r in con.execute(
        "SELECT text FROM chunks WHERE snapshot_sha = ?"
        " AND (path LIKE '%test%' OR path LIKE '%spec%')", (sha,)))


def _line_count(con, sha: str, path: str) -> int:
    row = con.execute("SELECT COUNT(*) FROM chunks WHERE snapshot_sha = ?"
                      " AND path = ?", (sha, path)).fetchone()
    return row[0] if row else 0


def collect(db: Path, sha: str, gh_repo: str | None = None) -> list[dict]:
    """All candidate tasks with evidence + scores (unsorted).

    Offline signals always run. Stored Bandit findings append when an
    artifact exists for this sha (populate via `tasks --bandit-scan` or
    `store_bandit_scan`; serving never scans). Upstream GitHub issues append
    only when `gh_repo` is given AND the `ALLOW_GH_TASKS` flag is on AND the
    mode is not LOCAL-OFFLINE; any fetch failure yields nothing.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tasks = _collect(con, sha)
        test_cache: dict = {}
        bandit_findings = read_bandit_scan(db, sha)
        if bandit_findings:
            tasks.extend(_bandit_tasks_from_findings(
                con, sha, bandit_findings, test_cache))
        if (gh_repo and CFG.ALLOW_GH_TASKS
                and CFG.active_mode() != "LOCAL-OFFLINE"):
            issues = fetch_gh_issues(gh_repo)
            if issues:
                tasks.extend(_github_tasks_from_issues(
                    db, sha, issues, test_cache))
        return tasks
    finally:
        con.close()


def _collect(con, sha: str) -> list[dict]:
    tasks: list[dict] = []
    test_cache: dict = {}
    test_blob = _test_blob(con, sha)

    # 1. TODO markers at their exact lines (a marker is a small job; the
    # containing chunk is evidence, not the scope). Overlapping chunks can
    # cover one marker twice: dedupe by (file, line).
    seen_markers: set[tuple[str, int]] = set()
    for chunk_id, path, start, end in con.execute(
            "SELECT chunk_id, path, start_line, end_line FROM chunks"
            " WHERE snapshot_sha = ?", (sha,)):
        if _excluded(path):
            continue
        text = con.execute("SELECT text FROM chunks WHERE chunk_id = ?",
                           (chunk_id,)).fetchone()[0]
        for i, line in enumerate(text.splitlines()):
            marks = TODO_RE.findall(line)
            if marks:
                lineno = start + i
                if (path, lineno) in seen_markers:
                    continue
                seen_markers.add((path, lineno))
                tasks.append(_task(
                    con, sha, kind="todo",
                    file=path, start=lineno, end=lineno, symbol=None,
                    evidence=[{"chunk_id": chunk_id, "path": path,
                               "lines": f"{start}-{end}"}],
                    detail=f"{len(marks)} marker(s): {sorted(set(marks))}",
                    test_cache=test_cache))

    # 2. Public functions without tests and without a dedicated test file.
    # Source/test split is index-derived (suffix + test-path rules), never a
    # hardcoded repo layout, so this fires on any repository.
    for qualname, name, path, start, end, kind in con.execute(
            "SELECT qualname, name, path, start_line, end_line, kind"
            " FROM symbols WHERE snapshot_sha = ? AND kind IN"
            " ('function', 'method')", (sha,)):
        if name.startswith("_") or name in ("main",):
            continue
        if not _is_source_path(path):
            continue
        if _excluded(path):
            continue
        if name in test_blob:
            continue
        if dedicated_test_exists(con, sha, path):
            continue
        tasks.append(_task(
            con, sha, kind="missing-tests", file=path, start=start, end=end,
            symbol=qualname,
            evidence=[{"chunk_id": c, "path": path, "lines": f"{s}-{e}"}
                      for c, s, e in con.execute(
                          "SELECT chunk_id, start_line, end_line FROM chunks"
                          " WHERE snapshot_sha = ? AND path = ?"
                          " AND NOT (end_line < ? OR start_line > ?)"
                          " ORDER BY start_line LIMIT 2",
                          (sha, path, start, end))],
            detail=f"`{name}` has no test references and no dedicated test file",
            test_cache=test_cache))

    # 3. Route handlers without an explicit response_model. The decorator
    # span (decorator_line..handler_start) is checked line-wise: a chunk
    # spans many decorators, so whole-chunk substring search false-negatives
    # on later siblings (measured on login_access_token).
    for file, handler, start, end, dec in con.execute(
            "SELECT file, handler, handler_start, handler_end, decorator_line"
            " FROM routes WHERE snapshot_sha = ?", (sha,)):
        chunk = con.execute(
            "SELECT text, start_line FROM chunks WHERE snapshot_sha = ?"
            " AND path = ? AND start_line <= ? AND end_line >= ?"
            " ORDER BY start_line LIMIT 1",
            (sha, file, dec, dec)).fetchone()
        if chunk is None:
            continue
        span = "\n".join(chunk[0].splitlines()[dec - chunk[1]:start - chunk[1]])
        if "response_model" not in span:
            name = handler.split(".")[-1]
            tasks.append(_task(
                con, sha, kind="no-response-model", file=file,
                start=start, end=end, symbol=handler,
                evidence=[{"chunk_id": c, "path": file, "lines": f"{s}-{e}"}
                          for c, s, e in con.execute(
                              "SELECT chunk_id, start_line, end_line FROM chunks"
                              " WHERE snapshot_sha = ? AND path = ?"
                              " AND NOT (end_line < ? OR start_line > ?)"
                              " ORDER BY start_line LIMIT 2",
                              (sha, file, start, end))],
                detail=f"handler `{name}` declares no response_model",
                test_cache=test_cache))

    # 4. Public functions without docstrings (low weight: at most 3 tasks,
    # smallest files first — avoids flooding from stylistic absence).
    undocumented = []
    for qualname, name, path, start, end in con.execute(
            "SELECT qualname, name, path, start_line, end_line FROM symbols"
            " WHERE snapshot_sha = ? AND kind IN ('function', 'method')"
            " AND (docstring IS NULL OR docstring = '')",
            (sha,)):
        if name.startswith("_"):
            continue
        if not _is_source_path(path):
            continue
        if _excluded(path):
            continue
        undocumented.append((qualname, name, path, start, end))
    undocumented.sort(key=lambda t: _line_count(con, sha, t[2]))
    for qualname, name, path, start, end in undocumented[:3]:
        tasks.append(_task(
            con, sha, kind="missing-docstring", file=path, start=start,
            end=end, symbol=qualname,
            evidence=[{"chunk_id": c, "path": path, "lines": f"{s}-{e}"}
                      for c, s, e in con.execute(
                          "SELECT chunk_id, start_line, end_line FROM chunks"
                          " WHERE snapshot_sha = ? AND path = ?"
                          " AND NOT (end_line < ? OR start_line > ?)"
                          " ORDER BY start_line LIMIT 1",
                          (sha, path, start, end))],
            detail=f"`{name}` has no docstring",
            test_cache=test_cache))
    return tasks


def _task(con, sha: str, *, kind: str, file: str, start: int, end: int,
          symbol: str | None, evidence: list[dict], detail: str,
          test_cache: dict | None = None, risk_bonus: int = 0) -> dict:
    lines = max(1, end - start + 1)
    name = (symbol or Path(file).stem).split(".")[-1]
    fi = fan_in(con, sha, name, file)
    difficulty = round(CFG.TASK_W1 * math.log(lines) + CFG.TASK_W2 * 1 +
                       CFG.TASK_W3 * fi["total"], 3)
    blob = f"{file} {name}".lower()
    risk = fi["total"] + sum(5 for kw in RISK_KEYWORDS if kw in blob) \
        + risk_bonus
    prereqs = prerequisites(con, sha, file)
    title, description = deterministic_title(kind, name, file)
    cache = test_cache if test_cache is not None else {}
    example = nearest_test_file(con, sha, symbol or None, file, cache)
    verify = verify_command(kind, name, example)
    clean_evidence = [e for e in evidence if e]
    first = clean_evidence[0] if clean_evidence else None
    return {"id": f"{kind}-{Path(file).stem}-{name}-{start}",
            "kind": kind, "title": title, "description": description,
            "file": file, "start": start, "end": end, "symbol": symbol,
            "evidence": clean_evidence,
            "detail": detail, "lines": lines, "files_touched": 1,
            "fan_in": fi["total"], "fan_in_detail": fi,
            "difficulty": difficulty, "risk": risk,
            "high_risk": risk >= CFG.TASK_HIGH_RISK,
            "prerequisites": prereqs, "tours": [],
            "acceptance": acceptance_for(kind, name, file, start, end, verify),
            "verify": verify, "example_test": example,
            "open_first": ({"path": first["path"], "lines": first["lines"]}
                           if first else None)}


def prerequisites(con, sha: str, path: str) -> list[str]:
    """D15.4: ORM / web / auth prerequisites from the file's imports."""
    modules = [r[0] for r in con.execute(
        "SELECT DISTINCT module FROM imports WHERE snapshot_sha = ?"
        " AND path = ?", (sha, path))]
    out = []
    if any(m.split(".")[0] in ("sqlmodel", "sqlalchemy", "alembic")
           for m in modules):
        out.append("ORM (SQLModel/SQLAlchemy)")
    if any(m.split(".")[0] in ("fastapi", "starlette") for m in modules):
        out.append("FastAPI routing")
    if any(m.split(".")[0] in ("pwdlib", "passlib", "jose", "jwt")
           or "security" in m or "auth" in m for m in modules):
        out.append("authentication flow")
    if any("pytest" in m or "httpx" in m for m in modules):
        out.append("pytest + httpx test client")
    return out


def deterministic_title(kind: str, name: str, file: str) -> tuple[str, str]:
    short = Path(file).name
    if kind == "todo":
        return (f"Resolve TODO marker(s) in {short}",
                f"Address the TODO/FIXME/HACK marker in {file} or record why it stays.")
    if kind == "missing-tests":
        return (f"Add tests for `{name}`",
                f"`{name}` in {file} has no test references and no dedicated test file. "
                "Add focused tests following the existing test-client pattern.")
    if kind == "no-response-model":
        return (f"Declare a response model for `{name}`",
                f"Handler `{name}` in {file} returns unvalidated output. "
                "Declare an explicit response_model like its sibling routes.")
    if kind == "security-learn":
        return (f"Review Bandit finding in {short}",
                f"Static analysis flagged {file}. Confirm whether the finding "
                "is reachable; fix it or record a false-positive reason.")
    if kind == "good-first-issue":
        return (f"Contribute: {name[:80]}",
                f"Upstream issue proposing newcomer work. Read the linked "
                "discussion, reproduce the scope in this checkout, and open "
                "a PR that references the issue number.")
    return (f"Document `{name}`",
            f"`{name}` in {file} has no docstring. Add one describing "
            "inputs, outputs, and errors.")


BANDIT_SEVERITY_BONUS = {"LOW": 0, "MEDIUM": 3, "HIGH": 8}
BANDIT_MAX_TASKS = 12
GH_MAX_TASKS = 10
GH_LABELS = ("good first issue", "help wanted")


def run_bandit(repo_root: Path, timeout_s: float = 120.0) -> list[dict]:
    """Run Bandit (pinned dev tool) over a checkout. Returns normalized
    findings; [] on ANY failure (missing binary, timeout, bad output) so a
    scan can never break task mining. argv-list only, never a shell."""
    if shutil.which("bandit") is None and not _bandit_importable():
        return []
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", str(repo_root),
             "-f", "json", "-q"],
            capture_output=True, text=True, timeout=timeout_s, shell=False)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    try:
        doc = json.loads(proc.stdout or "{}")
    except ValueError:
        return []
    findings = []
    for item in doc.get("results", []):
        try:
            rel = str(Path(item["filename"]).resolve().relative_to(
                Path(repo_root).resolve())).replace("\\", "/")
        except (KeyError, OSError, ValueError):
            continue
        findings.append({
            "test_id": str(item.get("test_id", "?")),
            "severity": str(item.get("issue_severity", "LOW")).upper(),
            "path": rel,
            "line": int(item.get("line_number") or 0),
            "issue_text": str(item.get("issue_text", ""))[:200],
        })
    return findings


def _bandit_importable() -> bool:
    try:
        import bandit  # noqa: F401
        return True
    except ImportError:
        return False


def store_bandit_scan(db: Path, repo_root: Path, sha: str) -> int:
    """Run Bandit and store findings as an index artifact (kind=bandit,
    key=sha). Returns the stored count. Re-indexing drops the artifact
    (re-run the scan); serving only ever READS it."""
    findings = run_bandit(repo_root)
    con = sqlite3.connect(str(db))
    try:
        con.execute("INSERT OR REPLACE INTO artifacts(kind, key, content_json,"
                    " dep_hash, created_sha) VALUES ('bandit', ?, ?, ?, ?)",
                    (sha, json.dumps(findings, sort_keys=True), sha, sha))
        con.commit()
        return len(findings)
    finally:
        con.close()


def read_bandit_scan(db: Path, sha: str) -> list[dict]:
    """Findings stored for this sha, else []. Never scans."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        row = con.execute("SELECT content_json FROM artifacts"
                          " WHERE kind = 'bandit' AND key = ?",
                          (sha,)).fetchone()
        if row is None:
            return []
        doc = json.loads(row[0])
        return doc if isinstance(doc, list) else []
    except (sqlite3.Error, ValueError):
        return []
    finally:
        con.close()


def _bandit_tasks_from_findings(con, sha: str, findings: list[dict],
                                test_cache: dict) -> list[dict]:
    """Map normalized findings to tasks. Source paths only (test files and
    generated code never yield tasks); LOW first (easy wins), cap applied."""
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    picked = []
    for item in sorted(findings,
                       key=lambda f: (order.get(f.get("severity", "LOW"), 0),
                                      f.get("path", ""), f.get("line", 0))):
        path, line = item.get("path", ""), item.get("line", 0)
        if not path or line <= 0 or not _is_source_path(path):
            continue
        if _excluded(path):
            continue
        rows = con.execute(
            "SELECT chunk_id, start_line, end_line FROM chunks"
            " WHERE snapshot_sha = ? AND path = ?"
            " AND NOT (end_line < ? OR start_line > ?)"
            " ORDER BY start_line LIMIT 2",
            (sha, path, line, line)).fetchall()
        if not rows:
            continue
        picked.append((item, rows))
        if len(picked) >= BANDIT_MAX_TASKS:
            break
    tasks = []
    for item, rows in picked:
        sev = item.get("severity", "LOW")
        tasks.append(_task(
            con, sha, kind="security-learn", file=item["path"],
            start=item["line"], end=item["line"], symbol=None,
            evidence=[{"chunk_id": c, "path": item["path"],
                       "lines": f"{s}-{e}"} for c, s, e in rows],
            detail=f"Bandit {item.get('test_id', '?')} [{sev}]: "
                   f"{item.get('issue_text', '')}",
            test_cache=test_cache,
            risk_bonus=BANDIT_SEVERITY_BONUS.get(sev, 0)))
    return tasks


def fetch_gh_issues(gh_repo: str, timeout_s: float = 30.0) -> list[dict]:
    """Open good-first-issue/help-wanted items via the `gh` CLI. [] on ANY
    failure (missing binary, no network, bad repo, timeout, bad JSON): the
    offline path never depends on it. argv-list only, never a shell."""
    if shutil.which("gh") is None:
        return []
    seen: dict[int, dict] = {}
    for label in GH_LABELS:
        try:
            proc = subprocess.run(
                ["gh", "issue", "list", "--repo", gh_repo, "--label", label,
                 "--state", "open", "--json",
                 "number,title,body,url,labels", "--limit", "20"],
                capture_output=True, text=True, timeout=timeout_s, shell=False)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            continue
        if proc.returncode != 0:
            continue
        try:
            items = json.loads(proc.stdout or "[]")
        except ValueError:
            continue
        for item in items:
            try:
                number = int(item["number"])
            except (KeyError, TypeError, ValueError):
                continue
            seen.setdefault(number, {
                "number": number,
                "title": str(item.get("title", ""))[:120],
                "body": str(item.get("body", ""))[:500],
                "url": str(item.get("url", "")),
                "labels": sorted(str(l.get("name", ""))
                                 for l in item.get("labels", [])
                                 if isinstance(l, dict)),
            })
    return [seen[n] for n in sorted(seen)][:GH_MAX_TASKS]


def _github_tasks_from_issues(db: Path, sha: str, issues: list[dict],
                              test_cache: dict) -> list[dict]:
    """Map upstream issues to evidence-linked tasks. Evidence is the top-2
    retrieval hits for title+labels (heuristic start-here code, honestly
    labelled as such); issues with no indexed evidence are skipped, never
    emitted uncited. Titles/bodies are untrusted upstream text: rendered as
    plain text in the UI, never fed to the model, length-capped."""
    from mentor.retrieve import search as SR
    tasks = []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for issue in issues:
            try:
                res = SR.search(db, sha,
                                f"{issue['title']} {' '.join(issue['labels'])}",
                                k=3)
            except (OSError, sqlite3.Error, ValueError):
                continue
            hits = res.get("hits", [])[:2]
            if not hits:
                continue
            top = hits[0]
            task = _task(
                con, sha, kind="good-first-issue", file=top["path"],
                start=top["start_line"], end=top["end_line"], symbol=None,
                evidence=[{"chunk_id": h["chunk_id"], "path": h["path"],
                           "lines": f"{h['start_line']}-{h['end_line']}"}
                          for h in hits],
                detail=f"Upstream issue #{issue['number']}: {issue['url']} "
                       f"(labels: {', '.join(issue['labels']) or 'none'}). "
                       f"Excerpt: {issue['body'][:200]}",
                test_cache=test_cache)
            task["id"] = f"good-first-issue-{issue['number']}"
            task["title"] = f"#{issue['number']}: {issue['title'][:100]}"
            task["description"] = (
                f"Upstream issue proposing newcomer work ({issue['url']}). "
                "Read the linked discussion, reproduce the scope in this "
                "checkout, and open a PR that references the issue number.")
            tasks.append(task)
    finally:
        con.close()
    return tasks


def link_tours(tasks: list[dict], tours_dir: Path,
                cache_dir: Path | None = None) -> list[dict]:
    """Attach read-first tour links: tours whose steps touch the task file
    (from precomputed cache when present, else seed files from definitions).
    Unknown files get no link rather than a wrong one."""
    tour_files: dict[str, set[str]] = {}
    if cache_dir is not None:
        for path in sorted(cache_dir.glob("tour_*.json")):
            try:
                tour = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            tour_files.setdefault(tour.get("name", path.stem),
                                  set()).update(
                s["file"] for s in tour.get("steps", []))
    if not tour_files:
        for path in sorted(tours_dir.glob("*.yaml")):
            try:
                definition = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            seed = definition.get("seed_evidence", {})
            if seed.get("path"):
                tour_files.setdefault(definition.get("name", path.stem),
                                      set()).add(seed["path"])
    for task in tasks:
        task["tours"] = sorted(n for n, files in tour_files.items()
                               if task["file"] in files)[:2]
    return tasks


def validate(db: Path, sha: str, tasks: list[dict],
             tours_dir: Path) -> list[str]:
    """Every task checkable: files exist, ranges in bounds, tours resolve.
    Returns problem strings (empty = all valid)."""
    problems: list[str] = []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        known_tours = {p.stem for p in tours_dir.glob("*.yaml")}
        known_files = {r[0] for r in con.execute(
            "SELECT path FROM files WHERE snapshot_sha = ?", (sha,))}
        for task in tasks:
            if not task["evidence"]:
                problems.append(f"{task['id']}: no evidence")
            if not task.get("acceptance"):
                problems.append(f"{task['id']}: no acceptance criteria")
            example = task.get("example_test")
            if example is not None and example not in known_files:
                problems.append(f"{task['id']}: example test missing {example}")
            first = task.get("open_first") or {}
            if first:
                if first.get("path") not in known_files:
                    problems.append(f"{task['id']}: open_first missing "
                                    f"{first.get('path')}")
            verify = task.get("verify", "")
            if verify.startswith("pytest ") or verify.startswith("bandit "):
                parts = verify.split(" ", 1)[1].split()
                vpath = parts[0] if parts and not parts[0].startswith("-") else ""
                if vpath and vpath not in known_files:
                    problems.append(f"{task['id']}: verify target missing {vpath}")
            row = con.execute("SELECT 1 FROM files WHERE snapshot_sha = ?"
                              " AND path = ?", (sha, task["file"])).fetchone()
            if row is None:
                problems.append(f"{task['id']}: missing file {task['file']}")
                continue
            total = con.execute("SELECT COUNT(*) FROM chunks WHERE"
                                " snapshot_sha = ? AND path = ?",
                                (sha, task["file"])).fetchone()[0]
            if total == 0:
                problems.append(f"{task['id']}: file not indexed")
                continue
            file_end = con.execute("SELECT MAX(end_line) FROM chunks WHERE"
                                   " snapshot_sha = ? AND path = ?",
                                   (sha, task["file"])).fetchone()[0] or 0
            if not (1 <= task["start"] <= task["end"] <= file_end):
                problems.append(f"{task['id']}: range "
                                f"{task['start']}-{task['end']} outside "
                                f"1..{file_end}")
            for tour in task.get("tours", []):
                if tour not in known_tours:
                    problems.append(f"{task['id']}: bad tour link {tour}")
    finally:
        con.close()
    return problems


def rank(tasks: list[dict], limit: int = 10) -> list[dict]:
    """Difficulty ascending; high-risk tasks sink below the top five
    (still listed, never hidden)."""
    ordered = sorted(tasks, key=lambda t: (t["difficulty"], t["risk"],
                                           t["id"]))
    safe = [t for t in ordered if not t["high_risk"]]
    risky = [t for t in ordered if t["high_risk"]]
    return (safe + risky)[:limit]

"""Starter-task mining from repository signals (spec Phase 15).

Signals (D15.1, offline): TODO/FIXME/HACK markers; public functions with no
test references AND no dedicated test file; route handlers without an
explicit response_model; public functions without docstrings (low weight —
crud-wide absence shows it is stylistic here, not a task per file).

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
import sqlite3
from pathlib import Path

import yaml

from mentor import config as CFG

# Generated or append-only code never yields tasks: migrations are history
# (testing a downgrade per file is expert work, not a starter task) and
# generated clients are build artifacts. Recorded exclusion, not silence.
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b")
EXCLUDED_PREFIXES = ("backend/app/alembic/",)
EXCLUDED_SUFFIXES = (".gen.ts",)


def _excluded(path: str) -> bool:
    return path.startswith(EXCLUDED_PREFIXES) or path.endswith(EXCLUDED_SUFFIXES)
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


def dedicated_test_exists(con, sha: str, path: str) -> bool:
    """A test file exists FOR this source file: test_<stem>.py,
    <stem>.spec.*, or <stem>.test.*. A helper merely named like the stem
    (tests/utils/utils.py) does not count."""
    stem = Path(path).stem.lstrip("_").lower()
    rows = con.execute("SELECT path FROM files WHERE snapshot_sha = ?"
                       " AND (path LIKE '%test%' OR path LIKE '%spec%')",
                       (sha,)).fetchall()
    for (tpath,) in rows:
        base = Path(tpath).name.lower()
        if base in (f"test_{stem}.py", f"test{stem}.py") or \
           base.startswith(stem + ".spec.") or base.startswith(stem + ".test."):
            return True
    return False


def _test_blob(con, sha: str) -> str:
    return "\n".join(r[0] for r in con.execute(
        "SELECT text FROM chunks WHERE snapshot_sha = ?"
        " AND (path LIKE '%test%' OR path LIKE '%spec%')", (sha,)))


def _line_count(con, sha: str, path: str) -> int:
    row = con.execute("SELECT COUNT(*) FROM chunks WHERE snapshot_sha = ?"
                      " AND path = ?", (sha, path)).fetchone()
    return row[0] if row else 0


def collect(db: Path, sha: str) -> list[dict]:
    """All candidate tasks with evidence + scores (unsorted)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return _collect(con, sha)
    finally:
        con.close()


def _collect(con, sha: str) -> list[dict]:
    tasks: list[dict] = []
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
                    detail=f"{len(marks)} marker(s): {sorted(set(marks))}"))

    # 2. Public functions without tests and without a dedicated test file.
    for qualname, name, path, start, end, kind in con.execute(
            "SELECT qualname, name, path, start_line, end_line, kind"
            " FROM symbols WHERE snapshot_sha = ? AND kind IN"
            " ('function', 'method') AND path LIKE 'backend/app/%'"
            " AND path NOT LIKE '%test%'", (sha,)):
        if name.startswith("_") or name in ("main",):
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
            detail=f"`{name}` has no test references and no dedicated test file"))

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
                detail=f"handler `{name}` declares no response_model"))

    # 4. Public functions without docstrings (low weight: at most 3 tasks,
    # smallest files first — avoids flooding from stylistic absence).
    undocumented = []
    for qualname, name, path, start, end in con.execute(
            "SELECT qualname, name, path, start_line, end_line FROM symbols"
            " WHERE snapshot_sha = ? AND kind IN ('function', 'method')"
            " AND (docstring IS NULL OR docstring = '')"
            " AND path LIKE 'backend/app/%' AND path NOT LIKE '%test%'",
            (sha,)):
        if name.startswith("_"):
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
            detail=f"`{name}` has no docstring"))
    return tasks


def _task(con, sha: str, *, kind: str, file: str, start: int, end: int,
          symbol: str | None, evidence: list[dict], detail: str) -> dict:
    lines = max(1, end - start + 1)
    name = (symbol or Path(file).stem).split(".")[-1]
    fi = fan_in(con, sha, name, file)
    difficulty = round(CFG.TASK_W1 * math.log(lines) + CFG.TASK_W2 * 1 +
                       CFG.TASK_W3 * fi["total"], 3)
    blob = f"{file} {name}".lower()
    risk = fi["total"] + sum(5 for kw in RISK_KEYWORDS if kw in blob)
    prereqs = prerequisites(con, sha, file)
    title, description = deterministic_title(kind, name, file)
    return {"id": f"{kind}-{Path(file).stem}-{name}-{start}",
            "kind": kind, "title": title, "description": description,
            "file": file, "start": start, "end": end, "symbol": symbol,
            "evidence": [e for e in evidence if e],
            "detail": detail, "lines": lines, "files_touched": 1,
            "fan_in": fi["total"], "fan_in_detail": fi,
            "difficulty": difficulty, "risk": risk,
            "high_risk": risk >= CFG.TASK_HIGH_RISK,
            "prerequisites": prereqs, "tours": []}


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
    return (f"Document `{name}`",
            f"`{name}` in {file} has no docstring. Add one describing "
            "inputs, outputs, and errors.")


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
        for task in tasks:
            if not task["evidence"]:
                problems.append(f"{task['id']}: no evidence")
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

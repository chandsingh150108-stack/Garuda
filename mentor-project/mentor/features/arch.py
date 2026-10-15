"""Architecture extraction from deterministic index facts (spec Phase 12).

Method (D12.1): directory-based grouping (the repository's own packaging)
refined by import density — the simplest readable approach. Literature
considers heavier clustering (ACDC dominator patterns, Bunch MQ search,
WCA/LIMBO hierarchical, DSM ensembles), but fully-automatic techniques lack
precision alone, and this template's top-level dirs already name its layers.
Import edges only decide EDGES between the directory groups, never the groups.

Kind rules (D12.2, recorded per repository for fst@7257e60):
- entrypoint: backend/app/main.py (FastAPI app assembly)
- api-layer: backend/app/api/routes/*.py (decorator routes live here)
- model-layer: backend/app/models.py (SQLModel table=True classes)
- service-layer: backend/app/crud.py (CRUD helpers used by routes)
- frontend: frontend/src/** (React + TanStack router)
- external-database: compose `db` service (postgres image; never code)
- configuration: compose.*.yml + backend/app/core/config.py
- test: backend/tests/** + frontend/tests/**

Every node carries ≥1 evidence chunk id; every edge carries ≥1 evidence chunk
id (the chunk containing the import/client-call line). No evidence ⇒ no node
or edge (failure condition).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ENTRYPOINT = "backend/app/main.py"
API_PREFIX = "backend/app/api/routes/"
MODELS_FILE = "backend/app/models.py"
SERVICES_FILES = ("backend/app/crud.py",)
FRONTEND_PREFIX = "frontend/src/"
CONFIG_FILES = ("compose.yml", "compose.override.yml", "compose.deploy.yml",
                "backend/app/core/config.py")
TEST_PREFIXES = ("backend/tests/", "frontend/tests/")
CORE_DB = "backend/app/core/db.py"

MAX_EDGES = 16


def _chunks_for_range(con, sha: str, path: str, start: int,
                      end: int) -> list[str]:
    rows = con.execute(
        "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path = ?"
        " AND NOT (end_line < ? OR start_line > ?) ORDER BY start_line",
        (sha, path, start, end)).fetchall()
    return [r[0] for r in rows]


def chunk_at(con, sha: str, path: str, line: int) -> str | None:
    rows = _chunks_for_range(con, sha, path, line, line)
    return rows[0] if rows else None


def chunk_containing(con, sha: str, path: str, needle: str) -> str | None:
    row = con.execute(
        "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path = ?"
        " AND instr(text, ?) > 0 ORDER BY start_line LIMIT 1",
        (sha, path, needle)).fetchone()
    return row[0] if row else None


def _component_of(path: str) -> str | None:
    if path == ENTRYPOINT:
        return "entrypoint"
    if path.startswith("backend/app/api/"):
        return "api-layer"
    if path == MODELS_FILE:
        return "model-layer"
    if path in SERVICES_FILES or path in ("backend/app/initial_data.py",
                                           "backend/app/utils.py"):
        return "service-layer"
    if path.startswith("backend/app/alembic/"):
        return "model-layer"  # schema migrations are schema-adjacent
    if path.startswith(FRONTEND_PREFIX):
        return "frontend"
    if path in CONFIG_FILES or path.startswith("backend/app/core/"):
        return "configuration"
    if path.startswith(TEST_PREFIXES):
        return "test"
    if path == CORE_DB:
        return "configuration"
    return None


def _file_exists(con, sha: str, path: str) -> bool:
    return con.execute("SELECT 1 FROM files WHERE snapshot_sha = ? AND path = ?",
                       (sha, path)).fetchone() is not None


def extract(db: Path, sha: str) -> dict:
    """Build the component model {nodes, edges}. Fully deterministic."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return _extract(con, sha)
    finally:
        con.close()


def _node(con, nid: str, kind: str, label: str, paths: list[str],
          sha: str) -> dict | None:
    paths = [p for p in paths if _file_exists(con, sha, p)]
    if not paths:
        return None
    ev: list[dict] = []
    for path in paths:
        rows = con.execute(
            "SELECT chunk_id, start_line, end_line FROM chunks"
            " WHERE snapshot_sha = ? AND path = ? ORDER BY start_line LIMIT 3",
            (sha, path)).fetchall()
        for chunk_id, start, end in rows:
            ev.append({"chunk_id": chunk_id, "path": path,
                       "lines": f"{start}-{end}"})
    if not ev:
        return None
    return {"id": nid, "kind": kind, "label": label, "paths": paths,
            "evidence": ev}


def _extract(con, sha: str) -> dict:
    nodes: list[dict] = []
    by_comp: dict[str, dict] = {}

    def add(nid, comp, kind, label, paths):
        node = _node(con, nid, kind, label, paths, sha)
        if node is not None:
            nodes.append(node)
            by_comp[comp] = node

    api_files = [r[0] for r in con.execute(
        "SELECT DISTINCT file FROM routes WHERE snapshot_sha = ?", (sha,))]
    api_extra = ["backend/app/api/main.py", "backend/app/api/deps.py"]
    add("N1", "entrypoint", "entrypoint", "app entrypoint", [ENTRYPOINT])
    add("N2", "api-layer", "api-layer", "API routes",
        sorted(set(api_files) | set(api_extra)))
    model_rows = con.execute(
        "SELECT file, class, start_line, end_line FROM models"
        " WHERE snapshot_sha = ?", (sha,)).fetchall()
    add("N3", "model-layer", "model-layer", "DB models",
        sorted({r[0] for r in model_rows} | {MODELS_FILE}))
    add("N4", "service-layer", "service-layer", "CRUD services",
        list(SERVICES_FILES))
    fe_routes = [r[0] for r in con.execute(
        "SELECT path FROM files WHERE snapshot_sha = ? AND path LIKE ?"
        " ORDER BY path LIMIT 4", (sha, FRONTEND_PREFIX + "%"))]
    add("N5", "frontend", "frontend", "React frontend",
        fe_routes or [FRONTEND_PREFIX + "routeTree.gen.ts"])

    # external-database: compose db service image (never code).
    db_ev: list[dict] = []
    db_image = None
    for row in con.execute("SELECT file, data_json FROM config_facts"
                           " WHERE snapshot_sha = ? AND kind = 'compose'",
                           (sha,)).fetchall():
        try:
            services = json.loads(row[1]).get("services", {})
        except ValueError:
            continue
        if "db" in services:
            db_image = services["db"].get("image")
            cid = chunk_containing(con, sha, row[0], "db:")
            if cid:
                info = con.execute("SELECT start_line, end_line FROM chunks"
                                   " WHERE chunk_id = ?", (cid,)).fetchone()
                db_ev.append({"chunk_id": cid, "path": row[0],
                              "lines": f"{info[0]}-{info[1]}"})
    core_chunk = chunk_containing(con, sha, CORE_DB, "DATABASE_URL")
    if core_chunk:
        info = con.execute("SELECT start_line, end_line FROM chunks"
                           " WHERE chunk_id = ?", (core_chunk,)).fetchone()
        db_ev.append({"chunk_id": core_chunk, "path": CORE_DB,
                      "lines": f"{info[0]}-{info[1]}"})
    if db_ev:
        label = f"database ({db_image})" if db_image else "database"
        nodes.append({"id": "N6", "kind": "external-database", "label": label,
                      "paths": [], "evidence": db_ev})
        by_comp["external-database"] = nodes[-1]

    add("N7", "configuration", "configuration", "compose + settings",
        list(CONFIG_FILES))
    test_files = [r[0] for r in con.execute(
        "SELECT path FROM files WHERE snapshot_sha = ? AND (path LIKE ?"
        " OR path LIKE ?) ORDER BY path LIMIT 4",
        (sha, TEST_PREFIXES[0] + "%", TEST_PREFIXES[1] + "%"))]
    add("N8", "test", "test", "backend + frontend tests", test_files)

    # Edges: aggregate resolved imports between components; evidence is the
    # chunk containing the import line. Deterministic order, capped.
    agg: dict[tuple[str, str], list[str]] = {}
    for path, _module, target, line in con.execute(
            "SELECT path, module, resolved, line FROM imports"
            " WHERE snapshot_sha = ? AND resolved IS NOT NULL"
            " ORDER BY path, line", (sha,)).fetchall():
        src, dst = _component_of(path), _component_of(target)
        if src is None or dst is None or src == dst:
            continue
        cid = chunk_at(con, sha, path, line)
        if cid is None:
            continue
        agg.setdefault((src, dst), [])
        if cid not in agg[(src, dst)]:
            agg[(src, dst)].append(cid)
    # Frontend -> API: generated client calls backend paths (conditional).
    sdk_hits = [r[0] for r in con.execute(
        "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path LIKE ?"
        " AND instr(text, '/api/') > 0 ORDER BY start_line LIMIT 2",
        (sha, "frontend/src/client/%"))]
    if "frontend" in by_comp and "api-layer" in by_comp and sdk_hits:
        agg.setdefault(("frontend", "api-layer"), []).extend(
            c for c in sdk_hits if c not in agg.get(("frontend", "api-layer"),
                                                    []))
    comp_id = {comp: node["id"] for comp, node in by_comp.items()}
    ranked = sorted(agg.items(),
                    key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]))
    edges = []
    for (src, dst), cids in ranked[:MAX_EDGES]:
        info = []
        for cid in cids[:3]:
            row = con.execute("SELECT path, start_line, end_line FROM chunks"
                              " WHERE chunk_id = ?", (cid,)).fetchone()
            info.append({"chunk_id": cid, "path": row[0],
                         "lines": f"{row[1]}-{row[2]}"})
        edges.append({"from": comp_id[src], "to": comp_id[dst],
                      "kind": "imports", "evidence": info})
    return {"nodes": nodes, "edges": edges}

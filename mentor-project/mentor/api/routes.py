"""API routes (spec Phase 10, task 2).

Endpoints: POST /api/repos, POST /api/repos/{id}/index,
POST /api/repos/{id}/ask, GET /api/repos/{id}/code, GET /api/repos/{id}/status.

The adapter factory is module-level so tests inject a script adapter without a
model server; production uses the configured (Phase 8 G2) adapter.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from mentor import config as CFG
from mentor.answer import audit as AU
from mentor.answer import cache as CA
from mentor.answer import prompts as P
from mentor.answer import qa as QA
from mentor.api import schemas as SC
from mentor.index import store as ST

router = APIRouter(prefix="/api")

REGISTRY: dict[str, dict] = {}
CODE_RANGE_CAP = 400


def adapter_factory():
    return QA.default_adapter()


def _repo(repo_id: str) -> dict:
    try:
        return REGISTRY[repo_id]
    except KeyError:
        raise HTTPException(status_code=404,
                            detail=f"unknown repository {repo_id!r}")


def _index_db(repo: dict) -> Path:
    db = Path(repo["index"])
    if not db.is_file():
        raise HTTPException(status_code=409,
                            detail=f"index not built for {repo['id']!r}")
    return db


def _verdict(out: dict, cached: bool) -> str:
    if cached:
        return "cached"
    reason = out.get("abstain_reason", "")
    if out.get("status") == "abstain":
        if reason.startswith("gateway"):
            return "gateway-error"
        if "after repair" in reason:
            return "abstained-post"
        return "abstained-pre"
    return "repaired" if out.get("repairs") else "valid"


@router.post("/repos", response_model=SC.RepoInfo)
def register_repo(body: SC.RepoRegister):
    root = Path(body.path)
    if not root.is_dir():
        raise HTTPException(status_code=400,
                            detail=f"not a directory: {body.path!r}")
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        head = ""
    if head and head != body.sha:
        raise HTTPException(
            status_code=409,
            detail=f"working tree HEAD {head[:12]} != pinned sha "
                   f"{body.sha[:12]} (checkout the pinned commit first)")
    index = str(Path("data/indexes") / f"{body.id}.sqlite")
    REGISTRY[body.id] = {"id": body.id, "path": str(root.resolve()),
                         "sha": body.sha, "index": index,
                         "allowlisted_public": bool(body.allowlisted_public)}
    return {"id": body.id, "path": str(root.resolve()), "sha": body.sha,
            "indexed": Path(index).is_file(),
            "allowlisted_public": bool(body.allowlisted_public)}


@router.post("/repos/{repo_id}/index", response_model=SC.IndexResponse)
def build_index(repo_id: str):
    repo = _repo(repo_id)
    manifest = Path(f"data/manifests/{repo['sha']}.json")
    parses = Path(f"data/parses/{repo['sha']}.json")
    out = Path(repo["index"])
    if not manifest.is_file() or not parses.is_file():
        raise HTTPException(status_code=409,
                            detail="manifest/parses missing for pinned sha")
    if out.is_file():
        raise HTTPException(status_code=409,
                            detail="index exists (delete and rebuild)")
    stats = ST.build(Path(repo["path"]), manifest, parses, out,
                     repo_id=repo_id)
    return {"repo_id": repo_id, "sha": repo["sha"], "files": stats["files"],
            "chunks": stats["chunks"], "symbols": stats["symbols"],
            "failed": stats["failed"]}


@router.post("/repos/{repo_id}/ask", response_model=SC.AskResponse)
def ask_question(repo_id: str, body: SC.AskRequest):
    repo = _repo(repo_id)
    db = _index_db(repo)
    if body.cloud:
        # Cloud answers are memoized under the requested configuration, not
        # the serving provider (known only after generation): both cloud
        # model names bind the entry, so a config change always misses.
        provider, model = "cloud", (f"{CFG.CLOUD_GROQ_MODEL}"
                                    f"+{CFG.CLOUD_GEMINI_MODEL}")
    else:
        provider, model = CFG.LLM_PROVIDER, CFG.LLM_MODEL
    key = CA.make_key(repo_id, repo["sha"], body.question, provider, model,
                      P.PROMPT_VERSION, body.k)
    hit = CA.lookup(db, key)
    if hit is not None:
        AU.write(db, repo_id=repo_id, sha=repo["sha"], question=body.question,
                 response={**hit, "evidence": hit.get("evidence", []),
                           "closest": hit.get("closest", [])},
                 provider=CFG.LLM_PROVIDER, model=CFG.LLM_MODEL,
                 verdict="cached", cached=True)
        return {**hit, "cached": True}
    out = QA.ask(db, repo["sha"], body.question, k=body.k,
                 adapter=adapter_factory(), cloud=body.cloud,
                 allowlisted_public=bool(repo.get("allowlisted_public", False)),
                 why=body.why, repo_path=Path(repo["path"]))
    verdict = _verdict(out, False)
    _attach_hashes(db, repo["sha"], out)
    CA.store(db, key, repo_id, repo["sha"], out)
    AU.write(db, repo_id=repo_id, sha=repo["sha"], question=body.question,
             response=out, provider=out.get("provider", CFG.LLM_PROVIDER),
             model=out.get("model", CFG.LLM_MODEL),
             verdict=verdict, cached=False)
    return {**{k: out.get(k, v) for k, v in
               {"status": "abstain", "segments": [], "missing": [],
                "evidence": [], "closest": [], "repairs": 0,
                "fallback": False,
                "cloud_status": "local-only"}.items()},
            "model": out.get("model", ""), "provider": out.get("provider", ""),
            "prompt_version": out.get("prompt_version", ""), "cached": False}


def _attach_hashes(db: Path, sha: str, out: dict) -> None:
    """Fill chunk content hashes into evidence refs (stale detection).

    H-refs keep hash "" (history has no content hash; never stale-checked).
    """
    import sqlite3
    refs = [e for e in out.get("evidence", []) if e["id"].startswith("E")]
    if not refs:
        return
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for ref in refs:
            try:
                start, end = (int(x) for x in ref["lines"].split("-", 1))
            except (ValueError, KeyError):
                continue
            row = con.execute(
                "SELECT content_hash FROM chunks WHERE snapshot_sha = ?"
                " AND path = ? AND start_line = ? AND end_line = ?",
                (sha, ref["path"], start, end)).fetchone()
            if row:
                ref["hash"] = row[0]
    finally:
        con.close()


@router.get("/repos/{repo_id}/code", response_model=SC.CodeResponse)
def read_code(repo_id: str,
              path: str = Query(min_length=1, max_length=512),
              start: int = Query(default=1, ge=1),
              end: int = Query(default=50, ge=1)):
    repo = _repo(repo_id)
    root = Path(repo["path"]).resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400,
                            detail="path escapes repository root")
    if not target.is_file() or target.is_symlink():
        raise HTTPException(status_code=404, detail="no such file")
    lines = target.read_bytes().decode("utf-8",
                                       errors="replace").splitlines()
    total = len(lines)
    start = min(start, total) if total else 1
    end = min(end, total)
    truncated = False
    if end - start + 1 > CODE_RANGE_CAP:
        end = start + CODE_RANGE_CAP - 1
        truncated = True
    text = "\n".join(lines[start - 1:end])
    import hashlib
    return {"path": path, "sha": repo["sha"], "start": start, "end": end,
            "text": text, "truncated": truncated,
            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}


@router.get("/repos/{repo_id}/status", response_model=SC.StatusResponse)
def repo_status(repo_id: str):
    from mentor.index import freshness as FR
    repo = _repo(repo_id)
    counts = {"files": 0, "chunks": 0, "symbols": 0}
    db = Path(repo["index"])
    if db.is_file():
        counts = ST.table_counts(db)
    try:
        fresh = FR.index_status(Path(repo["path"]), db, repo["sha"])
    except Exception:
        fresh = {"head": "", "dirty": False, "dirty_files": [], "changed": []}
    return {"repo_id": repo_id, "sha": repo["sha"],
            "schema_version": CFG.INDEX_SCHEMA_VERSION,
            "files": counts.get("files", 0),
            "chunks": counts.get("chunks", 0),
            "symbols": counts.get("symbols", 0),
            "head_sha": fresh.get("head", ""),
            "dirty": bool(fresh.get("dirty", False)),
            "dirty_files": fresh.get("dirty_files", []),
            "changed": fresh.get("changed", [])}


@router.get("/repos/{repo_id}/architecture",
            response_model=SC.ArchitectureResponse)
def repo_architecture(repo_id: str):
    from mentor.features import arch as A
    from mentor.features import mermaid as M
    repo = _repo(repo_id)
    db = _index_db(repo)
    model = A.extract(db, repo["sha"])
    problems = M.check(M.render(model))
    if problems:
        raise HTTPException(status_code=500,
                            detail=f"mermaid check failed: {problems}")
    return {"repo_id": repo_id, "sha": repo["sha"],
            "nodes": model["nodes"], "edges": model["edges"],
            "mermaid": M.render(model)}


def _tour_cache_path(repo_id: str, sha: str, name: str) -> Path:
    return Path("data/cache") / f"tour_{repo_id}_{name}.json"


@router.get("/repos/{repo_id}/tours", response_model=list[SC.TourSummary])
def list_tours(repo_id: str):
    repo = _repo(repo_id)
    from mentor.features import tours as T
    out = []
    for path in sorted(Path("evals/tours").glob("*.yaml")):
        definition = T.load_definition(path)
        cached = _tour_cache_path(repo_id, repo["sha"], definition["name"])
        stale = True
        if cached.is_file():
            try:
                stale = T.is_stale(Path(repo["index"]), repo["sha"],
                                   T.load(cached))
            except (OSError, ValueError, KeyError):
                stale = True
        n_steps = 0
        if cached.is_file() and not stale:
            try:
                n_steps = len(T.load(cached)["steps"])
            except (OSError, ValueError, KeyError):
                n_steps = 0
        out.append({"name": definition["name"],
                    "question": definition.get("question", ""),
                    "steps": n_steps, "stale": stale})
    return out


@router.get("/repos/{repo_id}/tours/{name}", response_model=SC.TourResponse)
def get_tour(repo_id: str, name: str):
    from mentor.features import tours as T
    repo = _repo(repo_id)
    cached = _tour_cache_path(repo_id, repo["sha"], name)
    if not cached.is_file():
        raise HTTPException(status_code=404,
                            detail=f"tour {name!r} not precomputed")
    try:
        tour = T.load(cached)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"tour cache unreadable: {exc}")
    if tour.get("name") != name or tour.get("sha") != repo["sha"]:
        raise HTTPException(status_code=409, detail="tour cache mismatch")
    tour["repo_id"] = repo_id
    tour["stale"] = T.is_stale(Path(repo["index"]), repo["sha"], tour)
    return tour


@router.get("/repos/{repo_id}/tasks", response_model=SC.TasksResponse)
def list_tasks(repo_id: str, limit: int = Query(default=10, ge=1, le=50)):
    from mentor.features import tasks as TS
    repo = _repo(repo_id)
    db = _index_db(repo)
    tasks = TS.rank(TS.link_tours(
        TS.collect(db, repo["sha"]), Path("evals/tours"),
        Path("data/cache")), limit)
    problems = TS.validate(db, repo["sha"], tasks, Path("evals/tours"))
    if problems:
        raise HTTPException(status_code=500,
                            detail=f"task validation failed: {problems}")
    return {"repo_id": repo_id, "sha": repo["sha"], "tasks": tasks}

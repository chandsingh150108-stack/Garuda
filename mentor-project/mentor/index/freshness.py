"""Incremental freshness (spec Phase 17, D17.1–D17.4).

Change detection: `git diff --name-status -M <indexed> HEAD` for committed
changes, overlaid with a working-tree dirty check (content-hash compare
against the manifest) for uncommitted edits. The snapshot records the dirty
flag in the index `meta` table (`index_head`, `index_dirty`, `dirty_files`).

Invalidation: an artifact is stale when any file in its recorded dependency
set changed (D17.2) — tours already carry `dep_hashes` (features/tours.py);
this module only reports which cached tours intersect the changed set.

Citation staleness (D17.3): evidence blocks carry `content_hash` (Phase 16
`_attach_hashes`); the code endpoint recomputes the current-lines hash and
the UI shows the badge on mismatch. No timestamp-based invalidation anywhere.

Trigger (D17.4): `mentor reindex` + `scripts/install_hook.py` (opt-in
post-commit hook). No webhook server in v1. Rollback: full `mentor index`
rebuild from scratch.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from mentor.ingest import filters as F
from mentor.ingest import manifest as M
from mentor.index import store as ST
from mentor.parse import config_extract as CE
from mentor.parse import parse_worker as W


def _git(repo: Path, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, timeout=timeout)


def git_head(repo: Path) -> str:
    """Committed HEAD SHA, or "" when unavailable (not a git repo)."""
    try:
        out = _git(repo, "rev-parse", "HEAD")
    except (subprocess.SubprocessError, OSError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_dirty_names(repo: Path) -> list[str]:
    """Working-tree paths with uncommitted changes (porcelain).

    Returns repo-relative posix paths. Untracked (`??`) entries are included
    (they are content the index has never seen). Never raises: [] on error.
    """
    try:
        out = _git(repo, "status", "--porcelain=v1", "-uall")
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode != 0:
        return []
    names: list[str] = []
    for line in out.stdout.splitlines():
        if len(line) < 4:
            continue
        code, rest = line[:2], line[3:]
        if code.strip() == "??":
            names.append(rest.strip().replace("\\", "/"))
            continue
        if " -> " in rest:  # rename in progress; take the new path
            rest = rest.split(" -> ", 1)[1]
        names.append(rest.strip().replace("\\", "/"))
    return sorted(set(names))


def git_diff_status(repo: Path, old: str, new: str = "HEAD") -> list[tuple]:
    """Parse `git diff --name-status -M old new` into tuples.

    Returns (status, path) for A/M/D/T, (R, old_path, new_path) for renames.
    Empty list when old == new, on error, or when either ref is missing.
    """
    if not old or not new:
        return []
    try:
        out = _git(repo, "diff", "--name-status", "-M", f"{old}", f"{new}")
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode != 0:
        return []
    rows: list[tuple] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        code = parts[0].strip()
        if code.startswith("R") and len(parts) == 3:
            rows.append(("R", parts[1].strip(), parts[2].strip()))
        elif len(parts) == 2:
            rows.append((code[:1], parts[1].strip()))
    return rows


def compute_changed(repo_root: Path, old_sha: str, manifest: dict) -> dict:
    """Changed set since the index was built.

    Committed changes come from `git diff old HEAD` (renames detected);
    uncommitted changes come from hashing dirty working-tree files against
    the manifest. Untracked files count as added. Result keys: head,
    dirty (bool), dirty_files, added, modified, deleted, renamed.
    """
    root = repo_root.resolve()
    head = git_head(root)
    by_path = {e["path"]: e for e in manifest.get("files", [])}
    added: set[str] = set()
    modified: set[str] = set()
    deleted: set[str] = set()
    renamed: list[list[str]] = []
    for row in git_diff_status(root, old_sha, head or "HEAD"):
        if row[0] == "R":
            _, src, dst = row
            renamed.append([src, dst])
            deleted.add(src)
            added.add(dst)
        elif row[0] == "A":
            added.add(row[1])
        elif row[0] == "D":
            deleted.add(row[1])
        else:  # M, T, ...
            modified.add(row[1])
    dirty_files: list[str] = []
    for rel in git_dirty_names(root):
        full = root / rel
        entry = by_path.get(rel)
        if entry is None or entry.get("skipped") is not None:
            if full.is_file() and not F.is_link(full):
                decision = F.decide_file(full, root)
                if decision.include:
                    added.add(rel)
                    dirty_files.append(rel)
            continue
        if not full.is_file() or F.is_link(full):
            deleted.add(rel)
            dirty_files.append(rel)
            continue
        if M.sha256_file(full) != entry.get("sha256"):
            modified.add(rel)
            dirty_files.append(rel)
    added -= deleted
    modified -= deleted
    modified -= added
    return {"head": head, "dirty": bool(dirty_files),
            "dirty_files": sorted(set(dirty_files)),
            "added": sorted(added), "modified": sorted(modified),
            "deleted": sorted(deleted), "renamed": sorted(renamed)}


def _delete_path_rows(con, sha: str, rel: str) -> None:
    con.execute("DELETE FROM files WHERE snapshot_sha = ? AND path = ?",
                (sha, rel))
    con.execute("DELETE FROM symbols WHERE snapshot_sha = ? AND path = ?",
                (sha, rel))
    con.execute("DELETE FROM imports WHERE snapshot_sha = ? AND path = ?",
                (sha, rel))
    con.execute("DELETE FROM routes WHERE snapshot_sha = ? AND file = ?",
                (sha, rel))
    con.execute("DELETE FROM models WHERE snapshot_sha = ? AND file = ?",
                (sha, rel))
    ids = [r[0] for r in con.execute(
        "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path = ?",
        (sha, rel)).fetchall()]
    con.execute("DELETE FROM chunks WHERE snapshot_sha = ? AND path = ?",
                (sha, rel))
    for cid in ids:
        con.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,))


def _manifest_entry_for(root: Path, rel: str) -> dict | None:
    """Fresh single-file manifest entry (None when now excluded)."""
    from mentor.ingest import secrets as S
    full = root / rel
    if F.is_link(full):
        return {"path": rel, "size": 0, "sha256": None,
                "language": "other", "skipped": "symlink"}
    decision = F.decide_file(full, root)
    if not decision.include:
        return {"path": rel, "size": 0, "sha256": None,
                "language": F.guess_language(full),
                "skipped": decision.reason}
    if S.scan_file(full):
        return {"path": rel, "size": int(full.stat().st_size),
                "sha256": M.sha256_file(full),
                "language": F.guess_language(full), "skipped": "secret"}
    return {"path": rel, "size": int(full.stat().st_size),
            "sha256": M.sha256_file(full),
            "language": F.guess_language(full), "skipped": None}


def reindex(repo_root: Path, index_path: Path, manifest_path: Path,
            parses_path: Path, old_sha: str,
            timeout_s: float = 10.0) -> dict:
    """Refresh only the rows affected by `compute_changed`.

    Manifest + parses JSON are rewritten to the indexed state; the index
    keeps its snapshot SHA (content follows the working tree) and records
    `index_head` / `index_dirty` / `dirty_files` in `meta`. Returns stats
    including `elapsed_s` (Phase 17 gate: < 60 s on the primary repo).
    """
    t0 = time.perf_counter()
    root = repo_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parses = json.loads(parses_path.read_text(encoding="utf-8"))
    changed = compute_changed(root, old_sha, manifest)
    touched = (set(changed["added"]) | set(changed["modified"])
               | set(changed["deleted"]))
    parseable = sorted(p for p in (set(changed["added"]) | set(changed["modified"]))
                       if (root / p).suffix.lower() in
                       {".py", ".ts", ".tsx", ".js", ".jsx"})
    new_parses = W.parse_many(root, parseable, timeout_s=timeout_s) if parseable else {}
    files_map: dict = parses.get("files", {})
    for rel in changed["deleted"]:
        files_map.pop(rel, None)
    files_map.update(new_parses)
    entries = {e["path"]: e for e in manifest.get("files", [])}
    for rel in changed["deleted"]:
        entries.pop(rel, None)
    for rel in sorted(set(changed["added"]) | set(changed["modified"])):
        full = root / rel
        if full.is_file():
            entry = _manifest_entry_for(root, rel)
            if entry is not None:
                entries[rel] = entry
        else:
            entries.pop(rel, None)
    manifest["files"] = sorted(entries.values(), key=lambda e: e["path"])
    manifest["count"] = len(manifest["files"])
    config = CE.extract_repo_config(root)
    from mentor.parse import cli as PC
    parses["files"] = files_map
    parses["routes"] = sorted(
        ({**r} for p, f in files_map.items() if f.get("status") == "parsed"
         for r in f.get("routes", [])),
        key=lambda r: (r["file"], r["decorator_line"]))
    parses["models"] = PC.join_models(files_map)
    parses["config"] = config
    con = ST._connect(index_path)
    try:
        with con:
            for rel in sorted(touched):
                _delete_path_rows(con, old_sha, rel)
            con.execute("DELETE FROM edges WHERE snapshot_sha = ?", (old_sha,))
            con.execute("DELETE FROM config_facts WHERE snapshot_sha = ?",
                        (old_sha,))
        stats = {"files": 0, "chunks": 0, "symbols": 0, "failed": []}
        for rel in sorted(set(changed["added"]) | set(changed["modified"])):
            entry = entries.get(rel)
            if entry is None or entry.get("skipped") is not None:
                continue
            with con:
                ST._index_file(con, root, old_sha, entry,
                               files_map.get(rel), timeout_s, stats)
        with con:
            ST.attach_edges_and_config(con, old_sha, parses)
            row = con.execute("SELECT file_count FROM snapshots WHERE sha = ?",
                              (old_sha,)).fetchone()
            if row is None:
                con.execute("INSERT INTO snapshots(sha, repo_id, file_count)"
                            " VALUES (?, ?, ?)", (old_sha, "fst", manifest["count"]))
            else:
                con.execute("UPDATE snapshots SET file_count = ? WHERE sha = ?",
                            (manifest["count"], old_sha))
            con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES "
                        "('index_head', ?)", (changed["head"],))
            con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES "
                        "('index_dirty', ?)", ("1" if changed["dirty"] else "0",))
            con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES "
                        "('dirty_files', ?)", (json.dumps(changed["dirty_files"]),))
            con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
    finally:
        con.close()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    parses_path.write_text(json.dumps(parses, indent=1), encoding="utf-8")
    elapsed = time.perf_counter() - t0
    return {"added": changed["added"], "modified": changed["modified"],
            "deleted": changed["deleted"], "renamed": changed["renamed"],
            "dirty": changed["dirty"], "dirty_files": changed["dirty_files"],
            "head": changed["head"], "reparsed": sorted(new_parses),
            "files": stats["files"], "chunks": stats["chunks"],
            "symbols": stats["symbols"], "failed": stats["failed"],
            "elapsed_s": round(elapsed, 2)}


def index_status(repo_root: Path, index_path: Path, sha: str) -> dict:
    """Freshness signal for the status endpoint / status bar.

    The index `files` table is the source of truth (never the manifest
    file, which may not exist for ad-hoc snapshots): every indexed file is
    re-hashed against the working tree, plus untracked additions via
    `git status`. Never raises (defaults on non-git repos).
    """
    import sqlite3
    out: dict = {"indexed_sha": sha, "head": "", "dirty": False,
                 "dirty_files": [], "changed": [], "indexed_head": "",
                 "index_dirty": False}
    root = repo_root.resolve()
    try:
        out["head"] = git_head(root)
    except Exception:
        pass
    try:
        con = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT path, sha256, skipped FROM files"
                               " WHERE snapshot_sha = ?", (sha,)).fetchall()
            meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        finally:
            con.close()
    except Exception:
        return out
    out["indexed_head"] = meta.get("index_head", "")
    out["index_dirty"] = meta.get("index_dirty", "0") == "1"
    changed: set[str] = set()
    dirty: set[str] = set()
    indexed = {path for path, _, _ in rows}
    for path, want, skipped in rows:
        if skipped is not None or want is None:
            continue
        full = root / path
        try:
            if not full.is_file() or F.is_link(full):
                changed.add(path)
                dirty.add(path)
            elif M.sha256_file(full) != want:
                changed.add(path)
                dirty.add(path)
        except OSError:
            changed.add(path)
            dirty.add(path)
    try:
        for rel in git_dirty_names(root):
            if rel in indexed:
                continue
            full = root / rel
            try:
                if full.is_file() and not F.is_link(full) \
                        and F.decide_file(full, root).include:
                    changed.add(rel)
                    dirty.add(rel)
            except OSError:
                continue
    except Exception:
        pass
    out["dirty"] = bool(dirty)
    out["dirty_files"] = sorted(dirty)
    out["changed"] = sorted(changed)
    return out


def tours_affected(cache_dir: Path, changed_paths: list[str]) -> list[str]:
    """Cached tour names whose recorded dep set intersects `changed_paths`."""
    changed = set(changed_paths)
    hit: list[str] = []
    for path in sorted(cache_dir.glob("tour_*.json")):
        try:
            tour = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        deps = set((tour.get("dep_hashes") or {}).keys())
        if deps & changed:
            hit.append(tour.get("name", path.stem))
    return sorted(hit)


def content_stale(index_path: Path, sha: str, path: str, lines: str,
                  current_text: str) -> bool:
    """True when the working-tree text no longer matches the indexed chunk.

    Compares sha256(current_text) against the stored `content_hash` for the
    exact (path, lines) chunk. Missing rows read as stale (fail-visible).
    """
    import sqlite3
    try:
        start, end = (int(x) for x in lines.split("-", 1))
    except ValueError:
        return True
    con = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT content_hash FROM chunks"
                          " WHERE snapshot_sha = ? AND path = ?"
                          " AND start_line = ? AND end_line = ?",
                          (sha, path, start, end)).fetchone()
    finally:
        con.close()
    if row is None:
        return True
    digest = hashlib.sha256(current_text.encode("utf-8")).hexdigest()
    return digest != row[0]

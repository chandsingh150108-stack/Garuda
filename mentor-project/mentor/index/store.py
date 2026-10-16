"""SQLite index store (spec Phase 4).

Builds one SQLite file per repository from the Phase 2 manifest and Phase 3
parses: files, symbols, imports, edges, routes, models, config facts, chunks
(with FTS5 rows). One transaction per file. Parameterized queries only —
repository content is untrusted. No wall-clock values are stored, so two
builds of identical input are byte-comparable.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

from mentor.index import chunker as K

SCHEMA_VERSION = 2
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def chunk_text_from_lines(repo_root: Path, path: str, start: int, end: int) -> str:
    """Reproduce a chunk's stored `text` exactly from source lines.

    The single reconstruction function every later citation uses.
    """
    raw = (repo_root.resolve() / path).read_bytes().decode("utf-8", errors="replace")
    return "\n".join(raw.splitlines()[start - 1:end])


def _connect(out: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(out))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(out: Path) -> sqlite3.Connection:
    if out.exists():
        raise FileExistsError(f"refusing to overwrite: {out} (delete and rebuild)")
    out.parent.mkdir(parents=True, exist_ok=True)
    con = _connect(out)
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    con.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),))
    con.commit()
    return con


def ensure_service_tables(con) -> None:
    """Additively create Phase 10 service tables if missing.

    Content tables are untouched, so indexes built at version 1 gain audit +
    cache without a rebuild (recorded D10 decision). Fresh builds already have
    them via schema.sql (version 2).
    """
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    for name in ("audit", "cache"):
        start = ddl.index(f"CREATE TABLE {name} (")
        end = ddl.index(");", start) + len(");")
        stmt = ddl[start:end].replace(f"CREATE TABLE {name} (",
                                      f"CREATE TABLE IF NOT EXISTS {name} (", 1)
        con.execute(stmt)
    con.commit()


def _jdump(value) -> str:
    return json.dumps(value, sort_keys=True)


def build(repo_root: Path, manifest_path: Path, parses_path: Path, out: Path,
          repo_id: str = "fst", timeout_s: float = 10.0) -> dict:
    """Build the index. Returns stats {files, chunks, symbols, failed}."""
    root = repo_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parses = json.loads(parses_path.read_text(encoding="utf-8"))
    sha = manifest["sha"]
    parsed_files: dict = parses.get("files", {})
    config = parses.get("config", {})
    con = init_db(out)
    stats = {"files": 0, "chunks": 0, "symbols": 0, "failed": []}
    try:
        with con:
            con.execute("INSERT INTO repos(id, name) VALUES (?, ?)", (repo_id, repo_id))
            con.execute("INSERT INTO snapshots(sha, repo_id, file_count) VALUES (?, ?, ?)",
                        (sha, repo_id, manifest["count"]))
        indexed = [e for e in manifest["files"] if e.get("skipped") is None]
        total = len(indexed)
        t0 = time.monotonic()
        for i, entry in enumerate(sorted(indexed, key=lambda e: e["path"]), start=1):
            _index_file(con, root, sha, entry, parsed_files.get(entry["path"]),
                        timeout_s, stats)
            if i == total or i % 50 == 0:
                dt = time.monotonic() - t0
                print(f"index {i}/{total} files={stats['files']} "
                      f"chunks={stats['chunks']} {dt:.1f}s",
                      file=sys.stderr, flush=True)
        attach_edges_and_config(con, sha, parses)
        with con:
            con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
    finally:
        con.close()
    return stats


def _index_file(con: sqlite3.Connection, root: Path, sha: str, entry: dict,
                parsed: dict | None, timeout_s: float, stats: dict):
    rel = entry["path"]
    suffix = Path(rel).suffix.lower()
    language = {".py": "python", ".ts": "typescript", ".tsx": "tsx",
                ".js": "tsx", ".jsx": "tsx"}.get(suffix, "text")
    symbols = (parsed or {}).get("symbols", []) if parsed else []
    res = K.chunk_file(root, rel, symbols, timeout_s)
    if res.get("status") != "ok":
        stats["failed"].append({"path": rel, "reason": res.get("reason")})
        with con:
            con.execute(
                "INSERT INTO files(snapshot_sha, path, size, sha256, language, skipped)"
                " VALUES (?, ?, ?, ?, ?, 'chunk_failed')",
                (sha, rel, entry.get("size", 0), entry.get("sha256"), language))
        return
    chunks = K.assemble(sha, rel, res["spans"], symbols, res["lines"])
    parsed = parsed or {}
    with con:  # one transaction per file
        con.execute(
            "INSERT INTO files(snapshot_sha, path, size, sha256, language, skipped)"
            " VALUES (?, ?, ?, ?, ?, NULL)",
            (sha, rel, entry.get("size", 0), entry.get("sha256"), language))
        con.executemany(
            "INSERT INTO symbols(snapshot_sha, path, qualname, kind, name, parent,"
            " start_line, end_line, signature_line, docstring, params, bases_json,"
            " decorators_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(sha, rel, s["qualname"], s["kind"], s["name"], s.get("parent"),
              s["start_line"], s["end_line"], s["signature_line"], s.get("docstring"),
              s.get("params"), _jdump(s.get("bases")), _jdump(s.get("decorators", [])))
             for s in symbols])
        con.executemany(
            "INSERT INTO imports(snapshot_sha, path, module, names_json, line, level, resolved)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(sha, rel, i["module"], _jdump(i.get("names", [])), i["line"],
              i.get("level", 0), i.get("resolved")) for i in parsed.get("imports", [])])
        con.executemany(
            "INSERT INTO routes(snapshot_sha, file, method, path, handler, handler_start,"
            " handler_end, decorator_line, router_var, router_prefix, prefix_unknown)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(sha, r.get("file", rel), r["method"], r.get("path"), r["handler"],
              r["handler_lines"][0], r["handler_lines"][1], r["decorator_line"],
              r.get("router_var"), r.get("router_prefix"), int(bool(r.get("prefix_unknown"))))
             for r in parsed.get("routes", [])])
        con.executemany(
            "INSERT INTO models(snapshot_sha, file, class, qualname, start_line, end_line,"
            " table_name, table_inferred, bases_json, fields_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(sha, m.get("file", rel), m["class"], m["qualname"], m["lines"][0],
              m["lines"][1], m["table"], int(bool(m.get("table_inferred"))),
              _jdump(m.get("bases", [])), _jdump(m.get("fields", [])))
             for m in parsed.get("models", [])])
        # NOTE: repo-wide edges + config facts are written once after the file
        # loop by attach_edges_and_config (Phase 3 CLI already aggregates them
        # at parses["edges"] / parses["config"]).
        for c in chunks:
            con.execute(
                "INSERT INTO chunks(chunk_id, snapshot_sha, path, start_line, end_line,"
                " method, header, text, embed_text, identifiers, content_hash,"
                " approx_tokens, is_exception)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (c["chunk_id"], sha, c["path"], c["start_line"], c["end_line"],
                 c["method"], c["header"], c["text"], c["embed_text"], c["identifiers"],
                 c["content_hash"], c["approx_tokens"], int(bool(c["is_exception"]))))
            con.execute(
                "INSERT INTO chunks_fts(chunk_id, header, identifiers, text)"
                " VALUES (?, ?, ?, ?)",
                (c["chunk_id"], c["header"], c["identifiers"], c["text"]))
    stats["files"] += 1
    stats["chunks"] += len(chunks)
    stats["symbols"] += len(symbols)


def attach_edges_and_config(con: sqlite3.Connection, sha: str, parses: dict):
    """Write repo-wide edges + config facts (called by build_from_parses)."""
    from mentor.parse import edges as E
    files = {p: f for p, f in parses.get("files", {}).items()
             if f.get("status") == "parsed"}
    edge_data = E.build_edges(files)
    rows = []
    for e in edge_data["imports"] + edge_data["calls"]:
        rows.append((sha, e["kind"], e["label"], e.get("from", e.get("from_file", "")),
                     e.get("to", e.get("to_file")),
                     _jdump({k: v for k, v in e.items()
                             if k not in ("kind", "label", "from", "to")})))
    with con:
        con.executemany(
            "INSERT INTO edges(snapshot_sha, kind, label, from_ref, to_ref, detail_json)"
            " VALUES (?, ?, ?, ?, ?, ?)", rows)
        for kind, group in (("compose", parses.get("config", {}).get("compose", {})),
                            ("pyproject", parses.get("config", {}).get("pyproject", {})),
                            ("package_json", parses.get("config", {}).get("package_json", {}))):
            for file, data in group.items():
                con.execute(
                    "INSERT INTO config_facts(snapshot_sha, file, kind, data_json)"
                    " VALUES (?, ?, ?, ?)", (sha, file, kind, _jdump(data)))


def query_fts(db: Path, text: str, limit: int = 10) -> list[dict]:
    """BM25 lexical lookup over the FTS table (Phase 5 will build on this)."""
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute(
            "SELECT chunk_id, header, bm25(chunks_fts) AS rank FROM chunks_fts"
            " WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (text, limit)).fetchall()
        return [{"chunk_id": r[0], "header": r[1], "rank": r[2]} for r in rows]
    finally:
        con.close()


def table_counts(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    try:
        tables = ["repos", "snapshots", "files", "symbols", "imports", "edges",
                  "routes", "models", "config_facts", "chunks", "artifacts", "audit_log"]
        out = {}
        for t in tables:
            out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        out["chunks_fts"] = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        return out
    finally:
        con.close()


def dump_rows(db: Path) -> str:
    """Deterministic full dump for idempotence comparison (no timestamps stored)."""
    con = sqlite3.connect(str(db))
    try:
        parts = []
        for t in ["meta", "repos", "snapshots", "files", "symbols", "imports", "edges",
                  "routes", "models", "config_facts", "chunks", "chunks_fts",
                  "artifacts", "audit_log"]:
            if t == "chunks_fts":
                rows = con.execute(
                    "SELECT chunk_id, header, identifiers, text FROM chunks_fts"
                    " ORDER BY chunk_id").fetchall()
            else:
                rows = con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
            parts.append(f"== {t} ==\n" + "\n".join(repr(r) for r in rows))
        return "\n".join(parts)
    finally:
        con.close()

"""Phase 4 gate: SQLite store end-to-end + fst artifact gates (spec Phase 4).

Tmp-repo tests build tiny indexes through the real manifest/extract/chunk
path (extracts run in-process on snippets). fst tests verify the gate
artifact `data/indexes/fst.sqlite` (built via `python -m mentor.cli index`
then `... --out ...fst-check.sqlite`); they skip with the exact build
commands when the artifacts are absent.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from mentor.index import store as S
from mentor.ingest import manifest as M
from mentor.parse import py_extract as P

ROOT = Path(__file__).resolve().parent.parent
PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
FST_DB = ROOT / "data" / "indexes" / "fst.sqlite"
FST_CHECK_DB = ROOT / "data" / "indexes" / "fst-check.sqlite"


def _tiny_repo(root: Path) -> None:
    (root / "app.py").write_text(
        '"""Greeter."""\nimport os\n\n\ndef greet(name):\n'
        '    """Say hi."""\n    return "hi " + name + os.sep\n',
        encoding="utf-8")
    (root / "doc.md").write_text("# Doc\n\nSome words here.\n", encoding="utf-8")


def _repo_for(tmp_path: Path, out_name: str = "idx.sqlite") -> Path:
    return tmp_path / f"repo_{out_name.replace('.', '_')}"


def _build_tmp(tmp_path: Path, out_name: str = "idx.sqlite") -> Path:
    repo = _repo_for(tmp_path, out_name)
    repo.mkdir()
    _tiny_repo(repo)
    manifest = M.build_manifest(repo, "testsha")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    files = {}
    for entry in manifest["files"]:
        if entry.get("skipped") is not None:
            continue
        p = repo / entry["path"]
        if p.suffix == ".py":
            files[entry["path"]] = P.extract_py(p, p.read_bytes(), repo)
    parses = {"sha": "testsha", "files": files, "routes": [], "models": [],
              "include_routers": [], "edges": {"imports": [], "calls": []},
              "config": {"compose": {}, "pyproject": {}, "package_json": {}}}
    (tmp_path / "parses.json").write_text(json.dumps(parses), encoding="utf-8")
    out = tmp_path / out_name
    stats = S.build(repo, tmp_path / "manifest.json", tmp_path / "parses.json", out,
                    repo_id="t")
    assert stats["failed"] == []
    return out


def test_build_counts_match_manifest(tmp_path: Path):
    out = _build_tmp(tmp_path)
    counts = S.table_counts(out)
    assert counts["files"] == 2
    assert counts["chunks"] == counts["chunks_fts"] > 0
    assert counts["symbols"] == 1  # greet only (imports are not symbols)
    assert counts["edges"] == 1  # the single unresolved `import os` edge


def test_idempotent_rebuild(tmp_path: Path):
    a = _build_tmp(tmp_path, "a.sqlite")
    b = _build_tmp(tmp_path, "b.sqlite")
    assert S.dump_rows(a) == S.dump_rows(b)


def test_reconstruction_tmp(tmp_path: Path):
    out = _build_tmp(tmp_path)
    repo = _repo_for(tmp_path)
    con = sqlite3.connect(str(out))
    try:
        rows = con.execute("SELECT path, start_line, end_line, text FROM chunks").fetchall()
    finally:
        con.close()
    assert rows
    for path, start, end, text in rows:
        assert S.chunk_text_from_lines(repo, path, start, end) == text


def test_fts_finds_identifier_tmp(tmp_path: Path):
    out = _build_tmp(tmp_path)
    hits = S.query_fts(out, "greet")
    assert hits and all("app.py" in h["header"] for h in hits)


def test_budget_tmp(tmp_path: Path):
    out = _build_tmp(tmp_path)
    con = sqlite3.connect(str(out))
    try:
        bad = con.execute(
            "SELECT chunk_id FROM chunks WHERE approx_tokens > 512 AND is_exception = 0"
        ).fetchall()
    finally:
        con.close()
    assert bad == []


def test_no_embed_text_in_text_column(tmp_path: Path):
    out = _build_tmp(tmp_path)
    con = sqlite3.connect(str(out))
    try:
        rows = con.execute("SELECT header, text, embed_text FROM chunks").fetchall()
    finally:
        con.close()
    assert rows
    for header, text, embed in rows:
        assert embed == header + "\n" + text
        # Failure condition: text must never BE the embed form (header would
        # leak into displayed citations).
        assert text != embed and not text.startswith(header + "\n")


def _fst_db():
    if not FST_DB.is_file():
        pytest.skip("run: python -m mentor.cli index --repo data/repos/fst "
                    f"--sha {PINNED_SHA} --out data/indexes/fst.sqlite")
    return FST_DB


def test_fst_counts_match_manifest():
    _fst_db()
    counts = S.table_counts(FST_DB)
    manifest = json.loads((ROOT / "data" / "manifests" / f"{PINNED_SHA}.json").read_text())
    indexed = sum(1 for f in manifest["files"] if f.get("skipped") is None)
    assert counts["files"] == indexed
    assert counts["chunks"] == counts["chunks_fts"] > 0
    assert counts["symbols"] > 100
    assert counts["routes"] == 23
    assert counts["models"] == 2


def test_fst_reconstruction_every_chunk():
    _fst_db()
    repo = ROOT / "data" / "repos" / "fst"
    cache: dict[str, list[str]] = {}
    con = sqlite3.connect(str(FST_DB))
    try:
        rows = con.execute("SELECT path, start_line, end_line, text FROM chunks").fetchall()
    finally:
        con.close()
    assert rows
    bad = 0
    for path, start, end, text in rows:
        lines = cache.get(path)
        if lines is None:
            lines = (repo / path).read_text(encoding="utf-8",
                                            errors="replace").splitlines()
            cache[path] = lines
        if "\n".join(lines[start - 1:end]) != text:
            bad += 1
    assert bad == 0


def test_fst_coverage_top_level():
    _fst_db()
    parses = json.loads((ROOT / "data" / "parses" / f"{PINNED_SHA}.json").read_text())
    con = sqlite3.connect(str(FST_DB))
    try:
        spans = con.execute("SELECT path, start_line, end_line FROM chunks").fetchall()
    finally:
        con.close()
    by_path: dict[str, list[tuple[int, int]]] = {}
    for path, s, e in spans:
        by_path.setdefault(path, []).append((s, e))
    gaps = []
    for rel, parsed in parses["files"].items():
        if parsed.get("status") != "parsed":
            continue
        cov = by_path.get(rel, [])
        for sym in parsed.get("symbols", []):
            if sym.get("parent") is not None:
                continue
            for ln in range(sym["start_line"], sym["end_line"] + 1):
                if not any(s <= ln <= e for s, e in cov):
                    gaps.append(f"{rel}:{ln} ({sym['qualname']})")
    assert gaps == []


def test_fst_fts_signup():
    _fst_db()
    hits = S.query_fts(FST_DB, "register_user")
    assert hits
    assert any("routes/users.py" in h["header"] for h in hits)


def test_fst_budget():
    _fst_db()
    con = sqlite3.connect(str(FST_DB))
    try:
        bad = con.execute(
            "SELECT chunk_id, path FROM chunks WHERE approx_tokens > 512 AND is_exception = 0"
        ).fetchall()
    finally:
        con.close()
    assert bad == [], bad[:5]


def test_fst_second_build_identical():
    _fst_db()
    if not FST_CHECK_DB.is_file():
        pytest.skip("run: python -m mentor.cli index --repo data/repos/fst "
                    f"--sha {PINNED_SHA} --out data/indexes/fst-check.sqlite")
    assert S.dump_rows(FST_DB) == S.dump_rows(FST_CHECK_DB)

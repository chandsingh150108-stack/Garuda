"""Phase 17 gate: incremental freshness — scenario, negative, positive,
rename, dirty-tree, and the <60 s reindex timing on the primary repo."""
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from mentor.index import freshness as FR
from mentor.index import store as ST
from mentor.ingest import manifest as M
from mentor.parse import cli as PC
from mentor.parse import config_extract as CE
from mentor.parse import parse_worker as W

A_PY = '''"""Fixture module a."""


def alpha(x):
    """Double the input."""
    return x * 2


def beta(x):
    return alpha(x) + 1
'''

B_PY = '''"""Fixture module b (imports a)."""
from pkg.a import alpha


def gamma(x):
    return alpha(x) * 10
'''

NOTES_MD = "# notes\n\nNothing to see here.\n"


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, f"git {args}: {out.stderr}"
    return out.stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def build_fixture(tmp_path: Path) -> dict:
    """Tiny git repo + manifest + parses + index. Returns paths + sha."""
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "a.py").write_text(A_PY, encoding="utf-8")
    (repo / "pkg" / "b.py").write_text(B_PY, encoding="utf-8")
    (repo / "notes.md").write_text(NOTES_MD, encoding="utf-8")
    git(repo, "init", "-q")
    sha = commit_all(repo, "initial")
    manifest = M.build_manifest(repo, sha)
    manifest_path = tmp_path / "m.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rels = [e["path"] for e in manifest["files"] if e.get("skipped") is None
             and Path(e["path"]).suffix.lower() == ".py"]
    files = W.parse_many(repo, rels, timeout_s=10.0)
    assert all(v.get("status") == "parsed" for v in files.values()), files
    parses = {"sha": sha, "files": files, "routes": [],
              "models": PC.join_models(files),
              "config": CE.extract_repo_config(repo)}
    parses_path = tmp_path / "p.json"
    parses_path.write_text(json.dumps(parses), encoding="utf-8")
    index = tmp_path / "f.sqlite"
    stats = ST.build(repo, manifest_path, parses_path, index, repo_id="fresh")
    assert stats["failed"] == []
    return {"repo": repo, "sha": sha, "manifest": manifest_path,
            "parses": parses_path, "index": index}


def chunk_texts(index: Path, sha: str, rel: str) -> dict:
    con = sqlite3.connect(str(index))
    try:
        rows = con.execute("SELECT start_line, end_line, text, content_hash"
                           " FROM chunks WHERE snapshot_sha = ? AND path = ?"
                           " ORDER BY start_line", (sha, rel)).fetchall()
    finally:
        con.close()
    return {(r[0], r[1]): (r[2], r[3]) for r in rows}


def files_rows(index: Path, sha: str) -> dict:
    con = sqlite3.connect(str(index))
    try:
        rows = con.execute("SELECT path, sha256 FROM files"
                           " WHERE snapshot_sha = ?", (sha,)).fetchall()
    finally:
        con.close()
    return dict(rows)


def test_scenario_edit_reindex_marks_old_citation_stale(tmp_path):
    fx = build_fixture(tmp_path)
    before = chunk_texts(fx["index"], fx["sha"], "pkg/a.py")
    assert before
    key = sorted(before)[0]
    old_text, old_hash = before[key]
    (fx["repo"] / "pkg" / "a.py").write_text(
        A_PY.replace("return x * 2", "return x * 3"), encoding="utf-8")
    stats = FR.reindex(fx["repo"], fx["index"], fx["manifest"],
                       fx["parses"], fx["sha"])
    assert "pkg/a.py" in stats["modified"] and stats["dirty"]
    after = chunk_texts(fx["index"], fx["sha"], "pkg/a.py")
    assert after != before  # the chunk changed
    lines = f"{key[0]}-{key[1]}"
    assert FR.content_stale(fx["index"], fx["sha"], "pkg/a.py", lines,
                            old_text)  # old cite now stale
    new_text = after.get(key, (None,))[0]
    if new_text is not None and new_text != old_text:
        assert not FR.content_stale(fx["index"], fx["sha"], "pkg/a.py",
                                    lines, new_text)


def test_negative_unrelated_edit_keeps_artifact_valid(tmp_path):
    from mentor.features import tours as T
    fx = build_fixture(tmp_path)
    tour = {"name": "demo", "steps": [{"file": "pkg/a.py"}]}
    tour["dep_hashes"] = T.dep_hashes(fx["index"], fx["sha"], tour)
    assert not T.is_stale(fx["index"], fx["sha"], tour)
    (fx["repo"] / "notes.md").write_text(NOTES_MD + "\nMore notes.\n",
                                         encoding="utf-8")
    stats = FR.reindex(fx["repo"], fx["index"], fx["manifest"],
                       fx["parses"], fx["sha"])
    assert "notes.md" in stats["modified"]
    assert not T.is_stale(fx["index"], fx["sha"], tour)  # untouched dep


def test_positive_dep_edit_marks_tour_stale_and_affected(tmp_path):
    from mentor.features import tours as T
    fx = build_fixture(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    tour = {"name": "demo", "question": "q", "sha": fx["sha"],
            "steps": [{"file": "pkg/a.py"}]}
    tour["dep_hashes"] = T.dep_hashes(fx["index"], fx["sha"], tour)
    (cache / "tour_fresh_demo.json").write_text(json.dumps(tour),
                                               encoding="utf-8")
    (fx["repo"] / "pkg" / "a.py").write_text(A_PY + "\n\nEXTRA = 1\n",
                                             encoding="utf-8")
    stats = FR.reindex(fx["repo"], fx["index"], fx["manifest"],
                       fx["parses"], fx["sha"])
    assert T.is_stale(fx["index"], fx["sha"], tour)  # dep changed
    assert FR.tours_affected(cache, stats["added"] + stats["modified"]
                             + stats["deleted"]) == ["demo"]


def test_rename_handled_as_move_without_orphans(tmp_path):
    fx = build_fixture(tmp_path)
    assert chunk_texts(fx["index"], fx["sha"], "pkg/b.py")
    git(fx["repo"], "mv", "pkg/b.py", "pkg/c.py")
    commit_all(fx["repo"], "rename b to c")
    stats = FR.reindex(fx["repo"], fx["index"], fx["manifest"],
                       fx["parses"], fx["sha"])
    assert ["pkg/b.py", "pkg/c.py"] in stats["renamed"] or (
        "pkg/b.py" in stats["deleted"] and "pkg/c.py" in stats["added"])
    assert chunk_texts(fx["index"], fx["sha"], "pkg/b.py") == {}  # no orphans
    assert chunk_texts(fx["index"], fx["sha"], "pkg/c.py")
    assert "pkg/b.py" not in files_rows(fx["index"], fx["sha"])


def test_dirty_tree_records_flag_and_hashes(tmp_path):
    fx = build_fixture(tmp_path)
    (fx["repo"] / "pkg" / "a.py").write_text(A_PY + "DIRTY = True\n",
                                             encoding="utf-8")
    manifest = json.loads(fx["manifest"].read_text(encoding="utf-8"))
    changed = FR.compute_changed(fx["repo"], fx["sha"], manifest)
    assert changed["dirty"] and changed["dirty_files"] == ["pkg/a.py"]
    assert "pkg/a.py" in changed["modified"]
    FR.reindex(fx["repo"], fx["index"], fx["manifest"], fx["parses"],
               fx["sha"])
    con = sqlite3.connect(str(fx["index"]))
    try:
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    finally:
        con.close()
    assert meta.get("index_dirty") == "1"
    assert "pkg/a.py" in json.loads(meta.get("dirty_files", "[]"))


def test_reindex_primary_repo_under_60s(tmp_path):
    """Gate timing on tmp copies (pinned index untouched, scratch reverted)."""
    src_index = Path("data/indexes/fst.sqlite")
    if not src_index.is_file():
        pytest.skip("primary index missing")
    index = tmp_path / "fst-timing.sqlite"
    shutil.copy(src_index, index)
    manifest_src = Path("data/manifests/7257e606cb94eada1dca40173e2b7f99dd549bc6.json")
    parses_src = Path("data/parses/7257e606cb94eada1dca40173e2b7f99dd549bc6.json")
    manifest = tmp_path / "m.json"
    parses = tmp_path / "p.json"
    shutil.copy(manifest_src, manifest)
    shutil.copy(parses_src, parses)
    repo = Path("data/repos/fst").resolve()
    scratch = repo / "demo_live_edit_scratch.py"
    scratch.write_text('"""Timing scratch (untracked, removed after test)."""\n'
                       "\nTIMING_SCRATCH = True\n", encoding="utf-8")
    try:
        stats = FR.reindex(repo, index, manifest, parses,
                           "7257e606cb94eada1dca40173e2b7f99dd549bc6")
    finally:
        scratch.unlink(missing_ok=True)
    assert stats["added"] == ["demo_live_edit_scratch.py"]
    assert stats["elapsed_s"] < 60, f"too slow: {stats['elapsed_s']}s"

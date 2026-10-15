"""Phase 17 gate: stale citations fail visible via the API.

An edited working tree makes previously-attached evidence hashes mismatch;
the code endpoint recomputes the current hash and the status endpoint
reports the dirty working tree.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from mentor.api import app as APP
from mentor.api import routes as R
from mentor.index import freshness as FR
from tests.test_freshness import build_fixture, chunk_texts


def _client(fx) -> TestClient:
    R.REGISTRY.clear()
    R.REGISTRY["fresh"] = {"id": "fresh", "path": str(fx["repo"].resolve()),
                           "sha": fx["sha"], "index": str(fx["index"])}
    return TestClient(APP.create_app())


def test_edited_lines_read_as_stale_through_api(tmp_path):
    fx = build_fixture(tmp_path)
    client = _client(fx)
    try:
        before = chunk_texts(fx["index"], fx["sha"], "pkg/a.py")
        key = sorted(before)[0]
        lines = f"{key[0]}-{key[1]}"
        r = client.get("/api/repos/fresh/code",
                       params={"path": "pkg/a.py", "start": key[0],
                               "end": key[1]})
        assert r.status_code == 200
        assert not FR.content_stale(fx["index"], fx["sha"], "pkg/a.py",
                                    lines, r.json()["text"])
        (fx["repo"] / "pkg" / "a.py").write_text(
            (fx["repo"] / "pkg" / "a.py").read_text(encoding="utf-8")
            .replace("return x * 2", "return x * 3"), encoding="utf-8")
        r2 = client.get("/api/repos/fresh/code",
                        params={"path": "pkg/a.py", "start": key[0],
                                "end": key[1]})
        assert r2.status_code == 200
        # The old evidence hash no longer matches the current lines: this
        # mismatch is exactly what the UI stale badge checks.
        assert r2.json()["content_hash"] != before[key][1]
        assert FR.content_stale(fx["index"], fx["sha"], "pkg/a.py", lines,
                                r2.json()["text"])  # current vs index: stale
    finally:
        R.REGISTRY.clear()


def test_status_reports_dirty_working_tree(tmp_path):
    fx = build_fixture(tmp_path)
    client = _client(fx)
    try:
        body = client.get("/api/repos/fresh/status").json()
        assert body["dirty"] is False and body["changed"] == []
        (fx["repo"] / "notes.md").write_text("# notes\n\nEdited.\n",
                                             encoding="utf-8")
        body = client.get("/api/repos/fresh/status").json()
        assert body["dirty"] is True
        assert "notes.md" in body["changed"]
        assert "notes.md" in body["dirty_files"]
    finally:
        R.REGISTRY.clear()


def test_missing_chunk_reads_as_stale_not_valid(tmp_path):
    fx = build_fixture(tmp_path)
    assert FR.content_stale(fx["index"], fx["sha"], "pkg/a.py", "999-1005",
                            "whatever") is True
    assert FR.content_stale(fx["index"], fx["sha"], "nope.py", "1-9",
                            "whatever") is True

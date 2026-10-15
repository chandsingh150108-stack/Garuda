"""Phase 10 gate: service boundary — bind, confinement, range cap, typing."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mentor.api import app as APP
from mentor.api import routes as R
from mentor import config as CFG

SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        return self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]


@pytest.fixture()
def client(tmp_path):
    import sqlite3
    R.REGISTRY.clear()
    src = Path("data/indexes/fst.sqlite")
    db = tmp_path / "t.sqlite"
    shutil.copy(src, db)
    con = sqlite3.connect(str(db))
    try:
        con.execute("DELETE FROM audit")
        con.execute("DELETE FROM cache")
        con.commit()
    finally:
        con.close()
    R.REGISTRY["t"] = {"id": "t", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    R.adapter_factory = lambda: ScriptAdapter(
        ['{"status": "abstain", "segments": [], "missing": ["test"]}'])
    yield TestClient(APP.create_app())
    R.REGISTRY.clear()


def test_bind_refuses_non_loopback_without_flag():
    with pytest.raises(APP.BindRefused):
        APP.resolve_bind("0.0.0.0", False)
    assert APP.resolve_bind("0.0.0.0", True) == "0.0.0.0"
    assert APP.resolve_bind("127.0.0.1", False) == "127.0.0.1"


def test_register_and_status_typed(client):
    r = client.post("/api/repos", json={"path": "data/repos/fst",
                                        "sha": SHA, "id": "t2"})
    assert r.status_code == 200
    assert r.json()["sha"] == SHA
    r = client.get("/api/repos/t/status")
    assert r.status_code == 200
    body = r.json()
    assert body["repo_id"] == "t" and body["chunks"] > 1000


def test_path_confinement(client):
    r = client.get("/api/repos/t/code", params={"path": "../../etc/passwd"})
    assert r.status_code in (400, 404)
    r = client.get("/api/repos/t/code",
                   params={"path": "backend/app/main.py", "start": 1, "end": 5})
    assert r.status_code == 200
    assert r.json()["sha"] == SHA
    assert len(r.json()["text"].splitlines()) <= 5


def test_range_cap_truncates(client):
    r = client.get("/api/repos/t/code",
                   params={"path": "frontend/src/client/types.gen.ts",
                           "start": 1, "end": 100000})
    assert r.status_code == 200
    body = r.json()
    assert body["truncated"] is True
    assert len(body["text"].splitlines()) == R.CODE_RANGE_CAP


def test_oversize_body_rejected(client):
    big = "x" * (CFG.MAX_BODY_BYTES + 1)
    r = client.post("/api/repos/t/ask", json={"question": big})
    assert r.status_code == 413

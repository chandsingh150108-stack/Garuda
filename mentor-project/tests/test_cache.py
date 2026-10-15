"""Phase 10 gate: answer cache — validated answers cached, SHA change misses,
abstentions never cached (spec Phase 10, D10.3)."""
import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from mentor.answer import cache as CA
from mentor.api import app as APP
from mentor.api import routes as R
from mentor import config as CFG

SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"

GOOD = ('{"status": "answer", "segments": '
        '[{"text": "registration uses `register_user`", "kind": "fact", '
        '"evidence_ids": ["E1"]}], "missing": []}')
ABS = '{"status": "abstain", "segments": [], "missing": ["weak"]}'


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        return self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]


def _client(tmp_path, outcome):
    R.REGISTRY.clear()
    db = tmp_path / "c.sqlite"
    shutil.copy(Path("data/indexes/fst.sqlite"), db)
    con = sqlite3.connect(str(db))
    try:
        con.execute("DELETE FROM audit")
        con.execute("DELETE FROM cache")
        con.commit()
    finally:
        con.close()
    R.REGISTRY["c"] = {"id": "c", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    adapter = ScriptAdapter([outcome, outcome])
    R.adapter_factory = lambda: adapter
    return TestClient(APP.create_app()), db, adapter


def test_second_identical_ask_is_cached(tmp_path):
    client, db, adapter = _client(tmp_path, GOOD)
    q = "How does user registration (`register_user`) work?"
    r1 = client.post("/api/repos/c/ask", json={"question": q})
    r2 = client.post("/api/repos/c/ask", json={"question": q})
    assert r1.json()["status"] == "answer" and r2.json()["cached"] is True
    assert adapter.calls == 1
    assert r1.json()["segments"] == r2.json()["segments"]


def test_sha_change_is_cache_miss(tmp_path):
    client, db, adapter = _client(tmp_path, GOOD)
    key_here = CA.make_key("c", SHA, "q?", CFG.LLM_PROVIDER, CFG.LLM_MODEL,
                           "p9v1", 10)
    assert CA.lookup(db, "nope") is None
    other = CA.make_key("c", "0" * 40, "q?", CFG.LLM_PROVIDER, CFG.LLM_MODEL,
                        "p9v1", 10)
    assert other != key_here
    assert CA.lookup(db, other) is None


def test_abstention_never_cached(tmp_path):
    client, db, adapter = _client(tmp_path, ABS)
    q = "How does billing work in this app?"
    client.post("/api/repos/c/ask", json={"question": q})
    client.post("/api/repos/c/ask", json={"question": q})
    assert adapter.calls == 2
    con = sqlite3.connect(str(db))
    try:
        (n,) = con.execute("SELECT COUNT(*) FROM cache").fetchone()
    finally:
        con.close()
    assert n == 0

"""Phase 10 gate: hash-by-default audit — one row per ask, no text, matching
evidence (spec Phase 10, D10.2)."""
import json
import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from mentor.answer import cache as CA
from mentor.api import app as APP
from mentor.api import routes as R

SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        return self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]


def _client(tmp_path, answer):
    R.REGISTRY.clear()
    db = tmp_path / "a.sqlite"
    shutil.copy(Path("data/indexes/fst.sqlite"), db)
    con = sqlite3.connect(str(db))
    try:
        # Runtime rows (e.g. from live smoke runs) must not leak into tests.
        con.execute("DELETE FROM audit")
        con.execute("DELETE FROM cache")
        con.commit()
    finally:
        con.close()
    R.REGISTRY["a"] = {"id": "a", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    R.adapter_factory = lambda: ScriptAdapter([answer])
    return TestClient(APP.create_app()), db


def test_ask_writes_exactly_one_hash_only_row(tmp_path):
    import hashlib
    client, db = _client(tmp_path, '{"status": "abstain", "segments": [],'
                                   ' "missing": ["no billing code"]}')
    q = "How does billing work in this app?"
    r = client.post("/api/repos/a/ask", json={"question": q})
    assert r.status_code == 200
    assert r.json()["status"] == "abstain"
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute("SELECT q_hash, q_text, a_text, evidence_json,"
                           " provider, status, verdict, prompt_version FROM audit"
                           ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1
    q_hash, q_text, a_text, ev_json, provider, status, verdict, pv = rows[0]
    assert q_hash == CA.question_hash(q) == hashlib.sha256(
        "how does billing work in this app?".encode()).hexdigest()
    assert q_text is None and a_text is None  # hashes only by default
    assert provider == "llamacpp" and status == "abstain"
    assert verdict in ("abstained-pre", "abstained-post")
    assert pv == "p9v1"
    logged_ids = [e["id"] for e in json.loads(ev_json)]
    served_ids = [c["id"] for c in r.json()["closest"]]
    assert logged_ids == served_ids and logged_ids


def test_audit_evidence_matches_response(tmp_path):
    good = json.dumps({"status": "answer",
                       "segments": [{"text": "x", "kind": "inference",
                                     "evidence_ids": []}],
                       "missing": []})
    # inference-only answer fails V6 -> abstains; evidence refs = closest.
    client, db = _client(tmp_path, good)
    r = client.post("/api/repos/a/ask", json={"question": "billing?"})
    assert r.json()["status"] == "abstain"
    con = sqlite3.connect(str(db))
    try:
        (ev_json,) = con.execute(
            "SELECT evidence_json FROM audit").fetchone()
    finally:
        con.close()
    assert isinstance(json.loads(ev_json), list)

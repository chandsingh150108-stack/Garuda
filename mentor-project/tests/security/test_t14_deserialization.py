"""T14: unsafe deserialization. Boundary: model weights + cache files.
Controls: GGUF weights via the server (never unpickled in-process); no
`pickle` loads of untrusted inputs anywhere in `mentor/`; answer/demo
caches stored as JSON. Test: static ban + JSON round-trip proof.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "mentor"


def test_no_pickle_loads_of_untrusted_input():
    hits = []
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import pickle" in text or "pickle.loads" in text \
                or "pickle.load(" in text:
            hits.append(str(path))
        if "yaml.load(" in text and "safe_load" not in text:
            hits.append(f"{path}: unsafe yaml.load")
    assert hits == [], f"deserialization surface: {hits}"


def test_cache_payloads_are_plain_json(tmp_path):
    from mentor.answer import cache as CA
    good = {"status": "answer",
            "segments": [{"text": "t", "kind": "fact",
                          "evidence_ids": ["E1"]}],
            "missing": []}
    db = tmp_path / "c.sqlite"
    import sqlite3
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE cache (key TEXT PRIMARY KEY, repo_id TEXT,"
                " sha TEXT, created_ts TEXT, response_json TEXT)")
    con.commit()
    con.close()
    assert CA.store(db, "k", "r", "s", good) is True
    assert CA.lookup(db, "k")["status"] == "answer"
    assert CA.store(db, "k2", "r", "s", {"status": "abstain", "segments": [],
                                         "missing": ["x"]}) is False

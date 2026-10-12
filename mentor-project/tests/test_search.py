"""Phase 5 gate: fused search on the fst index (spec Phase 5).

Five identifier queries assert the definition chunk ranks top-3; determinism,
injection safety, k-honoring, and confidence signals round out the gate.
Needs `data/indexes/fst.sqlite` (skips with the build command otherwise).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mentor.index import store as S
from mentor.retrieve import search as SR

ROOT = Path(__file__).resolve().parent.parent
PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
FST_DB = ROOT / "data" / "indexes" / "fst.sqlite"

# (query, definition file, definition line that must sit inside a top-3 hit)
IDENTIFIER_QUERIES = [
    ("How does `register_user` work?",
     "backend/app/api/routes/users.py", 147),
    ("Where is `create_user` defined in crud?",
     "backend/app/crud.py", 10),
    ("Where is `verify_password` defined?",
     "backend/app/core/security.py", 29),
    ("What fields does the `User` model have?",
     "backend/app/models.py", 51),
    ("What does `get_password_hash` do?",
     "backend/app/core/security.py", 35),
]


def _fst_db() -> Path:
    if not FST_DB.is_file():
        pytest.skip("run: python -m mentor.cli index --repo data/repos/fst "
                    f"--sha {PINNED_SHA} --out data/indexes/fst.sqlite")
    return FST_DB


@pytest.mark.parametrize("query,path,line", IDENTIFIER_QUERIES)
def test_identifier_definition_in_top3(query: str, path: str, line: int):
    db = _fst_db()
    res = SR.search(db, PINNED_SHA, query, k=10)
    top3 = res["hits"][:3]
    assert any(h["path"] == path and h["start_line"] <= line <= h["end_line"]
               for h in top3), [ (h["path"], h["start_line"], h["end_line"]) for h in top3 ]


def test_determinism_identical_ordering():
    db = _fst_db()
    first = SR.search(db, PINNED_SHA, "How does `register_user` work?", k=10)
    second = SR.search(db, PINNED_SHA, "How does `register_user` work?", k=10)
    assert [h["chunk_id"] for h in first["hits"]] == [h["chunk_id"] for h in second["hits"]]
    assert [h["score"] for h in first["hits"]] == [h["score"] for h in second["hits"]]


def test_injection_query_safe_and_readonly():
    db = _fst_db()
    before = S.table_counts(db)
    res = SR.search(db, PINNED_SHA, "' OR 1=1 --", k=10)
    assert isinstance(res["hits"], list)
    assert isinstance(res["confidence"], dict)
    assert S.table_counts(db) == before


def test_k_honored_and_hit_shape():
    db = _fst_db()
    res = SR.search(db, PINNED_SHA, "signup", k=5)
    assert len(res["hits"]) <= 5
    for hit in res["hits"]:
        assert set(hit) >= {"chunk_id", "path", "start_line", "end_line",
                            "score", "retrievers", "header"}
        assert hit["retrievers"] and set(hit["retrievers"]) <= {"lexical", "symbol", "path"}


def test_confidence_signals_wellformed():
    db = _fst_db()
    res = SR.search(db, PINNED_SHA, "How does `register_user` work?", k=10)
    conf = res["confidence"]
    assert conf["top_score"] >= 0.0
    assert 0.0 <= conf["identifier_coverage"] <= 1.0
    assert isinstance(conf["two_retriever_agreement"], bool)
    assert conf["identifier_coverage"] > 0.0

"""Latency + G3-precision probe for Phase 5 (spec tasks 9-10).

Times fused search over 20 queries (p50/p95) and measures file-level
precision@10 of lexical-only vs fused rankings on 5 identifier queries with
hand-verified relevant files. Prints JSON to stdout; numbers are recorded in
EVALUATION_RESULTS.md (Phase 6 gold set will supersede the probe).
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentor.retrieve import analyze as A
from mentor.retrieve import lexical as L
from mentor.retrieve import search as SR

SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
DB = Path("data/indexes/fst.sqlite")

QUERIES = [
    "How does `register_user` work?",
    "Where is `create_user` defined in crud?",
    "Where is `verify_password` defined?",
    "What fields does the `User` model have?",
    "What does `get_password_hash` do?",
    "What happens at `/users/signup`?",
    "How does login work?",
    "Where are items created?",
    "What is `API_V1_STR`?",
    "How is the database initialized?",
    "What tables exist in the database?",
    "Where is password hashing configured?",
    "How do tests create random users?",
    "What frontend routes exist?",
    "How is email sent for new accounts?",
    "What does `SessionDep` mean?",
    "Where is CORS configured?",
    "What is `SECRET_KEY` used for?",
    "How are items listed for a user?",
    "How do billing refunds work for the enterprise plan?",
]

# query -> relevant files (hand-verified definition/use locations)
RELEVANT = {
    QUERIES[0]: {"backend/app/api/routes/users.py"},
    QUERIES[1]: {"backend/app/crud.py"},
    QUERIES[2]: {"backend/app/core/security.py"},
    QUERIES[3]: {"backend/app/models.py"},
    QUERIES[4]: {"backend/app/core/security.py"},
}


def file_precision(retrieved_files: list[str], relevant: set[str], k: int = 10) -> float:
    top = retrieved_files[:k]
    return sum(1 for f in top if f in relevant) / k


def main() -> int:
    lat: dict[str, float] = {}
    for query in QUERIES:
        t0 = time.perf_counter()
        SR.search(DB, SHA, query, k=10)
        lat[query] = (time.perf_counter() - t0) * 1000.0
    values = sorted(lat.values())
    import math
    p50 = statistics.median(values)
    p95 = values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        prec = {}
        for query, relevant in RELEVANT.items():
            analysis = A.analyze(query)
            lex_ids = [h["chunk_id"] for h in L.search_lexical(con, analysis, 10)]
            fused = SR.search(DB, SHA, query, k=10)["hits"]

            def files_of(ids):
                paths = []
                for cid in ids:
                    row = con.execute("SELECT path FROM chunks WHERE chunk_id = ?",
                                      (cid,)).fetchone()
                    if row:
                        paths.append(row[0])
                return paths

            prec[query] = {
                "relevant": sorted(relevant),
                "lexical_p10": round(file_precision(files_of(lex_ids), relevant), 3),
                "fused_p10": round(file_precision(
                    [h["path"] for h in fused], relevant), 3),
            }
    finally:
        con.close()
    print(json.dumps({"n": len(QUERIES),
                      "latency_ms": {q: round(v, 2) for q, v in lat.items()},
                      "p50_ms": round(p50, 2), "p95_ms": round(p95, 2),
                      "precision_probe": prec}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

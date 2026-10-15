"""Hash-by-default audit writer (spec Phase 10, D10.2).

One row per served ask: timestamp, repo, SHA, SHA-256 of the question,
evidence IDs + paths + ranges, provider, status, validator verdict, prompt
version. Question/answer TEXT is never stored unless `audit_store_text=true`
(default false) — a leaked log then reveals hashes, not content.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
from pathlib import Path

from mentor import config as CFG
from mentor.answer import cache as CA
from mentor.index import store as ST


def write(db: Path, *, repo_id: str, sha: str, question: str,
          response: dict, provider: str, model: str, verdict: str,
          cached: bool = False,
          store_text: bool = CFG.AUDIT_STORE_TEXT) -> int:
    """Append one audit row. Returns the row id."""
    from mentor.answer import prompts as P
    evidence = [{"id": e["id"], "path": e["path"], "lines": e["lines"]}
                for e in response.get("evidence", [])]
    if response.get("status") == "abstain":
        evidence = [{"id": c["id"], "path": c["path"], "lines": c["lines"]}
                    for c in response.get("closest", [])]
    con = sqlite3.connect(str(db))
    try:
        ST.ensure_service_tables(con)
        with con:
            cur = con.execute(
                "INSERT INTO audit(ts, repo_id, sha, q_hash, evidence_json,"
                " provider, model, status, verdict, prompt_version, cached,"
                " q_text, a_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 repo_id, sha, CA.question_hash(question),
                 json.dumps(evidence, sort_keys=True),
                 provider, model, response.get("status", "?"), verdict,
                 P.PROMPT_VERSION, int(cached),
                 question if store_text else None,
                 json.dumps(response, sort_keys=True) if store_text else None))
            return cur.lastrowid
    finally:
        con.close()

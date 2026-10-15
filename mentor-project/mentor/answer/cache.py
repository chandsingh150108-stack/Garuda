"""Validated-answer cache (spec Phase 10, D10.3).

Key = sha256(repo_id, sha, INDEX_SCHEMA_VERSION, normalized-question hash,
provider, model, prompt version, k). The SHA + repo_id + schema version bind
the entry to one repository at one commit on one index layout, so a key can
never return an answer from another repository or commit. Abstentions are
NEVER cached (re-evaluated after index changes); only status=answer outputs
with at least one cited fact are stored.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from mentor import config as CFG
from mentor.index import store as ST

_WS = re.compile(r"\s+")


def normalize(question: str) -> str:
    """Canonical question form for hashing (case + whitespace folded)."""
    return _WS.sub(" ", question.strip().lower())


def question_hash(question: str) -> str:
    return hashlib.sha256(normalize(question).encode("utf-8")).hexdigest()


def make_key(repo_id: str, sha: str, question: str, provider: str, model: str,
             prompt_version: str, k: int) -> str:
    parts = [repo_id, sha, str(CFG.INDEX_SCHEMA_VERSION),
             question_hash(question), provider, model, prompt_version, str(k)]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _connect(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db))
    ST.ensure_service_tables(con)
    return con


def lookup(db: Path, key: str) -> dict | None:
    con = _connect(db)
    try:
        row = con.execute("SELECT response_json FROM cache WHERE key = ?",
                          (key,)).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return json.loads(row[0])


def store(db: Path, key: str, repo_id: str, sha: str, response: dict) -> bool:
    """Store a validated answer. Returns False (no store) for abstentions or
    answers without a cited fact — these are re-evaluated every time."""
    if response.get("status") != "answer":
        return False
    if not any(s.get("kind") == "fact" and s.get("evidence_ids")
               for s in response.get("segments", [])):
        return False
    import datetime
    con = _connect(db)
    try:
        with con:
            con.execute(
                "INSERT OR REPLACE INTO cache(key, repo_id, sha, created_ts,"
                " response_json) VALUES (?, ?, ?, ?, ?)",
                (key, repo_id, sha,
                 datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 json.dumps(response, sort_keys=True)))
    finally:
        con.close()
    return True

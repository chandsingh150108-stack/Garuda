"""Per-provider daily budget (spec Phase 11, D11.3).

Counts requests + approximate tokens per provider per UTC day in SQLite.
Calls stop at 90% of the RECORDED limit (fail-closed: a provider with no
recorded limits is never called). Limits come from dated console/doc reads in
RESEARCH_LOG.md — never hardcoded guesses.
"""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

STOP_FRACTION = 0.90


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE IF NOT EXISTS cloud_budget ("
                " provider TEXT NOT NULL, day TEXT NOT NULL,"
                " requests INTEGER NOT NULL DEFAULT 0,"
                " tokens INTEGER NOT NULL DEFAULT 0,"
                " PRIMARY KEY (provider, day))")
    con.commit()
    return con


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def usage(db: Path, provider: str, day: str | None = None) -> dict:
    con = _connect(db)
    try:
        row = con.execute("SELECT requests, tokens FROM cloud_budget"
                          " WHERE provider = ? AND day = ?",
                          (provider, day or _today())).fetchone()
    finally:
        con.close()
    return {"requests": row[0] if row else 0, "tokens": row[1] if row else 0}


def allowed(db: Path, provider: str, limits: dict | None) -> tuple[bool, str]:
    """Fail-closed: no recorded limits -> not allowed."""
    if not limits:
        return False, "no recorded limits for provider"
    used = usage(db, provider)
    if used["requests"] >= STOP_FRACTION * limits.get("rpd", 0):
        return False, f"daily request budget reached ({used['requests']})"
    if used["tokens"] >= STOP_FRACTION * limits.get("tpd", 0):
        return False, f"daily token budget reached ({used['tokens']})"
    return True, "within budget"


def record(db: Path, provider: str, tokens: int) -> None:
    con = _connect(db)
    try:
        with con:
            con.execute("INSERT INTO cloud_budget(provider, day, requests, tokens)"
                        " VALUES (?, ?, 1, ?)"
                        " ON CONFLICT(provider, day) DO UPDATE SET"
                        " requests = requests + 1, tokens = tokens + ?",
                        (provider, _today(), tokens, tokens))
    finally:
        con.close()

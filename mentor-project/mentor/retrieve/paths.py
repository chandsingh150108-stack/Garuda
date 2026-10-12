"""Path matching against repository file paths (spec Phase 5, D5.2).

Route segments (`/users/signup` -> users, signup) and file-like tokens match
chunk paths by case-insensitive substring. Ranked by number of matched
segments (desc), ties by chunk_id. LIKE metacharacters are escaped;
everything is parameterized.
"""
from __future__ import annotations

import re
import sqlite3

from mentor.retrieve import analyze as A


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def path_tokens(analysis: A.QueryAnalysis) -> list[str]:
    tokens: list[str] = []
    for route in analysis.routes:
        tokens.extend(t.lower() for t in re.findall(r"[a-z0-9]+", route.lower()))
    tokens.extend(f.lower() for f in analysis.files)
    seen: set[str] = set()
    return [t for t in tokens if t and not (t in seen or seen.add(t))]


def search_paths(con: sqlite3.Connection, sha: str, analysis: A.QueryAnalysis,
                 k: int) -> list[dict]:
    """Return [{chunk_id, rank}] ordered by segment hits then chunk_id."""
    tokens = path_tokens(analysis)
    if not tokens:
        return []
    conds = " OR ".join("LOWER(path) LIKE '%' || ? || '%' ESCAPE '\\'"
                        for _ in tokens)
    rows = con.execute(
        f"SELECT DISTINCT path FROM chunks WHERE snapshot_sha = ? AND ({conds})",
        (sha, *[_escape_like(t) for t in tokens])).fetchall()
    scored = []
    for (path,) in rows:
        lowered = path.lower()
        hits = sum(1 for t in tokens if t in lowered)
        scored.append((-hits, path))
    scored.sort()
    out: list[str] = []
    for _, path in scored:
        for (cid,) in con.execute(
                "SELECT chunk_id FROM chunks WHERE snapshot_sha = ? AND path = ?"
                " ORDER BY start_line", (sha, path)).fetchall():
            out.append(cid)
            if len(out) >= k:
                return [{"chunk_id": c, "rank": i + 1} for i, c in enumerate(out)]
    return [{"chunk_id": c, "rank": i + 1} for i, c in enumerate(out)]

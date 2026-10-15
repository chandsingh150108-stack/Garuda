"""Evidence assembly: retrieved hits -> numbered blocks (spec Phase 9, D9.1).

Blocks E1..En are assigned by the server in retrieval rank order. Text is read
from the index (`chunks.text`, exact source lines), NEVER from the working
tree: the index is the cited artifact. Budget default ~3000 approx tokens
(chars//4, per D4.1). Callers render blocks for the model; the model sees IDs
and line-numbered text only — never raw paths it could echo (see V8).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

EVIDENCE_BUDGET_TOKENS = 3000


def approx_tokens(text: str) -> int:
    """Deterministic token approximation (chars//4, per D4.1)."""
    return len(text) // 4


def build(db: Path, sha: str, hits: list[dict],
          budget_tokens: int = EVIDENCE_BUDGET_TOKENS) -> dict:
    """Assemble evidence blocks from ranked hits.

    Returns {blocks, used_tokens, truncated}. Each block carries the chunk's
    exact index text plus its path/range for server-side citation rendering.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        blocks: list[dict] = []
        used = 0
        truncated = False
        for rank, hit in enumerate(hits, start=1):
            row = con.execute(
                "SELECT path, start_line, end_line, header, text FROM chunks"
                " WHERE chunk_id = ? AND snapshot_sha = ?",
                (hit["chunk_id"], sha)).fetchone()
            if row is None:
                continue
            path, start, end, header, text = row
            cost = approx_tokens(text)
            if blocks and used + cost > budget_tokens:
                truncated = True
                break
            blocks.append({"id": f"E{rank}", "chunk_id": hit["chunk_id"],
                           "path": path, "start_line": start, "end_line": end,
                           "header": header, "text": text,
                           "approx_tokens": cost,
                           "score": hit.get("score", 0.0)})
            used += cost
        return {"blocks": blocks, "used_tokens": used, "truncated": truncated}
    finally:
        con.close()


def render(block: dict) -> str:
    """Line-numbered rendering for the model prompt (untrusted data)."""
    lines = block["text"].splitlines() or [""]
    numbered = "\n".join(
        f"{block['start_line'] + i:>6} | {line}" for i, line in enumerate(lines))
    return (f"[{block['id']}] {block['path']}:{block['start_line']}-"
            f"{block['end_line']}\n{numbered}")

"""Optional LLM title step with evidence-traceable validation (spec Phase 12).

The model may propose a plainer node title, but the validator accepts it ONLY
if the title contains a word or identifier present in the node's cited
evidence (D12.3). Otherwise the deterministic label stands. No title without
evidence (failure condition).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

_WORD = re.compile(r"[a-z0-9]+")


def evidence_texts(db: Path, sha: str, node: dict) -> str:
    """Concatenated cited text for a node (from the index, not files)."""
    ids = [e["chunk_id"] for e in node.get("evidence", [])]
    if not ids:
        return ""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            f"SELECT text FROM chunks WHERE chunk_id IN "
            f"({','.join('?' for _ in ids)})", tuple(ids)).fetchall()
    finally:
        con.close()
    return "\n".join(r[0] for r in rows)


def accept_title(proposed: str, evidence: str) -> bool:
    """True iff a significant word of the proposal occurs in the evidence."""
    hay = evidence.lower()
    words = {w for w in _WORD.findall(proposed.lower()) if len(w) >= 4}
    return any(w in hay for w in words)


def apply_titles(model: dict, titles: dict[str, str], db: Path,
                 sha: str) -> tuple[dict, dict]:
    """Apply proposed titles where evidence-traceable. Returns (model, report)
    with per-node accepted/proposed/kept. Model shape unchanged otherwise."""
    report: dict[str, dict] = {}
    by_id = {n["id"]: n for n in model["nodes"]}
    for nid, proposed in titles.items():
        node = by_id.get(nid)
        if node is None or not proposed:
            continue
        ok = accept_title(proposed, evidence_texts(db, sha, node))
        report[nid] = {"proposed": proposed, "accepted": ok,
                       "kept": proposed if ok else node["label"]}
        if ok:
            node["label"] = proposed
    return model, report


def propose_titles(model: dict, db: Path, sha: str, adapter,
                   timeout_s: float = 120.0) -> dict[str, str]:
    """Ask the model for one short title per node (JSON {id: title}).
    Deterministic fallback: empty dict (labels stand)."""
    from mentor.llm import gateway as GW
    nodes = [{"id": n["id"], "label": n["label"], "kind": n["kind"],
              "paths": n["paths"][:3]} for n in model["nodes"]]
    messages = [{"role": "system", "content": (
        "Propose one short plain title per architecture node. Respond with a "
        "single JSON object mapping node id to title, e.g. "
        '{"N1": "App startup"}. Use words from the file and symbol names '
        "given. No other text.")},
        {"role": "user", "content": json.dumps(nodes)}]
    try:
        parsed = GW.generate(adapter, messages, {"type": "object"},
                             {"max_tokens": 256}, timeout_s=timeout_s)
    except GW.GatewayError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v)[:80] for k, v in parsed.items()
            if isinstance(v, str) and v.strip()}

"""Single-command demo (spec Phase 21, D21.1).

Verifies index + demo cache, prints the fixed 15-step sequence with the
expected response kind per step, opens the browser, then serves on loopback
(blocking). Any verification failure exits non-zero BEFORE the browser
opens — a broken demo never starts.
"""
from __future__ import annotations

import json
import sqlite3
import webbrowser
from pathlib import Path

STEPS = [
    ("Start locally with `mentor demo`",
     "server on loopback, mode banner, index verified at pinned SHA"),
    ("Open the primary repository", "name, pinned SHA, status current"),
    ("Show the architecture", ">=6 components; node click opens its code"),
    ("Ask 'How does signup work?'", "answer with citation chips + provider"),
    ("Show the guided signup tour", "validated steps + sequence diagram + hop labels"),
    ("Click three citations", "code view at exact lines with pinned SHA"),
    ("Ask a why question", "PROVEN/HISTORY segments or separate INFERRED"),
    ("Show history provenance", "blame/commit SHA + author + date"),
    ("Ask an impossible question", "abstain + missing list + closest; no fake cite"),
    ("Show starter tasks", ">=5 tasks sorted, files+lines + read-first tours"),
    ("Scripted live edit", "affected citation shows the stale badge"),
    ("Re-index with `mentor reindex`", "only changed files re-parsed; dependents stale"),
    ("Show the refreshed answer", "new citation at new lines"),
    ("Offline method", "same question, same contract, provider LOCAL"),
    ("Show the audit log", "hashes + evidence IDs + ranges; no question text"),
]


def verify(index: Path, sha: str, cache_dir: Path) -> dict:
    """Return {'ok': bool, 'notes': [...]}. Never raises."""
    notes: list[str] = []
    if not index.is_file():
        return {"ok": False, "notes": [f"index missing: {index}"]}
    try:
        con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        try:
            has = con.execute("SELECT 1 FROM snapshots WHERE sha = ?",
                              (sha,)).fetchone()
            counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("files", "chunks", "symbols")}
        finally:
            con.close()
    except Exception as exc:
        return {"ok": False, "notes": [f"index unreadable: {exc}"]}
    if not has:
        notes.append(f"index lacks snapshot {sha[:12]}")
    for table, minimum in (("files", 100), ("chunks", 500),
                           ("symbols", 100)):
        if counts.get(table, 0) < minimum:
            notes.append(f"{table}={counts.get(table, 0)} below {minimum}")
    manifest = cache_dir / "precompute_manifest.json"
    if not manifest.is_file():
        notes.append(f"demo cache missing: {manifest} (run `mentor precompute`)")
    else:
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            if doc.get("sha") != sha:
                notes.append("demo cache SHA mismatch")
            if len(doc.get("questions", [])) < 5:
                notes.append("demo cache has <5 cached answers")
        except (OSError, ValueError) as exc:
            notes.append(f"demo cache unreadable: {exc}")
    return {"ok": not notes, "notes": notes}


def run(index: Path, repo: Path, sha: str, repo_id: str, cache_dir: Path,
        host: str, port: int, no_browser: bool = False) -> int:
    print(f"mentor demo: verifying {repo_id}@{sha[:12]} …")
    check = verify(index, sha, cache_dir)
    for note in check["notes"]:
        print(f"  BLOCKED: {note}")
    if not check["ok"]:
        return 2
    print(f"  index ok + demo cache ok ({host}:{port})")
    for i, (title, expected) in enumerate(STEPS, start=1):
        print(f"  step {i:2d}/15: {title}\n             -> {expected}")
    url = f"http://{host}:{port}/ask"
    if not no_browser:
        print(f"opening {url}")
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"  browser launch failed (non-fatal): {exc}")
    import uvicorn
    from mentor.api import app as APP
    from mentor.api import routes as R
    APP.resolve_bind(host, False)
    R.REGISTRY[repo_id] = {"id": repo_id, "path": str(repo.resolve()),
                           "sha": sha, "index": str(index)}
    from mentor import config as CFG
    print(f"serving {repo_id}@{sha[:12]} — {CFG.mode_banner()}")
    uvicorn.run(APP.create_app(), host=host, port=port, log_level="info")
    return 0

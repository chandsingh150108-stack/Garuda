"""Pre-cloud redaction (spec Phase 11, D11.1).

Removes secret-indicator lines (same patterns as the ingest scanner) and drops
whole blocks the scanner flags. Reports counts BY CATEGORY only — values are
never logged, stored, or returned. A block that loses lines is marked
`redacted: True` with its original id preserved so citations still resolve.
"""
from __future__ import annotations

import json
from pathlib import Path

from mentor.ingest import secrets as S


def redact_blocks(blocks: list[dict]) -> tuple[list[dict], dict]:
    """Return (kept_blocks, report). Report holds counts + dropped ids only."""
    kept: list[dict] = []
    dropped: list[str] = []
    redacted_lines = 0
    by_category: dict[str, int] = {}
    for block in blocks:
        findings = S.scan_text(block["text"])
        if not findings:
            kept.append(block)
            continue
        bad = {f.line_number for f in findings}
        for f in findings:
            by_category[f.category] = by_category.get(f.category, 0) + 1
        lines = block["text"].splitlines()
        survivors = [ln for i, ln in enumerate(lines, start=1) if i not in bad]
        redacted_lines += len(bad)
        if not survivors:
            dropped.append(block["id"])
            continue
        kept.append({**block, "text": "\n".join(survivors), "redacted": True})
    return kept, {"blocks_dropped": dropped, "lines_redacted": redacted_lines,
                  "by_category": by_category}


def manifest_scan_clean(sha: str) -> bool:
    """The repository's latest secret scan is clean (D11.1): no manifest
    entry was excluded for secrets. Missing manifest = not clean."""
    manifest = Path(f"data/manifests/{sha}.json")
    if not manifest.is_file():
        return False
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return not any(e.get("skipped") == "secret" for e in doc.get("files", []))

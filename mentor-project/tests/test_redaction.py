"""Phase 11 gate: redaction — canary never in payload, counts without values."""
from mentor.llm import redact as RD

CANARY = "AKIAIOSFODNN7EXAMPLE"
JWT = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
       "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")


def _block(eid, text):
    return {"id": eid, "chunk_id": "c", "path": "p.py", "start_line": 1,
            "end_line": 3, "header": "h", "text": text, "approx_tokens": 10}


def test_canary_line_removed_counts_no_values():
    blocks = [_block("E1", f"key = {CANARY}\nuser = 'alice'\nmode = 'x'")]
    kept, report = RD.redact_blocks(blocks)
    assert len(kept) == 1 and kept[0].get("redacted") is True
    payload = "\n".join(b["text"] for b in kept)
    assert CANARY not in payload
    assert "alice" in payload  # innocent lines survive
    assert report["by_category"] == {"aws_access_key": 1}
    assert report["lines_redacted"] == 1
    assert CANARY not in str(report)  # counts only, never values


def test_fully_tainted_block_dropped():
    blocks = [_block("E2", f"token = {JWT}")]
    kept, report = RD.redact_blocks(blocks)
    assert kept == []
    assert report["blocks_dropped"] == ["E2"]
    assert report["by_category"] == {"jwt": 1}


def test_clean_blocks_untouched():
    blocks = [_block("E3", "def register_user():\n    pass")]
    kept, report = RD.redact_blocks(blocks)
    assert kept == blocks and "redacted" not in kept[0]
    assert report == {"blocks_dropped": [], "lines_redacted": 0,
                      "by_category": {}}


def test_manifest_scan_clean_for_pinned_sha():
    assert RD.manifest_scan_clean(
        "7257e606cb94eada1dca40173e2b7f99dd549bc6") is True
    assert RD.manifest_scan_clean("0" * 40) is False

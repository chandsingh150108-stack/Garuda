"""Phase 9 gate: validator rejects 100% of the invalid suite (spec Phase 9)."""
import json
from pathlib import Path

from mentor.answer import validator as V

FIXTURE = Path(__file__).parent / "fixtures" / "invalid_outputs.json"


def _expand(entry):
    """Expand LONG/MANY placeholders into real violations."""
    out = json.loads(json.dumps(entry["output"]))
    if isinstance(out, dict) and isinstance(out.get("segments"), list):
        for seg in out["segments"]:
            if seg.get("text") == "LONG":
                seg["text"] = "x" * 601
    if isinstance(out, dict) and out.get("segments") == "MANY":
        out["segments"] = [{"text": f"claim {i}", "kind": "fact",
                             "evidence_ids": ["E1"]} for i in range(13)]
    return out


def test_invalid_suite_rejected_with_expected_codes():
    suite = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(suite) >= 10
    for entry in suite:
        if entry["name"].startswith("_"):
            continue
        errors = V.validate(_expand(entry), entry["blocks"])
        codes = {e.code for e in errors}
        assert errors, f"{entry['name']}: accepted, expected {entry['expected']}"
        for want in entry["expected"]:
            assert want in codes, (f"{entry['name']}: missing {want}, "
                                   f"got {sorted(codes)}")


def test_valid_answer_passes():
    blocks = [{"id": "E1", "path": "a.py", "start_line": 1, "end_line": 2,
               "header": "a.py", "text": "def register_user():\n    pass"}]
    out = {"status": "answer",
           "segments": [{"text": "registration is handled by `register_user`",
                         "kind": "fact", "evidence_ids": ["E1"]}],
           "missing": []}
    assert V.validate(out, blocks) == []


def test_valid_abstention_passes():
    blocks = [{"id": "E1", "path": "a.py", "start_line": 1, "end_line": 1,
               "header": "a.py", "text": "x = 1"}]
    out = {"status": "abstain", "segments": [],
           "missing": ["no billing code in evidence"]}
    assert V.validate(out, blocks) == []

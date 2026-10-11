"""Phase 1 gate: DECISIONS.md has 18 entries with required fields; GATED names procedure."""
import re
from pathlib import Path


DEC = Path(__file__).resolve().parent.parent / "DECISIONS.md"
REQUIRED = ["status", "evidence", "reason", "confidence", "fallback"]


def sections():
    text = DEC.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    return [p for p in parts if p.strip()]


def test_all_18_present():
    text = DEC.read_text(encoding="utf-8")
    for i in range(1, 19):
        assert re.search(rf"^## A{i}\b", text, flags=re.M), f"missing A{i}"


def test_a_entries_have_fields():
    secs = sections()
    a_secs = [s for s in secs if re.match(r"A\d+\b", s.strip())]
    assert len(a_secs) == 18, f"expected 18 A-sections, got {len(a_secs)}"
    for s in a_secs:
        low = s.lower()
        for f in REQUIRED:
            assert f in low, f"section {s.splitlines()[0]!r} missing field {f}"


def test_gated_name_procedure():
    text = DEC.read_text(encoding="utf-8")
    for g in ["G1", "G2", "G3", "G4"]:
        idx = text.find(g)
        assert idx != -1, f"missing {g}"
        window = text[idx:idx + 2000].lower()
        assert "benchmark procedure" in window, f"{g} names no benchmark procedure"
        assert "evaluation_results.md" in window or "decisions.md" in window, f"{g} names no results file"

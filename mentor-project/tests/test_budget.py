"""Phase 11 gate: daily budget — 90% stop, fail-closed, day isolation."""
from mentor.llm import budget as BU


def test_fail_closed_without_limits(tmp_path):
    db = tmp_path / "b.sqlite"
    ok, why = BU.allowed(db, "gemini", {})
    assert not ok and "no recorded limits" in why
    ok, _ = BU.allowed(db, "gemini", None)
    assert not ok


def test_stops_at_ninety_percent(tmp_path):
    db = tmp_path / "b.sqlite"
    limits = {"rpd": 100, "tpd": 10000}
    for _ in range(89):
        BU.record(db, "groq", 10)
    ok, _ = BU.allowed(db, "groq", limits)
    assert ok  # 89 < 90
    BU.record(db, "groq", 10)
    ok, why = BU.allowed(db, "groq", limits)
    assert not ok and "request budget" in why


def test_token_leg_binds_first(tmp_path):
    db = tmp_path / "b.sqlite"
    limits = {"rpd": 100000, "tpd": 1000}
    BU.record(db, "groq", 899)
    ok, _ = BU.allowed(db, "groq", limits)
    assert ok
    BU.record(db, "groq", 1)
    ok, why = BU.allowed(db, "groq", limits)
    assert not ok and "token budget" in why


def test_usage_counts_accumulate(tmp_path):
    db = tmp_path / "b.sqlite"
    BU.record(db, "groq", 40)
    BU.record(db, "groq", 60)
    assert BU.usage(db, "groq") == {"requests": 2, "tokens": 100}

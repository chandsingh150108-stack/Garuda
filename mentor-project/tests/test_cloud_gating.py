"""Phase 11 gate: cloud gating — default-off zero-egress, private blocked,
dirty-scan blocked (spec Phase 11, D11.1)."""
from pathlib import Path

from mentor import config as CFG
from mentor.answer import qa as QA
from mentor.llm import gateway as GW
from tests.socket_guard import SocketGuard

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"

CANARY = "AKIAIOSFODNN7EXAMPLE"


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        return self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]


def _local_answer():
    return ('{"status": "abstain", "segments": [],'
            ' "missing": ["gate test"]}')


def test_default_off_zero_provider_egress(monkeypatch):
    from mentor.llm import budget as BU
    assert CFG.ALLOW_FREE_CLOUD is False
    # Fake credentials: the gate blocks before any network, and SocketGuard
    # would fail the test on any egress attempt regardless.
    monkeypatch.setattr(CFG, "CLOUD_GROQ_MODEL", "live-list-model")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(BU, "_today", lambda: "2099-01-01")
    with SocketGuard(enforce=True) as guard:
        out = QA.ask(DB, SHA, "How does user registration work?", k=5,
                     adapter=ScriptAdapter([_local_answer()]), cloud=True,
                     allowlisted_public=True, tau_score=0.0, tau_cov=0.0)
    assert out["provider"] == CFG.LLM_PROVIDER
    assert out["fallback"] is True
    assert "allow_free_cloud" in out["cloud_status"]
    assert guard.non_loopback == []


def test_private_repo_blocked_no_egress(monkeypatch):
    monkeypatch.setattr(CFG, "ALLOW_FREE_CLOUD", True)
    monkeypatch.setattr(CFG, "CLOUD_GROQ_MODEL", "live-list-model")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-never-sent")
    with SocketGuard(enforce=True) as guard:
        out = QA.ask(DB, SHA, "How does user registration work?", k=5,
                     adapter=ScriptAdapter([_local_answer()]), cloud=True,
                     allowlisted_public=False, tau_score=0.0, tau_cov=0.0)
    assert out["fallback"] is True
    assert "allowlist" in out["cloud_status"]
    assert guard.non_loopback == []


def test_gate_order_names_first_failure():
    ok, why = GW.check_cloud_allowed(
        allow_free_cloud=False, allowlisted_public=False, scan_clean=False,
        redacted=False, within_cap=False, budget_ok=False,
        budget_reason="empty", provider="groq")
    assert not ok and "allow_free_cloud" in why
    ok, _ = GW.check_cloud_allowed(
        allow_free_cloud=True, allowlisted_public=True, scan_clean=True,
        redacted=True, within_cap=True, budget_ok=True, budget_reason="",
        provider="groq")
    assert ok
    ok, why = GW.check_cloud_allowed(
        allow_free_cloud=True, allowlisted_public=False, scan_clean=True,
        redacted=True, within_cap=True, budget_ok=True, budget_reason="",
        provider="gemini")
    assert not ok and "public" in why
    ok, why = GW.check_cloud_allowed(
        allow_free_cloud=True, allowlisted_public=True, scan_clean=False,
        redacted=True, within_cap=True, budget_ok=True, budget_reason="",
        provider="groq")
    assert not ok and "secret scan" in why


def test_egress_cloud_policy_pins_hosts():
    from mentor.llm import egress as EG
    assert EG.check_cloud_url("https://api.groq.com/x", "groq") == "api.groq.com"
    for bad in ("https://api.groq.com.evil.com/x", "https://example.com/",
                "https://generativelanguage.googleapis.com/x"):
        try:
            EG.check_cloud_url(bad, "groq")
        except EG.EgressBlocked:
            continue
        raise AssertionError(f"cloud egress allowed to {bad}")
    # Gemini host accepted only for gemini.
    assert EG.check_cloud_url("https://generativelanguage.googleapis.com/x",
                              "gemini")


def test_live_list_parsers_no_hardcoded_names():
    from mentor.llm import gemini_adapter as GE
    from mentor.llm import groq_adapter as GQ
    groq_body = {"data": [{"id": "openai/gpt-oss-20b"},
                          {"id": "qwen/qwen3.8-27b"}, {}]}
    assert GQ.parse_models(groq_body) == ["openai/gpt-oss-20b",
                                          "qwen/qwen3.8-27b"]
    gem_body = {"models": [{"name": "models/gemini-3.8-flash"}, {}]}
    assert GE.parse_models(gem_body) == ["gemini-3.8-flash"]
    # Adapters refuse empty (unconfigured) models: names come from the list.
    import pytest
    with pytest.raises(ValueError):
        GQ.GroqAdapter("", "k")
    with pytest.raises(ValueError):
        GE.GeminiAdapter("", "k")

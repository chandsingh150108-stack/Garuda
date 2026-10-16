"""Phase 19 gate: no-keys operation — with no provider keys in the
environment, cloud stays unconfigured and local serving never requires keys.
"""
import os

from mentor import config as CFG
from mentor.answer import qa as QA
from mentor.llm import gateway as GW
from tests.test_freshness import build_fixture


class ScriptAdapter:
    def complete(self, messages, schema, options, timeout_s):
        return ('{"status": "answer", "segments": [{"text": "handled by '
                '`alpha`", "kind": "fact", "evidence_ids": ["E1"]}], '
                '"missing": []}')


def _clean_env(monkeypatch):
    for var in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_no_keys_in_environment(monkeypatch):
    _clean_env(monkeypatch)
    assert os.environ.get("GROQ_API_KEY", "") == ""
    assert os.environ.get("GEMINI_API_KEY", "") == ""


def test_cloud_gate_closed_without_keys_or_flag():
    allowed, reason = GW.check_cloud_allowed(
        allow_free_cloud=False, allowlisted_public=False, scan_clean=True,
        redacted=True, within_cap=True, budget_ok=True,
        budget_reason="within budget", provider="groq")
    assert allowed is False and "CLOUD_BLOCKED" in reason


def test_cloud_request_without_keys_serves_local(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    fx = build_fixture(tmp_path)
    out = QA.ask(fx["index"], fx["sha"], "How does alpha work?",
                 adapter=ScriptAdapter(), cloud=True,
                 allowlisted_public=False)
    assert out["provider"] == CFG.LLM_PROVIDER  # local, never cloud
    assert "unconfigured" in out["cloud_status"]
    assert out["fallback"] is True
    assert out["status"] == "answer"

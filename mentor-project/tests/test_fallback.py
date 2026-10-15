"""Phase 11 gate: fallback — 429/timeout/blocked fall back to local in the same
contract; schema failures propagate; no-keys run stays local (spec Phase 11).
"""
import os

from mentor.answer import qa as QA
from mentor.llm import gateway as GW

from pathlib import Path

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _answer(text="ok"):
    return ('{"status": "answer", "segments": '
            f'[{{"text": "{text}", "kind": "inference", "evidence_ids": []}}], '
            '"missing": []}')


def test_rate_limited_cloud_falls_back_same_contract():
    cloud = ScriptAdapter([GW.GatewayError(GW.GatewayError.RATE_LIMITED, "429")])
    local = ScriptAdapter([_answer()])
    parsed, serving, fallback = GW.generate_auto(
        cloud, local, [{"role": "user", "content": "q"}], {"type": "object"},
        {}, provider="groq")
    assert serving == "local" and fallback is True
    assert parsed["status"] == "answer"  # contract unchanged
    # 429 is NOT retried (retrying a rate limit is wrong); one attempt, then
    # fallback. Transport retries apply to timeouts/resets only (Phase 8).
    assert cloud.calls == 1 and local.calls == 1


def test_schema_failure_propagates_not_masked():
    cloud = ScriptAdapter(["not json"])
    local = ScriptAdapter([_answer()])
    try:
        GW.generate_auto(cloud, local, [], {"type": "object"}, {})
    except GW.GatewayError as exc:
        assert exc.kind == GW.GatewayError.SCHEMA
    else:
        raise AssertionError("schema failure must propagate")
    assert local.calls == 0


def test_no_keys_stays_local_with_labels():
    from mentor import config as CFG
    assert os.environ.get("GROQ_API_KEY", "") == ""
    assert os.environ.get("GEMINI_API_KEY", "") == ""
    out = QA.ask(DB, SHA, "How does user registration work?", k=5,
                 adapter=ScriptAdapter([_answer()]), cloud=True,
                 allowlisted_public=True, tau_score=0.0, tau_cov=0.0)
    assert out["provider"] == CFG.LLM_PROVIDER
    assert out["fallback"] is True
    assert "unconfigured" in out["cloud_status"]


def test_429_end_to_end_marks_fallback():
    from mentor.llm import groq_adapter as GQ
    err429 = GW.GatewayError(GW.GatewayError.RATE_LIMITED, "429")
    cloud = ScriptAdapter([err429, err429])
    _ = GQ  # adapter shape documented; transport simulated by script adapter
    local = ScriptAdapter([_answer()])
    parsed, serving, fallback = GW.generate_auto(
        cloud, local, [], {"type": "object"}, {}, retries=1,
        provider="groq")
    assert (serving, fallback) == ("local", True)
    assert set(parsed) >= {"status", "segments", "missing"}

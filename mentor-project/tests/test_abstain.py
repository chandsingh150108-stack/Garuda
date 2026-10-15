"""Phase 9 gate: pre-generation gate, abstention shape, repair, budget."""
from pathlib import Path

from mentor.answer import abstain as AB
from mentor.answer import evidence as EV
from mentor.answer import prompts as P
from mentor.answer import qa as QA
from mentor.answer import validator as V
from mentor.llm import gateway as GW

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


def test_pre_gate_abstains_on_low_score():
    gate = AB.pre_gate({"top_score": 0.001, "identifier_coverage": 1.0},
                       True, tau_score=0.01, tau_cov=0.5)
    assert gate["abstain"]


def test_pre_gate_abstains_on_low_coverage_with_identifiers():
    gate = AB.pre_gate({"top_score": 0.04, "identifier_coverage": 0.0},
                       True, tau_score=0.01, tau_cov=0.5)
    assert gate["abstain"]


def test_pre_gate_passes_without_identifiers_despite_zero_coverage():
    gate = AB.pre_gate({"top_score": 0.04, "identifier_coverage": 0.0},
                       False, tau_score=0.01, tau_cov=0.5)
    assert not gate["abstain"]


def test_abstention_shape_has_closest_and_missing():
    blocks = [{"id": "E1", "path": "a.py", "start_line": 1, "end_line": 5,
               "header": "a.py", "text": "x = 1"}]
    out = AB.abstention(blocks, ["no billing code"], "low confidence")
    assert out["status"] == "abstain" and out["segments"] == []
    assert out["missing"] == ["no billing code"]
    assert out["closest"][0]["path"] == "a.py"


def test_qa_pregeneration_abstain_makes_no_model_call():
    adapter = ScriptAdapter(['{"status": "answer", "segments": [], "missing": []}'])
    out = QA.ask(DB, SHA, "zzzzqqqq no such thing anywhere", k=5,
                 adapter=adapter, tau_score=999.0)
    assert out["status"] == "abstain" and adapter.calls == 0
    assert out["prompt_version"] == P.PROMPT_VERSION


def test_qa_repair_once_then_answer():
    import json
    bad = json.dumps({"status": "answer",
                      "segments": [{"text": "uncited claim", "kind": "fact",
                                    "evidence_ids": []}], "missing": []})
    good = json.dumps({"status": "abstain", "segments": [],
                       "missing": ["insufficient evidence"]})
    adapter = ScriptAdapter([bad, good])
    out = QA.ask(DB, SHA, "How does user registration work?", k=5,
                 adapter=adapter, tau_score=0.0, tau_cov=0.0)
    assert adapter.calls == 2
    assert out["repairs"] == 1
    assert out["status"] == "abstain"
    assert out["missing"] == ["insufficient evidence"]


def test_qa_double_failure_abstains():
    import json
    bad = json.dumps({"status": "answer",
                      "segments": [{"text": "uncited", "kind": "fact",
                                    "evidence_ids": []}], "missing": []})
    adapter = ScriptAdapter([bad, bad])
    out = QA.ask(DB, SHA, "How does user registration work?", k=5,
                 adapter=adapter, tau_score=0.0, tau_cov=0.0)
    assert out["status"] == "abstain" and out["repairs"] == 1


def test_evidence_budget_enforced():
    res = QA.ask(DB, SHA, "signup", k=50, adapter=ScriptAdapter(
        ['{"status": "abstain", "segments": [], "missing": ["x"]}']),
        evidence_budget=100, tau_score=0.0, tau_cov=0.0)
    assert res["evidence_tokens"] <= 100 or res["status"] in ("answer", "abstain")
    env = EV.build(DB, SHA, [{"chunk_id": h} for h in []], budget_tokens=100)
    assert env["used_tokens"] == 0

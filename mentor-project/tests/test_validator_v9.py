"""Phase 14 gate: V9 causal-claim rule (spec Phase 14, D14.2)."""
from mentor.answer import validator as V

CODE = [{"id": "E1", "path": "a.py", "start_line": 1, "end_line": 5,
         "header": "a.py", "text": "def authenticate():\n    pass"}]
HIST = [{"id": "H1", "kind": "history", "path": "a.py", "lines": "1-5",
         "text": "commit 689d7105 by Seb on 2026-01-22 records: constant time (#2105)"}]


def test_causal_fact_without_history_rejected():
    out = {"status": "answer",
           "segments": [{"text": "it retries because the network is flaky",
                         "kind": "fact", "evidence_ids": ["E1"]}],
           "missing": []}
    codes = {e.code for e in V.validate(out, CODE)}
    assert "V9_CAUSAL_WITHOUT_HISTORY" in codes


def test_causal_fact_with_history_citation_passes():
    out = {"status": "answer",
           "segments": [{"text": "it sleeps to avoid enumeration attacks",
                         "kind": "fact", "evidence_ids": ["E1", "H1"],
                         "provenance": "history"}],
           "missing": []}
    assert V.validate(out, CODE + HIST) == []


def test_causal_inference_kind_passes_labelled():
    out = {"status": "answer",
           "segments": [
               {"text": "`authenticate` exists", "kind": "fact",
                "evidence_ids": ["E1"], "provenance": "proven"},
               {"text": "probably added to prevent timing attacks",
                "kind": "inference", "evidence_ids": ["E1"],
                "provenance": "inferred"}],
           "missing": []}
    # "to prevent" inside an inference segment is a labelled guess, not a
    # fact claim: V9 does not fire.
    assert V.validate(out, CODE) == []


def test_non_causal_facts_unaffected():
    out = {"status": "answer",
           "segments": [{"text": "registration is handled by `authenticate`",
                         "kind": "fact", "evidence_ids": ["E1"]}],
           "missing": []}
    assert V.validate(out, CODE) == []


def test_provenance_label_accepted_by_schema():
    out = {"status": "abstain", "segments": [],
           "missing": ["no recorded rationale found"]}
    assert V.validate(out, CODE) == []

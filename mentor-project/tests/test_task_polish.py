"""Tasks refresh Phase 3: LLM polish is best-effort prose, never load-bearing.

Deterministic titles always ship; polish overlays validated text only, and
the serve path applies it solely on id + evidence-hash match. No model is
needed here: script adapters stand in for the gateway.
"""
import json
from pathlib import Path

from mentor.features import task_polish as TP
from mentor.features import tasks as TS

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


class _Good:
    model = "stub-good"

    def complete(self, messages, schema, options, timeout_s):
        return json.dumps({
            "title": "Tidy up the starter task",
            "description": "Work through the flagged spot using the cited "
                           "code as the guide.",
            "evidence_ids": ["E1"]})


class _Garbage:
    model = "stub-garbage"

    def complete(self, messages, schema, options, timeout_s):
        return "not json at all"


class _BadIds:
    model = "stub-badids"

    def complete(self, messages, schema, options, timeout_s):
        return json.dumps({
            "title": "Tidy up the starter task",
            "description": "Work through the flagged spot.",
            "evidence_ids": ["E99"]})


def _first_task():
    tasks = TS.rank(TS.collect(DB, SHA), 3)
    assert tasks and tasks[0]["evidence"]
    return tasks[0]


def test_polish_opt_in_defaults_off():
    from mentor import config as CFG
    assert CFG.ALLOW_TASK_POLISH is False


def test_no_adapter_keeps_deterministic():
    task = _first_task()
    assert TP.polish_task(DB, SHA, dict(task), None) == task


def test_valid_stub_polishes_with_validator_pass():
    task = _first_task()
    out = TP.polish_task(DB, SHA, task, _Good())
    assert out["polished"]["title"] == "Tidy up the starter task"
    assert out["polished"]["prompt_version"] == TP.PROMPT_VERSION
    assert out["title"] == task["title"]  # base record untouched
    assert out["evidence"] == task["evidence"]


def test_garbage_output_falls_back_to_deterministic():
    task = _first_task()
    assert TP.polish_task(DB, SHA, dict(task), _Garbage()) == task


def test_bad_ids_fail_validation_and_fall_back():
    task = _first_task()
    assert TP.polish_task(DB, SHA, dict(task), _BadIds()) == task


def test_overlay_applies_only_on_hash_match():
    live = _first_task()
    polished = TP.polish_task(DB, SHA, live, _Good())
    assert "polished" in polished
    applied = TP.overlay_polish([dict(live)], [polished], DB, SHA)
    assert applied[0]["title"] == "Tidy up the starter task"
    assert applied[0]["polished"] is True
    tampered = json.loads(json.dumps(polished))
    tampered["polished"]["evidence_hashes"] = ["deadbeef"]
    kept = TP.overlay_polish([dict(live)], [tampered], DB, SHA)
    assert kept[0]["title"] == live["title"]
    assert kept[0]["polished"] is False

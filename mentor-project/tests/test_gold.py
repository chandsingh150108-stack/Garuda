"""Phase 6 gate: gold validation, composition, counterfactual (spec Phase 6).

Validates v1 against the pinned repo, enforces the 8/6/6/4/6 composition,
and checks the counterfactual set (renamed symbols present at mapped lines).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from mentor.eval import counterfactual as CF
from mentor.eval import gold as G

ROOT = Path(__file__).resolve().parent.parent
PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
V1 = ROOT / "evals" / "gold" / "v1.yaml"
V1_CF = ROOT / "evals" / "gold" / "v1_counterfactual.yaml"
MAP = ROOT / "evals" / "counterfactual_map.json"
REPO = ROOT / "data" / "repos" / "fst"
CF_REPO = ROOT / "data" / "repos" / "fst-cf"


def test_gold_validates_against_pinned_repo():
    gold = G.load(V1)
    assert G.validate(gold, REPO) == []


def test_gold_composition_exact():
    gold = G.load(V1)
    counts: dict[str, int] = {}
    for item in gold.items:
        counts[item.category] = counts.get(item.category, 0) + 1
    assert counts == {"where_how": 8, "arch": 6, "flow": 6, "why": 4,
                      "unanswerable": 6}
    assert len(gold.items) == 30


def test_unanswerable_items_carry_absence_evidence():
    gold = G.load(V1)
    bare = [i for i in gold.items if i.expected_status == "abstain"]
    assert len(bare) == 8  # 2 why-without-history + 6 unanswerable
    for item in bare:
        assert item.gold == []
        assert item.reviewer_notes.strip(), item.id


def test_answerable_items_have_gold_and_rubric():
    gold = G.load(V1)
    answered = [i for i in gold.items if i.expected_status == "answer"]
    assert len(answered) == 22
    for item in answered:
        assert item.gold, item.id
        assert item.must_include, item.id


def test_counterfactual_valid_and_renamed():
    assert V1_CF.is_file()
    problems = CF.check(V1, V1_CF, MAP, REPO, CF_REPO)
    assert problems == []
    cf = G.load(V1_CF)
    assert len(cf.items) == 30
    # Renamed identifiers actually changed in questions/facts (no leak of
    # old names where the map applies).
    import json
    rename_map = json.loads(MAP.read_text(encoding="utf-8"))
    text = V1_CF.read_text(encoding="utf-8")
    for old in ("create_user_cf", "signup-cf"):
        assert old in text, old


def test_gold_frozen_hash_recorded():
    digest = hashlib.sha256(V1.read_bytes()).hexdigest()
    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    assert digest in decisions, "v1.yaml SHA-256 must be recorded in DECISIONS.md"

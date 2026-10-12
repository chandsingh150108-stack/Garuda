"""Phase 5 gate: RRF fusion exactness (spec Phase 5, D5.2)."""
from fractions import Fraction

import pytest

from mentor.retrieve import fusion as FU


def test_hand_computed_three_list_order():
    rankings = [["a", "b", "c"], ["b", "a"], ["c"]]
    fused = FU.fuse(rankings, k=60)
    assert [doc for doc, _ in fused] == ["a", "b", "c"]
    assert fused[0][1] == pytest.approx(float(Fraction(1, 61) + Fraction(1, 62)))
    assert fused[2][1] == pytest.approx(float(Fraction(1, 63) + Fraction(1, 61)))


def test_ties_broken_by_doc_id():
    fused = FU.fuse([["b", "a"], ["a", "b"]], k=60)
    assert [doc for doc, _ in fused] == ["a", "b"]
    assert fused[0][1] == fused[1][1]


def test_single_ranking_preserves_order_with_rrf_scores():
    fused = FU.fuse([["x", "y"]], k=60)
    assert fused == [("x", 1 / 61), ("y", 1 / 62)]


def test_empty_rankings():
    assert FU.fuse([]) == []
    assert FU.fuse([[], []]) == []


def test_default_constant_is_60():
    assert FU.RRF_K == 60
    fused = FU.fuse([["only"]])
    assert fused == [("only", 1 / 61)]

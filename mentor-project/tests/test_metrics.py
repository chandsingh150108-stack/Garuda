"""Phase 6 gate: metric units + Wilson reference (spec Phase 6, D6.2-D6.3)."""
from mentor.eval import metrics as M
from mentor.eval import stats as ST

GOLD = [{"path": "a.py", "start_line": 10, "end_line": 20},
        {"path": "a.py", "start_line": 30, "end_line": 40}]


def _hits():
    return [
        {"path": "b.py", "start_line": 1, "end_line": 5},
        {"path": "a.py", "start_line": 15, "end_line": 25},
        {"path": "a.py", "start_line": 35, "end_line": 45},
    ]


def test_overlap_same_file_only():
    assert M.overlaps("a.py", 15, 25, "a.py", 10, 20)
    assert M.overlaps("a.py", 5, 10, "a.py", 10, 20)  # boundary touches
    assert not M.overlaps("a.py", 1, 9, "a.py", 10, 20)
    assert not M.overlaps("b.py", 15, 25, "a.py", 10, 20)


def test_recall_counts_covered_ranges():
    assert M.recall_at_k(_hits(), GOLD, 1) == 0.0
    assert M.recall_at_k(_hits(), GOLD, 2) == 0.5
    assert M.recall_at_k(_hits(), GOLD, 3) == 1.0
    assert M.recall_at_k(_hits(), [], 3) == 1.0


def test_mrr_first_relevant():
    assert M.mrr(_hits(), GOLD) == 0.5
    assert M.mrr(_hits()[:1], GOLD) == 0.0
    assert M.mrr([], GOLD) == 0.0


def test_symbol_hit_rate():
    assert M.symbol_hit_rate(_hits(), GOLD) == 1.0
    assert M.symbol_hit_rate(_hits()[:1], GOLD) == 0.0


def test_file_precision():
    assert M.file_precision_at_k(["a.py", "b.py", "c.py"], {"a.py", "c.py"}, 3) == 2 / 3
    assert M.file_precision_at_k([], {"a.py"}) == 0.0


def test_wilson_reference():
    # Reference: 4/22icol Wilson 95% interval ≈ [0.078, 0.398] (standard tables).
    lo, hi = ST.wilson(4 / 22, 22)
    assert abs(lo - 0.073) < 0.01
    assert abs(hi - 0.385) < 0.02
    assert ST.wilson(0.5, 0) == (0.0, 1.0)
    lo1, hi1 = ST.wilson(1.0, 22)
    assert lo1 > 0.8 and hi1 == 1.0

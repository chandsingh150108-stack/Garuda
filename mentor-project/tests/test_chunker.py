"""Phase 4 gate: chunker split/merge/assemble (spec Phase 4, D4.1-D4.3).

Pure split/merge/assemble tests run without subprocesses. `plan_file` tests
use the isolated worker on tiny fixtures. Budget, header/embed separation,
determinism, and no-dropped-lines are asserted throughout.
"""
from __future__ import annotations

from pathlib import Path

from mentor.index import chunker as K
from mentor.index import hashing as H

ROOT = Path(__file__).resolve().parent.parent


def _lines(n: int, width: int = 20) -> list[str]:
    return [f"ln{i:04d} " + "x" * (width - 8) for i in range(1, n + 1)]


def test_approx_tokens_is_chars_over_four():
    assert K.approx_tokens("a" * 400) == 100
    assert K.approx_tokens("") == 0


def test_split_small_units_merge():
    lines = _lines(10)
    units = [{"start": 1, "end": 5, "kind": "x", "children": []},
             {"start": 6, "end": 10, "kind": "x", "children": []}]
    spans = K.split_units(units, lines, budget=512)
    assert spans == [(1, 10, False, "ast")] or sum(
        e - s + 1 for s, e, _, _ in spans) == 10
    merged = K.merge_spans(spans, lines, budget=512)
    assert merged == [(1, 10, False, "ast")]


def test_split_oversized_at_child_boundaries():
    lines = _lines(40, width=100)  # 40x100 chars = 1000 tokens
    units = [{"start": 1, "end": 40, "kind": "fn", "children": [
        {"start": 1, "end": 20, "kind": "block", "children": []},
        {"start": 21, "end": 40, "kind": "block", "children": []}]}]
    spans = K.split_units(units, lines, budget=512)
    assert [(s, e) for s, e, _, _ in spans] == [(1, 20), (21, 40)]
    assert all(not x for _, _, x, _ in spans)


def test_single_line_over_budget_is_exception():
    lines = ["short", "y" * 3000, "short"]
    spans = K.split_units([{"start": 1, "end": 3, "kind": "x", "children": []}],
                          lines, budget=512)
    by_span = {(s, e): x for s, e, x, _ in spans}
    assert by_span[(2, 2)] is True
    assert by_span[(1, 1)] is False and by_span[(3, 3)] is False


def test_many_same_line_children_emit_one_span():
    # Regression: 130 export specifiers sharing line 4 (real fst index.ts
    # shape) must not emit 130 identical spans (chunk_id UNIQUE violation).
    big = ("export { " + ", ".join(f"VeryLongExportedName{i:03d}" for i in range(130))
           + " } from 'm';")  # ~3000 chars ≈ 750 tokens > budget on one line
    lines = ["// header", "", big, ""]
    kids = [{"start": 3, "end": 3, "kind": "export_specifier", "children": []}
            for _ in range(130)]
    units = [{"start": 1, "end": 1, "kind": "comment", "children": []},
             {"start": 3, "end": 3, "kind": "export_statement", "children": kids}]
    spans = K.split_units(units, lines, budget=512)
    assert [(s, e) for s, e, _, _ in spans].count((3, 3)) == 1
    by_span = {(s, e): x for s, e, x, _ in spans}
    assert by_span[(3, 3)] is True  # single over-budget line => exception


def test_gaps_never_dropped():
    # Children cover [2..3] and [6..7]; every other line must still land
    # in some span (blank or code).
    lines = ["", "a = 1", "b = 2", "", "", "c = 3", "d = 4", ""]
    units = [{"start": 2, "end": 3, "kind": "x", "children": []},
             {"start": 6, "end": 7, "kind": "x", "children": []}]
    spans = K.split_units(units, lines, budget=512)
    covered = set()
    for s, e, _, _ in spans:
        covered.update(range(s, e + 1))
    assert covered == set(range(1, 9))


def test_line_windows_overlap_and_cover():
    lines = _lines(200)
    spans = K.chunk_line_windows(lines, window=80, overlap=20)
    assert spans[0][:2] == (1, 80)
    assert spans[1][:2] == (61, 140)
    covered = set()
    for s, e, _, _ in spans:
        covered.update(range(s, e + 1))
    assert covered == set(range(1, 201))
    assert all(m == "lines" and not x for _, _, x, m in spans)


def test_line_windows_respect_budget_on_long_lines():
    lines = _lines(200, width=100)  # 200 x 100 chars = 5000 tokens
    spans = K.chunk_line_windows(lines, window=80, overlap=20, budget=512)
    covered = set()
    for s, e, x, m in spans:
        assert K.approx_tokens(K.slice_text(lines, s, e)) <= 512 or x
        covered.update(range(s, e + 1))
    assert covered == set(range(1, 201))


def test_assemble_exact_text_and_separation():
    lines = ["def f():", "    return 1", "", "x = 2"]
    symbols = [{"qualname": "f", "start_line": 1, "end_line": 2}]
    chunks = K.assemble("sha", "a.py", [(1, 4, False, "ast")], symbols, lines)
    assert len(chunks) == 1
    c = chunks[0]
    assert c["text"] == "def f():\n    return 1\n\nx = 2"
    assert c["header"] == "a.py | f"
    assert c["embed_text"] == "a.py | f\ndef f():\n    return 1\n\nx = 2"
    assert "def f():" not in c["header"] and c["text"].startswith("def f():")
    assert c["approx_tokens"] == len(c["text"]) // 4
    assert c["content_hash"] == H.sha256_text(c["text"])
    assert c["chunk_id"] == H.chunk_id("sha", "a.py", 1, 4, c["content_hash"])
    assert c["is_exception"] is False


def test_assemble_deterministic_ids():
    lines = _lines(5)
    kw = dict(repo_sha="s", path="p.py",
              spans=[(1, 5, False, "ast")], symbols=[], lines=lines)
    assert K.assemble(**kw)[0]["chunk_id"] == K.assemble(**kw)[0]["chunk_id"]


def test_plan_file_tiny_python(tmp_path: Path):
    src = tmp_path / "m.py"
    src.write_text("def f():\n    return 1\n", encoding="utf-8")
    plan = K.plan_file(tmp_path, "m.py", "python", timeout_s=30.0)
    assert plan["status"] == "ok"
    assert plan["units"][0]["start"] == 1
    assert plan["units"][0]["end"] == 2


def test_chunk_file_uses_lines_fallback_for_text(tmp_path: Path):
    doc = tmp_path / "notes.md"
    doc.write_text("# t\n\nhello\n", encoding="utf-8")
    res = K.chunk_file(tmp_path, "notes.md", [])
    assert res["status"] == "ok"
    assert res["spans"] == [(1, 3, False, "lines")]

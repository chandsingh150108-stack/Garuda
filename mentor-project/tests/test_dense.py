"""Phase 7 gate: dense retrieval units (spec Phase 7, D7.1-D7.3).

Brute-force search, metadata guards, and query-prefix handling are tested
with a fake encoder (no model downloads). Live-model behavior is measured by
scripts/bench_embedders.py, not here.
"""
import numpy as np
import pytest

from mentor.retrieve import dense as D


class FakeModel:
    def __init__(self):
        self.seen = []

    def encode(self, texts, batch_size=32, show_progress_bar=False,
               normalize_embeddings=True, convert_to_numpy=True):
        self.seen.extend(texts)
        vectors = []
        for i, _ in enumerate(texts):
            vec = np.zeros(4, dtype=np.float32)
            vec[i % 4] = 1.0
            vectors.append(vec)
        return np.stack(vectors)


def test_embed_texts_normalized_float32():
    model = FakeModel()
    out = D.embed_texts(model, ["a", "b", "c"])
    assert out.dtype == np.float32
    assert out.shape == (3, 4)
    assert model.seen == ["a", "b", "c"]


def test_embed_query_applies_prefix(monkeypatch):
    monkeypatch.setitem(D.MODEL_SPECS, "prefixed",
                        {"query_prefix": "query:", "dim": 4})
    try:
        model = FakeModel()
        D.embed_query(model, "prefixed", "hello")
        assert model.seen == ["query: hello"]
        model2 = FakeModel()
        D.embed_query(model2, "bge-m3", "hello")
        assert model2.seen == ["hello"]
    finally:
        del D.MODEL_SPECS["prefixed"]


def test_cosine_topk_matches_reference():
    rng = np.random.default_rng(7)
    matrix = rng.normal(size=(50, 8)).astype(np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    query = rng.normal(size=(8,)).astype(np.float32)
    query /= np.linalg.norm(query)
    got = D.cosine_topk(matrix, query, 5)
    ref_scores = matrix @ query
    ref = sorted(range(50), key=lambda i: -ref_scores[i])[:5]
    assert [i for i, _ in got] == ref
    assert all(got[i][1] >= got[i + 1][1] for i in range(4))


def test_search_dense_rank_order():
    matrix = np.array([[1, 0], [0, 1], [0.7, 0.7]], dtype=np.float32)
    out = D.search_dense(matrix, ["a", "b", "c"], np.array([1, 0], np.float32), 3)
    assert [h["chunk_id"] for h in out] == ["a", "c", "b"]
    assert [h["rank"] for h in out] == [1, 2, 3]


def test_metadata_guards_model_change():
    matrix = np.zeros((10, 1024), dtype=np.float32)
    ids = [f"c{i}" for i in range(10)]
    D.check_metadata("bge-m3", 1024, matrix, ids)  # ok
    with pytest.raises(ValueError, match="dim mismatch"):
        D.check_metadata("bge-m3", 768, matrix, ids)
    with pytest.raises(ValueError, match="shape mismatch"):
        D.check_metadata("bge-m3", 1024, matrix, ids[:5])


def test_model_specs_have_permissive_licences():
    for name, spec in D.MODEL_SPECS.items():
        assert spec["licence"] in ("MIT", "Apache-2.0"), name
        assert spec["dim"] > 0 and spec["query_prefix"] is None

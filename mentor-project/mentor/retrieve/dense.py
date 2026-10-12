"""Dense retrieval: code-embedding candidates on CPU (spec Phase 7, G1).

Candidates are benchmarked, not trusted: adoption needs a measured gain with
a permissive licence (D7.1/D7.2). Chunk text embedded is `embed_text`
(header + text); citations always use `text`. Brute-force cosine over
NumPy float32 (exact; 1279 chunks x 1024d ~= 5 MB — no index server needed).
"""
from __future__ import annotations

import numpy as np

MODEL_SPECS = {
    # Verified on source cards 2026-10-12 (see RESEARCH_LOG Phase 7).
    "bge-m3": {"hf": "BAAI/bge-m3", "dim": 1024, "licence": "MIT",
               "params": "568M", "query_prefix": None, "trust_remote_code": False},
    "jina-v2-code": {"hf": "jinaai/jina-embeddings-v2-base-code", "dim": 768,
                     "licence": "Apache-2.0", "params": "161M",
                     "query_prefix": None, "trust_remote_code": True},
}


def load_model(name: str, device: str = "cpu"):
    """Load a candidate on CPU via sentence-transformers.

    Low-memory options (16 GB laptop RAM shared with the OS/browser):
    transformers' low_cpu_mem_usage avoids a duplicate fp32 copy at load.
    """
    import os
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from sentence_transformers import SentenceTransformer
    spec = MODEL_SPECS[name]
    model = SentenceTransformer(
        spec["hf"], device=device,
        trust_remote_code=spec["trust_remote_code"],
        model_kwargs={"low_cpu_mem_usage": True, "torch_dtype": "float32"})
    # Our chunks are <=512 approx-tokens (~2000 chars); capping the encoder
    # well below its 8192 native limit cuts padding waste on CPU without
    # truncating any chunk content that matters.
    model.max_seq_length = min(model.max_seq_length, 1024)
    return model


def embed_texts(model, texts: list[str], batch_size: int = 32) -> np.ndarray:
    """L2-normalized float32 embeddings (cosine == dot product)."""
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False,
                           normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype=np.float32)


def embed_query(model, name: str, query: str) -> np.ndarray:
    prefix = MODEL_SPECS[name]["query_prefix"]
    text = f"{prefix} {query}" if prefix else query
    return embed_texts(model, [text])[0]


def cosine_topk(matrix: np.ndarray, query: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Exact brute-force cosine top-k. Returns [(row, score)] best-first."""
    scores = matrix @ query.astype(np.float32)
    order = np.argsort(-scores, kind="stable")[:k]
    return [(int(i), float(scores[i])) for i in order]


def search_dense(matrix: np.ndarray, chunk_ids: list[str], query_vec: np.ndarray,
                 k: int) -> list[dict]:
    """Rank chunk IDs by cosine similarity. Returns [{chunk_id, rank}]."""
    top = cosine_topk(matrix, query_vec, k)
    return [{"chunk_id": chunk_ids[i], "rank": position}
            for position, (i, _) in enumerate(top, start=1)]


def check_metadata(model_name: str, dim: int, matrix: np.ndarray,
                   chunk_ids: list[str]) -> None:
    """Loading guard: model name + dimension must match stored vectors or the
    index must be rebuilt from scratch (spec D7.3)."""
    expected = MODEL_SPECS[model_name]["dim"]
    if dim != expected:
        raise ValueError(f"dim mismatch: stored {dim} != {model_name} {expected}")
    if matrix.shape != (len(chunk_ids), expected):
        raise ValueError(f"shape mismatch: {matrix.shape} vs ({len(chunk_ids)}, {expected})")

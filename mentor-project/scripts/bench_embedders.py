"""G1 embedding benchmark (spec Phase 7).

For each candidate (none = B3 lexical-only floor): embed all chunks on CPU
(timed), rank the 22 answerable gold questions with RRF over B3 rankings
(+ dense ranking for embedders), and report recall@10/MRR with n. Vectors
are cached under data/cache/ so reruns skip re-embedding. Prints JSON.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from mentor.eval import gold as G
from mentor.eval import metrics as M
from mentor.retrieve import dense as D
from mentor.retrieve import fusion as FU
from mentor.retrieve import lexical as L
from mentor.retrieve import paths as PT
from mentor.retrieve import symbols as SY

SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
DB = Path("data/indexes/fst.sqlite")
CACHE = Path("data/cache")


def load_chunks(db: Path, sha: str):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT chunk_id, embed_text FROM chunks WHERE snapshot_sha = ?"
            " ORDER BY chunk_id", (sha,)).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows], [r[1] for r in rows]


def base_rankings(db: Path, sha: str, query: str, depth: int = 50):
    from mentor.retrieve import analyze as A
    analysis = A.analyze(query)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        lex = [h["chunk_id"] for h in L.search_lexical(con, analysis, depth)]
        sym = [h["chunk_id"] for h in SY.search_symbols(con, sha, analysis, depth)]
        pth = [h["chunk_id"] for h in PT.search_paths(con, sha, analysis, depth)]
    finally:
        con.close()
    return [lex, sym, pth], analysis


def gold_ranges(item) -> list[dict]:
    return [{"path": g.path, "start_line": g.start_line, "end_line": g.end_line}
            for g in item.gold]


_CHUNK_CACHE: dict[str, tuple] = {}


def _chunk_range(cid: str):
    if cid in _CHUNK_CACHE:
        return _CHUNK_CACHE[cid]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT path, start_line, end_line FROM chunks"
                          " WHERE chunk_id = ?", (cid,)).fetchone()
    finally:
        con.close()
    _CHUNK_CACHE[cid] = row
    return row


def run_candidate(name: str, items, chunk_ids, embed_texts, args) -> dict:
    if name == "none":
        model = None
        matrix = None
        out = {"model": "none", "licence": "n/a (no vectors)", "dim": 0,
               "embed_minutes": 0.0, "index_bytes": 0}
    elif args.rank_only:
        cache_path = CACHE / f"vectors_{name}.npz"
        blob = np.load(cache_path)
        chunk_ids, matrix = list(blob["ids"]), blob["matrix"]
        model = D.load_model(name, device="cpu")
        spec = D.MODEL_SPECS[name]
        D.check_metadata(name, spec["dim"], matrix, chunk_ids)
        out = {"model": name, "licence": spec["licence"], "dim": spec["dim"],
               "embed_minutes": "see shard runs",
               "index_bytes": int(matrix.nbytes)}
    else:
        spec = D.MODEL_SPECS[name]
        total = len(chunk_ids)
        lo = (total * args.shard) // args.shards
        hi = (total * (args.shard + 1)) // args.shards
        slice_ids, slice_texts = chunk_ids[lo:hi], embed_texts[lo:hi]
        t0 = time.perf_counter()
        model = D.load_model(name, device="cpu")
        # Small batches: activation memory scales with batch x seq_len, and
        # 3.9 GB free RAM cannot hold batch-32 @1024 tokens (swap-thrash).
        parts, done = [], 0
        step = 64
        for begin in range(0, len(slice_texts), step):
            chunk = slice_texts[begin:begin + step]
            parts.append(D.embed_texts(model, chunk, batch_size=4))
            done += len(chunk)
            print(f"shard {args.shard}: {done}/{len(slice_texts)} "
                  f"({(time.perf_counter()-t0)/60:.1f} min)", flush=True)
        matrix = np.concatenate(parts).astype(np.float32)
        embed_min = (time.perf_counter() - t0) / 60.0
        if matrix.shape != (len(slice_ids), spec["dim"]):
            raise ValueError(f"unexpected matrix shape {matrix.shape}")
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(CACHE / f"vectors_{name}_part{args.shard}.npz",
                            ids=np.array(slice_ids), matrix=matrix)
        out = {"model": name, "licence": spec["licence"], "dim": spec["dim"],
               "embed_minutes": round(embed_min, 2),
               "index_bytes": "see merge",
               "shard": [args.shard, args.shards, len(slice_ids)]}
        return out  # ranking needs the merged cache; run with --rank-only
    # per-question ranking
    recalls, mrrs = [], []
    latencies = []
    for item in items:
        t0 = time.perf_counter()
        base, _ = base_rankings(DB, SHA, item.question)
        if name == "none":
            fused = FU.fuse(base)
        else:
            qvec = D.embed_query(model, name, item.question)
            dense = [h["chunk_id"] for h in
                     D.search_dense(matrix, chunk_ids, qvec, 50)]
            fused = FU.fuse(base + [dense])
        latencies.append((time.perf_counter() - t0) * 1000.0)
        top10 = [c for c, _ in fused[:10]]
        hits = []
        for cid in top10:
            row = _chunk_range(cid)
            if row:
                hits.append({"path": row[0], "start_line": row[1], "end_line": row[2]})
        gold = gold_ranges(item)
        recalls.append(M.recall_at_k(hits, gold, 10))
        mrrs.append(M.mrr(hits, gold))
    out.update({"recall@10": round(statistics.fmean(recalls), 3),
                "mrr": round(statistics.fmean(mrrs), 3), "n": len(items),
                "latency_ms_p50": round(statistics.median(latencies), 1)})
    return out


def merge_shards(name: str, shards: int, chunk_ids: list[str]) -> Path:
    """Combine per-shard caches into the full vectors file (shard order)."""
    ids_all, mats = [], []
    for i in range(shards):
        part = CACHE / f"vectors_{name}_part{i}.npz"
        if not part.is_file():
            raise SystemExit(f"missing shard cache: {part}")
        blob = np.load(part)
        ids_all.extend(list(blob["ids"]))
        mats.append(blob["matrix"])
    if ids_all != chunk_ids:
        raise SystemExit("shard id order does not match index order")
    matrix = np.concatenate(mats).astype(np.float32)
    D.check_metadata(name, D.MODEL_SPECS[name]["dim"], matrix, chunk_ids)
    out = CACHE / f"vectors_{name}.npz"
    np.savez_compressed(out, ids=np.array(chunk_ids), matrix=matrix)
    print(f"merged {shards} shards -> {out} {matrix.shape}", flush=True)
    return out


def main() -> int:
    global DB
    parser = argparse.ArgumentParser(description="G1 embedding benchmark.")
    parser.add_argument("--gold", default="evals/gold/v1.yaml")
    parser.add_argument("--index", default=str(DB))
    parser.add_argument("--candidates", default="none,bge-m3,jina-v2-code")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--rank-only", action="store_true",
                        help="skip embedding; rank from merged vectors cache")
    parser.add_argument("--merge-shards", type=int, default=0, metavar="N",
                        help="merge N part-caches into the full vectors file and exit")
    args = parser.parse_args()
    DB = Path(args.index)
    gold = G.load(Path(args.gold))
    items = G.answerable(gold)
    chunk_ids, embed_texts = load_chunks(DB, SHA)
    print(f"chunks={len(chunk_ids)} questions={len(items)}", flush=True)
    if args.merge_shards:
        for name in args.candidates.split(","):
            name = name.strip()
            if name != "none":
                merge_shards(name, args.merge_shards, chunk_ids)
        return 0
    results = [run_candidate(name.strip(), items, chunk_ids, embed_texts, args)
               for name in args.candidates.split(",")]
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

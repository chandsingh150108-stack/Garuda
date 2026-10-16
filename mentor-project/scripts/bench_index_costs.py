"""Step-0 micro-benchmarks for the index-build performance plan (perf-00).

(a) Spawn tax: N x run_isolated(parse) on one file vs in-process parse_bytes.
(b) Timeout-file diagnosis: in-process parse_bytes vs extract_py per known-slow
    file (parse dominates => grammar pathology; extract dominates => FFI churn).
(c) File mix is read from the manifest (no timing needed).

Usage: python scripts/bench_index_costs.py [--reps 5]
Prints JSON to stdout; numbers go to EVALUATION_RESULTS.md by hand.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentor.parse import parse_worker as W  # noqa: E402
from mentor.parse import treesitter as T  # noqa: E402

REPO = Path("data/repos/sklearn")
MEDIUM_FILE = "sklearn/ensemble/_forest.py"
SLOW_FILES = [
    "sklearn/compose/tests/test_column_transformer.py",
    "sklearn/metrics/_classification.py",
    "sklearn/metrics/_ranking.py",
    "sklearn/metrics/pairwise.py",
    "sklearn/metrics/tests/test_classification.py",
    "sklearn/model_selection/_validation.py",
    "sklearn/preprocessing/_data.py",
    "sklearn/preprocessing/tests/test_data.py",
    "sklearn/tree/tests/test_tree.py",
    "sklearn/utils/estimator_checks.py",
    "sklearn/utils/validation.py",
]


def time_spawn_tax(root: str, rel: str, reps: int) -> dict:
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        res = W.run_isolated(W.parse_file_nocheck, (root, rel), 120.0)
        dt = time.perf_counter() - t0
        assert res.get("ok") is not None, res
        samples.append(round(dt, 3))
    data = (Path(root) / rel).read_bytes()
    inproc = []
    for _ in range(reps):
        t0 = time.perf_counter()
        T.parse_bytes("python", data)
        inproc.append(round(time.perf_counter() - t0, 3))
    return {"spawned_run_isolated_s": samples, "inprocess_parse_bytes_s": inproc}


def time_slow_file(root: str, rel: str) -> dict:
    from mentor.parse import py_extract  # deferred: mirrors child-side import

    data = (Path(root) / rel).read_bytes()
    out: dict = {"path": rel, "bytes": len(data)}
    t0 = time.perf_counter()
    tree = T.parse_bytes("python", data)
    out["parse_bytes_s"] = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    res = py_extract.extract_py(Path(root) / rel, data, Path(root))
    out["extract_py_s"] = round(time.perf_counter() - t0, 3)
    out["symbols"] = len(res.get("symbols", []))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()
    root = str(REPO.resolve())
    report: dict = {
        "medium_file": MEDIUM_FILE,
        "spawn_tax": time_spawn_tax(root, MEDIUM_FILE, args.reps),
        "slow_files": [time_slow_file(root, rel) for rel in SLOW_FILES],
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

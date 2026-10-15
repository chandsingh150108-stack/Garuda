"""Tau calibration for the pre-generation gate (spec Phase 9, D9.4).

One live pass over all gold items at tau=0,0 records per-item confidence
signals + post-gate status. The gate only ADDS abstentions, so higher
thresholds are simulated offline without re-running the model. Dev split picks
tau; test split reports honest rates. Split by fixed seed (default 7).
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentor.answer import abstain as AB
from mentor.answer import qa as QA
from mentor.eval import gold as G
from mentor.eval import stats as ST

PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate pre-gate thresholds.")
    ap.add_argument("--gold", default="evals/gold/v1.yaml")
    ap.add_argument("--index", default="data/indexes/fst.sqlite")
    ap.add_argument("--sha", default=PINNED_SHA)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out", default="docs/calibration_p9.json")
    args = ap.parse_args()

    gold = G.load(Path(args.gold))
    ids = [i.id for i in gold.items]
    random.Random(args.seed).shuffle(ids)
    half = len(ids) // 2
    dev, test = set(ids[:half]), set(ids[half:])
    print(f"dev={sorted(dev)}\ntest={sorted(test)}", flush=True)

    from mentor.retrieve import search as S
    rows = []
    for item in gold.items:
        res = S.search(Path(args.index), args.sha, item.question, k=args.k)
        out = QA.ask(Path(args.index), args.sha, item.question, k=args.k,
                     timeout_s=args.timeout, tau_score=0.0, tau_cov=0.0)
        rows.append({"id": item.id, "expected": item.expected_status,
                     "live": out["status"], "repairs": out["repairs"],
                     "top_score": round(res["confidence"]["top_score"], 5),
                     "coverage": round(res["confidence"]["identifier_coverage"], 3),
                     "has_identifiers": bool(res["analysis"]["identifiers"])})
        print(f"{item.id}: live={out['status']} score={rows[-1]['top_score']} "
              f"cov={rows[-1]['coverage']} ident={rows[-1]['has_identifiers']}",
              flush=True)

    scores = sorted({r["top_score"] for r in rows})
    grid_s = sorted({0.0} | {s for s in scores} | {0.005, 0.01, 0.02, 0.03})
    grid_c = [0.0, 0.25, 0.5, 0.75, 1.0]

    def simulate(rows_, ts, tc):
        fa = fab = ok = 0
        for r in rows_:
            gate = AB.pre_gate({"top_score": r["top_score"],
                                "identifier_coverage": r["coverage"]},
                               r["has_identifiers"], ts, tc)
            got = "abstain" if gate["abstain"] else r["live"]
            if r["expected"] == "abstain":
                if got == "answer":
                    fa += 1
                else:
                    ok += 1
            else:
                if got == "abstain":
                    fab += 1
                else:
                    ok += 1
        return ok, fa, fab

    dev_rows = [r for r in rows if r["id"] in dev]
    test_rows = [r for r in rows if r["id"] in test]
    best = None
    for ts, tc in itertools.product(grid_s, grid_c):
        ok, fa, fab = simulate(dev_rows, ts, tc)
        # Maximize correct; tie-break: fewer false answers, then lower taus.
        key = (ok, -fa, -ts, -tc)
        if best is None or key > best[0]:
            best = (key, ts, tc, ok, fa, fab)
    _, ts, tc, ok, fa, fab = best
    n_dev = len(dev_rows)
    n_test = len(test_rows)
    ok_t, fa_t, fab_t = simulate(test_rows, ts, tc)
    n_abs = sum(1 for r in test_rows if r["expected"] == "abstain")
    n_ans = n_test - n_abs
    result = {
        "seed": args.seed, "model": "qwen3-4b-instruct-q4_k_m",
        "tau_score": ts, "tau_cov": tc,
        "dev": {"n": n_dev, "correct": ok, "false_answer": fa,
                "false_abstain": fab,
                "accuracy": round(ok / n_dev, 3)},
        "test": {"n": n_test, "correct": ok_t,
                 "false_answer": {"n": fa_t, "of": n_abs,
                                  "rate": round(fa_t / n_abs, 3) if n_abs else 0.0,
                                  "ci95": list(ST.wilson(fa_t / n_abs, n_abs))},
                 "false_abstain": {"n": fab_t, "of": n_ans,
                                   "rate": round(fab_t / n_ans, 3) if n_ans else 0.0,
                                   "ci95": list(ST.wilson(fab_t / n_ans, n_ans))}},
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

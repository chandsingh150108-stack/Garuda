"""Counterbalanced study schedule (Phase 20, D20.1).

12 tasks in sets X (T01–T06) and Y (T07–T12); 4 sequences rotate condition
order × task-set order so each condition is first for half the participants
and each set pairs with each condition equally often:

  S1: session1=(mentor, X) session2=(baseline, Y)
  S2: session1=(baseline, Y) session2=(mentor, X)
  S3: session1=(mentor, Y) session2=(baseline, X)
  S4: session1=(baseline, X) session2=(mentor, Y)

Usage: python evals/study/randomize.py --seed 7 --participants 10
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

SEQUENCES = (
    ("mentor", "X", "baseline", "Y"),
    ("baseline", "Y", "mentor", "X"),
    ("mentor", "Y", "baseline", "X"),
    ("baseline", "X", "mentor", "Y"),
)


def schedule(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    rows = []
    for pos, i in enumerate(order):
        seq = SEQUENCES[pos % 4]
        rows.append({"participant": f"P{i + 1:02d}",
                     "session1_condition": seq[0], "session1_set": seq[1],
                     "session2_condition": seq[2], "session2_set": seq[3]})
    return sorted(rows, key=lambda r: r["participant"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study schedule.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--participants", type=int, default=10)
    parser.add_argument("--out", default="evals/study/schedule.csv")
    args = parser.parse_args(argv)
    rows = schedule(args.participants, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out} (n={len(rows)}, seed={args.seed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

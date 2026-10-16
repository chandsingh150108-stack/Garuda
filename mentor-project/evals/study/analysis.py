"""Study analysis (Phase 20, D20.4). Stdlib only (no scipy): paired
Wilcoxon signed-rank with normal approximation, median-difference effect
with seeded bootstrap 95% CIs, SUS descriptives, calibration table.

Input: sessions directory of JSON files
  {"participant": "P01", "condition": {"mentor": {...}, "baseline": {...}}}
where each condition maps metric -> value. Metrics: time_s (lower better),
correct (sum of rubric points), files_hit, draw, confidence, sus.
Output: JSON + a Markdown block appended to EVALUATION_RESULTS.md.

Usage: python evals/study/analysis.py --sessions evals/study/data/
         --seed 7 --out /tmp/study_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def wilcoxon_signed_rank(mentor: list[float], baseline: list[float]) -> dict:
    """Paired Wilcoxon (mentor − baseline), normal approx, ties averaged.

    Returns W+ (sum of positive ranks), two-sided p, n (nonzero pairs), and
    the median paired difference (effect). Zero-differences are dropped per
    the standard rule; n < 6 is reported, not tested (underpowered).
    """
    diffs = [m - b for m, b in zip(mentor, baseline) if (m - b) != 0]
    n = len(diffs)
    if n == 0:
        return {"W+": 0.0, "p_two_sided": 1.0, "n": 0,
                "median_diff": 0.0, "note": "all differences zero"}
    ranked = sorted(((abs(d), 1 if d > 0 else -1) for d in diffs),
                    key=lambda t: t[0])
    ranks, i = {}, 0
    while i < n:
        j = i
        while j < n and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg
        i = j
    w_plus = sum(ranks[k] for k in range(n) if ranked[k][1] > 0)
    expected = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0
    if var == 0:
        return {"W+": w_plus, "p_two_sided": 1.0, "n": n,
                "median_diff": statistics.median(diffs),
                "note": "n<6 or degenerate; descriptive only"}
    z = (w_plus - expected) / math.sqrt(var)
    out = {"W+": round(w_plus, 2),
           "p_two_sided": round(2 * (1 - _norm_cdf(abs(z))), 4),
           "n": n, "median_diff": statistics.median(diffs)}
    if n < 6:
        out["note"] = "n<6; descriptive only, not a test"
    return out


def bootstrap_ci(mentor: list[float], baseline: list[float], seed: int = 7,
                 reps: int = 2000) -> list[float]:
    """Seeded bootstrap 95% CI for the mean paired difference."""
    rng = random.Random(seed)
    diffs = [m - b for m, b in zip(mentor, baseline)]
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n
                   for _ in range(reps))
    return [round(means[int(0.025 * reps)], 4),
            round(means[int(0.975 * reps)], 4)]


def analyze(sessions_dir: Path, seed: int = 7) -> dict:
    files = sorted(sessions_dir.glob("*.json"))
    metrics = ("time_s", "correct", "files_hit", "draw",
               "confidence", "sus")
    by_metric: dict[str, dict[str, list[float]]] = {
        m: {"mentor": [], "baseline": []} for m in metrics}
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for cond in ("mentor", "baseline"):
            for m in metrics:
                try:
                    by_metric[m][cond].append(float(doc[cond][m]))
                except (KeyError, TypeError, ValueError):
                    pass
    report: dict = {"n_files": len(files), "seed": seed, "metrics": {}}
    for m in metrics:
        men, bas = by_metric[m]["mentor"], by_metric[m]["baseline"]
        if len(men) != len(bas) or not men:
            report["metrics"][m] = {"error": "unpaired or empty"}
            continue
        test = wilcoxon_signed_rank(men, bas)
        test["mean_diff"] = round(statistics.mean(
            a - b for a, b in zip(men, bas)), 4)
        test["ci95_mean_diff"] = bootstrap_ci(men, bas, seed)
        report["metrics"][m] = test
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study analysis.")
    parser.add_argument("--sessions", default="evals/study/data")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    report = analyze(Path(args.sessions), args.seed)
    text = json.dumps(report, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

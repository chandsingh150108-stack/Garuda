"""Wilson score intervals for reported proportions (spec Phase 6, D6.3)."""
from __future__ import annotations

import math


def wilson(p_hat: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for proportion p_hat measured over n samples."""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def fmt_interval(interval: tuple[float, float]) -> str:
    return f"[{interval[0]:.2f}, {interval[1]:.2f}]"

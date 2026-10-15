"""Pre-generation abstention gate + abstention response (spec Phase 9, D9.4).

Layer 1 (here): abstain WITHOUT calling the model when retrieval confidence
is too weak — top fused score below TAU_SCORE, or identifier coverage below
TAU_COV for queries that contain identifiers. Thresholds are calibrated on the
dev split (D9.4) and locked in DECISIONS.md; changing them after the held-out
split has been used requires a recorded entry.
Layer 2 (qa.py): abstain when validation + one repair both fail.
"""
from __future__ import annotations

# Calibrated 2026-10-16 on the dev split (seed 7); locked in DECISIONS.md D9.4.
# Grid maximized dev correct decisions (tie-break: fewer false answers, then
# lower taus). Coverage gate adds nothing beyond score on dev -> 0.0 (off).
TAU_SCORE = 0.02
TAU_COV = 0.0


def pre_gate(confidence: dict, has_identifiers: bool,
             tau_score: float = TAU_SCORE,
             tau_cov: float = TAU_COV) -> dict:
    """Return {abstain, reason}. Never calls the model."""
    top = confidence.get("top_score", 0.0)
    if top < tau_score:
        return {"abstain": True,
                "reason": f"top_score {top:.4f} < tau_score {tau_score:.4f}"}
    if has_identifiers:
        cov = confidence.get("identifier_coverage", 0.0)
        if cov < tau_cov:
            return {"abstain": True,
                    "reason": f"identifier_coverage {cov:.2f} < tau_cov "
                              f"{tau_cov:.2f}"}
    return {"abstain": False, "reason": "confidence sufficient"}


def abstention(blocks: list[dict], missing: list[str], reason: str) -> dict:
    """Abstention response: closest evidence refs + missing list, no claims."""
    closest = [{"id": b["id"], "path": b["path"],
                "lines": f"{b['start_line']}-{b['end_line']}",
                "header": b["header"]} for b in blocks[:3]]
    return {"status": "abstain", "segments": [], "missing": missing,
            "closest": closest, "abstain_reason": reason}

"""Pre-generation abstention gate + abstention response (spec Phase 9, D9.4).

Layer 1 (here): abstain WITHOUT calling the model when retrieval confidence
is too weak — top fused score below TAU_SCORE, or identifier coverage below
TAU_COV for queries that contain identifiers. Thresholds are calibrated on the
dev split (D9.4) and locked in DECISIONS.md; changing them after the held-out
split has been used requires a recorded entry.
Layer 2 (qa.py): abstain when validation + one repair both fail.
"""
from __future__ import annotations

import re

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


_DUMP_VERBS = (r"(list\s+all|dump|export(\s+all)?|show\s+me\s+(all|every)|"
               r"print\s+all)")
_SECRET_NOUNS = (r"(passwords?|secrets?|api[\s_-]?keys?|tokens?|credentials?|"
                 r"private[\s_-]?keys?)")
_BULK_PATTERNS = (
    re.compile(_DUMP_VERBS + r"\s+(the\s+|all\s+|every\s+|entire\s+|whole\s+)?"
               + _SECRET_NOUNS, re.IGNORECASE),
    re.compile(_SECRET_NOUNS + r"\s+(for\s+)?" + _DUMP_VERBS, re.IGNORECASE),
    re.compile(r"^\s*" + _SECRET_NOUNS + r"\s*\??\s*$", re.IGNORECASE),
    # Whole-table dumps (user rows include emails + password hashes).
    re.compile(r"\b(dump|export)\b.{0,24}\b(entire|whole|all|full)\b"
               r".{0,24}\btable\b", re.IGNORECASE),
)


def is_bulk_dump(query: str) -> bool:
    """True for bulk-exfiltration phrasing (spec Phase 18, T3 control).

    Deliberately narrow (dump-all verbs + secret nouns, or a bare secret
    word): mechanism questions such as "How are passwords hashed?" never
    match — verified in `tests/security/test_t3_exfiltration.py`.
    """
    return any(p.search(query) for p in _BULK_PATTERNS)

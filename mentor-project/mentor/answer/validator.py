"""Deterministic answer validator, rules V1-V8 (spec Phase 9, D9.3).

The validator guarantees citations EXIST, point to blocks supplied IN THIS
REQUEST, and that backticked identifiers quoted by the model appear in the
cited text. It does NOT prove the cited code semantically entails the claim
(recorded honest limit in docs/ARCHITECTURE.md; support measured in Phase 22).

Each rule returns machine-readable error codes plus a human message suitable
for the one-retry repair prompt. Target: 100% rejection of the invalid suite.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from mentor.answer import contract as C

MAX_SEGMENT_CHARS = 600
MAX_SEGMENTS = 12

_BACKTICKED = re.compile(r"`([^`]+)`")
_URL = re.compile(r"https?://|www\.[a-z0-9]", re.IGNORECASE)
_HTML = re.compile(r"<[a-zA-Z/!][^<>]*>")
_MD_LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
_PATH_LINE = re.compile(r"[A-Za-z0-9_\-./]+\.[A-Za-z0-9]{1,8}:\d+")
# V9: causal/design claims need history. Tight on purpose: "to <verb>"
# alone is everywhere; these markers state purpose or causation.
_CAUSAL = re.compile(
    r"\b(because|in order to|so that|to avoid|to prevent|exists to|"
    r"designed to|intended to|was (created|added|introduced) to)\b",
    re.IGNORECASE)
_HISTORY_ID = re.compile(r"^H[1-9][0-9]*$")


@dataclass
class VError:
    code: str
    message: str


def _valid_ids(blocks: list[dict]) -> set[str]:
    return {b["id"] for b in blocks}


def _block_text(blocks: list[dict], eid: str) -> str | None:
    for b in blocks:
        if b["id"] == eid:
            return b["text"]
    return None


def validate(output: str | dict, blocks: list[dict]) -> list[VError]:
    """Validate a model output against V1-V8. Empty list = valid."""
    errors: list[VError] = []
    # V1: parses and conforms to schema.
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            return [VError("V1_SCHEMA_PARSE", f"output is not JSON: {exc}")]
    else:
        parsed = output
    try:
        answer = C.Answer.model_validate(parsed)
    except ValidationError as exc:
        return [VError("V1_SCHEMA",
                       f"output does not match answer schema: {exc.errors()[0]}")]
    if not isinstance(parsed, dict):
        return [VError("V1_SCHEMA", "top-level answer must be a JSON object")]

    known = _valid_ids(blocks)

    def cited_ok(eid: str) -> bool:
        return eid in known

    # V5b: segment count cap (cheap, checked first for a stable message).
    if len(answer.segments) > MAX_SEGMENTS:
        errors.append(VError(
            "V5_TOO_MANY_SEGMENTS",
            f"{len(answer.segments)} segments exceeds cap {MAX_SEGMENTS}"))

    has_cited_fact = False
    for i, seg in enumerate(answer.segments):
        tag = f"segments[{i}]"
        good_ids = [e for e in seg.evidence_ids if e in known]
        bad_ids = [e for e in seg.evidence_ids if e not in known]
        # V2: every evidence_id refers to a block in this request.
        if bad_ids:
            errors.append(VError(
                "V2_UNKNOWN_ID",
                f"{tag}: unknown evidence IDs {bad_ids} "
                f"(request blocks: {sorted(known)})"))
        # V3: every fact segment has at least one valid evidence ID.
        if seg.kind == "fact" and not good_ids:
            errors.append(VError(
                "V3_UNCITED_FACT",
                f"{tag}: kind=fact requires at least one valid evidence ID"))
        if seg.kind == "fact" and good_ids:
            has_cited_fact = True
        # V4: backticked identifiers in facts appear in cited block text.
        if seg.kind == "fact" and good_ids:
            cited_text = "\n".join(
                _block_text(blocks, e) or "" for e in good_ids)
            for ident in _BACKTICKED.findall(seg.text):
                if ident not in cited_text:
                    errors.append(VError(
                        "V4_UNSUPPORTED_IDENTIFIER",
                        f"{tag}: `{ident}` does not appear in cited evidence"))
        # V5a: segment length cap.
        if len(seg.text) > MAX_SEGMENT_CHARS:
            errors.append(VError(
                "V5_SEGMENT_TOO_LONG",
                f"{tag}: {len(seg.text)} chars exceeds cap "
                f"{MAX_SEGMENT_CHARS}"))
        # V7: no URLs, HTML, or Markdown links/images.
        if _URL.search(seg.text):
            errors.append(VError("V7_URL",
                                 f"{tag}: URLs are not permitted in answers"))
        if _HTML.search(seg.text):
            errors.append(VError("V7_HTML",
                                 f"{tag}: HTML tags are not permitted"))
        if _MD_LINK.search(seg.text):
            errors.append(VError(
                "V7_MD_LINK",
                f"{tag}: Markdown links/images are not permitted"))
        # V8: no path:line patterns; the server renders citations.
        if _PATH_LINE.search(seg.text):
            errors.append(VError(
                "V8_PATH_LINE",
                f"{tag}: file-path-with-line patterns are not permitted; "
                "cite evidence IDs only"))

    # V6: status=answer requires at least one cited fact.
    if answer.status == "answer" and not has_cited_fact:
        errors.append(VError(
            "V6_NO_CITED_FACT",
            "status=answer requires at least one fact segment with a "
            "valid citation"))
    # V9 (Phase 14, D14.2): a causal/design claim stated as fact requires a
    # HISTORY citation (H-id) or must be kind=inference (labelled guess in a
    # separate section). Enforcement is on pointers, not on the provenance
    # label. History records what was written down, not what is true.
    for i, seg in enumerate(answer.segments):
        if seg.kind == "fact" and _CAUSAL.search(seg.text):
            good_ids = [e for e in seg.evidence_ids if e in known]
            if not any(_HISTORY_ID.match(e) for e in good_ids):
                errors.append(VError(
                    "V9_CAUSAL_WITHOUT_HISTORY",
                    f"segments[{i}]: causal claim stated as fact requires a "
                    "history (H-id) citation or kind=inference"))
    return errors

"""Answer contract: Pydantic models + JSON schema (spec Phase 9, D9.2).

The model outputs evidence IDs only; the server expands ranges (Phase 10 UI).
`status` is `answer` or `abstain`. Fact segments must cite; inference and
unknown segments may cite but are labelled as non-factual either way.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Segment(BaseModel):
    text: str = Field(min_length=1)
    kind: Literal["fact", "inference", "unknown"] = "fact"
    evidence_ids: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    status: Literal["answer", "abstain"] = "answer"
    segments: list[Segment] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


ANSWER_SCHEMA: dict = Answer.model_json_schema()

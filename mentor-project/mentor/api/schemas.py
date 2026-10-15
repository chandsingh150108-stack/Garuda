"""Typed API schemas (spec Phase 10, task 1). Pydantic throughout — the same
models the answer contract uses, so wire format and validation share code."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RepoRegister(BaseModel):
    path: str = Field(min_length=1)
    sha: str = Field(min_length=7, max_length=64)
    id: str = Field(default="fst", min_length=1, max_length=64)
    allowlisted_public: bool = False  # Phase 11: public-demo opt-in, default off


class RepoInfo(BaseModel):
    id: str
    path: str
    sha: str
    indexed: bool
    allowlisted_public: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    k: int = Field(default=10, ge=1, le=50)
    cloud: bool = False  # Phase 11: request cloud acceleration (gated)


class SegmentOut(BaseModel):
    text: str
    kind: str
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    id: str
    path: str
    lines: str


class AskResponse(BaseModel):
    status: Literal["answer", "abstain"]
    segments: list[SegmentOut] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    closest: list[EvidenceRef] = Field(default_factory=list)
    repairs: int = 0
    model: str = ""
    provider: str = ""
    prompt_version: str = ""
    cached: bool = False
    fallback: bool = False  # Phase 11: cloud requested but local served
    cloud_status: str = "local-only"


class CodeResponse(BaseModel):
    path: str
    sha: str
    start: int
    end: int
    text: str
    truncated: bool = False


class StatusResponse(BaseModel):
    repo_id: str
    sha: str
    schema_version: int
    files: int = 0
    chunks: int = 0
    symbols: int = 0


class IndexResponse(BaseModel):
    repo_id: str
    sha: str
    files: int
    chunks: int
    symbols: int
    failed: list = Field(default_factory=list)

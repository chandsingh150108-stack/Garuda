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
    why: bool = False  # Phase 14: attach commit-record history blocks


class SegmentOut(BaseModel):
    text: str
    kind: str
    evidence_ids: list[str] = Field(default_factory=list)
    provenance: str | None = None  # Phase 14: proven|history|inferred|unknown


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


class ArchEvidence(BaseModel):
    chunk_id: str
    path: str
    lines: str


class ArchNode(BaseModel):
    id: str
    kind: str
    label: str
    paths: list[str] = Field(default_factory=list)
    evidence: list[ArchEvidence] = Field(default_factory=list)


class ArchEdge(BaseModel):
    model_from: str = Field(alias="from")
    to: str
    kind: str
    evidence: list[ArchEvidence] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ArchitectureResponse(BaseModel):
    repo_id: str
    sha: str
    nodes: list[ArchNode] = Field(default_factory=list)
    edges: list[ArchEdge] = Field(default_factory=list)
    mermaid: str = ""


class TourStep(BaseModel):
    n: int
    symbol: str
    file: str
    start: int
    end: int
    hop: str
    from_symbol: str | None = Field(default=None, alias="from")
    hop_detail: str = ""
    title: str = ""
    explanation: str = ""
    narrated_by: str = "deterministic"
    evidence: list[ArchEvidence] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class TourResponse(BaseModel):
    name: str
    question: str
    sha: str
    steps: list[TourStep] = Field(default_factory=list)
    drops: list[dict] = Field(default_factory=list)
    sequence: str = ""
    dep_hashes: dict[str, str] = Field(default_factory=dict)
    stale: bool = False


class TourSummary(BaseModel):
    name: str
    question: str
    steps: int
    stale: bool = False


class TaskEvidence(BaseModel):
    chunk_id: str
    path: str
    lines: str


class TaskItem(BaseModel):
    id: str
    kind: str
    title: str
    description: str
    file: str
    start: int
    end: int
    symbol: str | None = None
    evidence: list[TaskEvidence] = Field(default_factory=list)
    detail: str = ""
    lines: int = 1
    files_touched: int = 1
    fan_in: int = 0
    difficulty: float = 0.0
    risk: int = 0
    high_risk: bool = False
    prerequisites: list[str] = Field(default_factory=list)
    tours: list[str] = Field(default_factory=list)


class TasksResponse(BaseModel):
    repo_id: str
    sha: str
    tasks: list[TaskItem] = Field(default_factory=list)

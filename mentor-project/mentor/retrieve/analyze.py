"""Query analysis: typed token extraction (spec Phase 5, D5.1).

Extracts backticked identifiers, word tokens (CamelCase/snake_case), route-like
paths, and file-like tokens. The original query is preserved for display and
for the Phase 7 dense retriever. No stopword removal (deterministic and
explainable; unmatched words simply match nothing in symbol lookup).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BACKTICK_RE = re.compile(r"`([^`]+)`")
ROUTE_RE = re.compile(r"(?<![A-Za-z0-9_./])(/[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)*/?)")
FILE_RE = re.compile(
    r"\b([A-Za-z0-9_\-]+\.(?:py|ts|tsx|js|jsx|json|yml|yaml|toml|md|sql|html|css|ini|cfg)"
    r"|Dockerfile|Makefile)\b")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class QueryAnalysis:
    original: str
    backticked: list[str] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def analyze(query: str) -> QueryAnalysis:
    backticked = [t.strip() for t in BACKTICK_RE.findall(query) if t.strip()]
    routes = _dedup([r.rstrip("/") or "/" for r in ROUTE_RE.findall(query)])
    files = _dedup(FILE_RE.findall(query))
    # Words come from the whole query (no masking): route segments and plain
    # mentions alike must reach the symbol retriever; profits dedupe below.
    words = _dedup(WORD_RE.findall(query))
    identifiers = _dedup([*backticked, *words])
    return QueryAnalysis(original=query, backticked=backticked, words=words,
                         routes=routes, files=files, identifiers=identifiers)


def fts_terms(analysis: QueryAnalysis) -> list[str]:
    """Flat lowercase alphanumeric terms for the FTS MATCH query."""
    terms: list[str] = []
    for token in [*analysis.identifiers, *analysis.routes, *analysis.files]:
        terms.extend(t.lower() for t in re.findall(r"[a-z0-9]+", token.lower()))
    return _dedup(terms)

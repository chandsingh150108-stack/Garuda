"""Identifier splitting for lexical retrieval (spec Phase 4, D4.1).

Splits camelCase, PascalCase, snake_case, digits, and path segments into
lowercase tokens. Both the original token and its parts are indexed so that
exact (`create_user`) and fuzzy (`create user`) queries match.
"""
from __future__ import annotations

import re

# Word-ish tokens in code or paths.
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# camelCase / PascalCase / acronym / letter<->digit boundaries.
_SPLIT_RE = re.compile(r"""
    (?<=[a-z])(?=[A-Z])          # get|User
  | (?<=[A-Z])(?=[A-Z][a-z])     # HTTP|Server
  | (?<=[A-Za-z])(?=[0-9])       # v|1, oauth|2
  | (?<=[0-9])(?=[A-Za-z])       # 2|FA
""", re.VERBOSE)


def split_identifier(token: str) -> list[str]:
    """Split one identifier into lowercase parts.

    >>> split_identifier("getUserById")
    ['get', 'user', 'by', 'id']
    >>> split_identifier("create_user")
    ['create', 'user']
    """
    chunks = re.split(r"[^0-9A-Za-z]+", token)
    parts: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        for piece in _SPLIT_RE.split(chunk):
            piece = piece.strip("_").lower()
            if piece:
                parts.append(piece)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique = [p for p in parts if not (p in seen or seen.add(p))]
    return unique


def identifiers_text(text: str, path: str) -> str:
    """Indexable string: original tokens (lowercased) + their parts.

    Code tokens come from identifier-like runs; path tokens from `/`- and
    `.`-separated segments (so `users.py` and route fragments match).
    """
    originals: list[str] = []
    for tok in TOKEN_RE.findall(text):
        originals.append(tok.lower())
    for seg in re.split(r"[^0-9A-Za-z]+", path):
        if seg:
            originals.append(seg.lower())
    terms: list[str] = list(originals)
    for tok in originals:
        terms.extend(split_identifier(tok))
    seen: set[str] = set()
    return " ".join(t for t in terms if not (t in seen or seen.add(t)))

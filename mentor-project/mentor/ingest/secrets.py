"""Regex secret scanner (spec Phase 2).

Matching files are excluded from indexing. Only SHA-256 hashes of matched
lines are stored -- never the secret value itself. No logging of values.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# Categories mapped to compiled patterns. Patterns match *indicators*; the
# caller stores only hashes, never the matched text.
PATTERNS: dict[str, re.Pattern[str]] = {
    # AWS access key ID (example: AKIAIOSFODNN7EXAMPLE)
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Private key headers
    "private_key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    # Generic password/api_key assignments with a long value (>=8 chars).
    # Deliberately narrow to `password` / `api_key` names to limit false positives.
    # Generic password/api_key assignments, but ONLY with quoted string
    # literals. Bare variable references and kwarg passing (e.g.
    # `password=user_in.password`) are code, not key material, and must not
    # exclude whole source files from the index. Real deployed secrets live
    # in `.env`/key files, which are excluded by filename.
    "password_assignment": re.compile(
        r"(?i)\bpassword\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
    "api_key_assignment": re.compile(
        r"(?i)\bapi_key\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
    # JWT-like compact serialization (header.payload.signature)
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}


@dataclass(frozen=True)
class SecretFinding:
    category: str
    line_number: int
    line_hash: str  # sha256 of the full line text; the value is never stored


def _hash_line(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8", errors="replace")).hexdigest()


def scan_text(text: str) -> list[SecretFinding]:
    """Scan text and return findings (hashes only)."""
    findings: list[SecretFinding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for category, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(SecretFinding(category, lineno, _hash_line(line)))
                break  # one finding per line is enough to exclude the file
    return findings


def scan_file(path: Path, max_bytes: int = 1_000_000) -> list[SecretFinding]:
    """Scan a file without following symlinks (caller must lstat-check first)."""
    try:
        if path.stat().st_size > max_bytes:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text)


def contains_secret(text: str) -> bool:
    return bool(scan_text(text))

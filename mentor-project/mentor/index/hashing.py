"""SHA-256 hashing and chunk identity (spec Phase 4, D4.3)."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def chunk_id(repo_sha: str, path: str, start_line: int, end_line: int,
             content_hash: str) -> str:
    """Deterministic chunk identity (newline-joined, unambiguous)."""
    joined = "\n".join([repo_sha, path, str(start_line), str(end_line), content_hash])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

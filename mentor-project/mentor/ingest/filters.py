"""File filters for sandboxed ingestion (spec Phase 2).

Never follows symlinks. Never fetches submodules. Never executes repo code.
Path safety via realpath confinement. No shell use.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mentor.config import LOCKFILE_MAX_BYTES, MAX_FILE_BYTES

ALLOWED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml",
    ".toml", ".md", ".sql", ".html", ".css", ".ini", ".cfg",
}
ALLOWED_BASENAMES = {"Dockerfile", "Makefile"}

EXCLUDED_DIRS = {"node_modules", ".git", "dist", "build", ".venv", "__pycache__"}

LOCKFILE_NAMES = {
    "uv.lock", "bun.lock", "bun.lockb", "package-lock.json", "poetry.lock",
    "yarn.lock", "pnpm-lock.yaml",
}

# Unconditionally excluded filenames (never indexed)
EXCLUDED_SUFFIXES = (".pem", ".key", ".p12")
EXCLUDED_PREFIXES = ("id_rsa",)
EXCLUDED_NAMES = {".env"}


@dataclass(frozen=True)
class FilterDecision:
    include: bool
    reason: str | None = None


def safe_join(repo_root: Path, relpath: str) -> Path:
    """Resolve relpath under repo_root. Reject absolute paths and `..` escapes."""
    if not relpath or os.path.isabs(relpath):
        raise ValueError(f"rejected absolute/empty path: {relpath!r}")
    # Reject `..` components before touching the filesystem.
    parts = relpath.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        raise ValueError(f"rejected path traversal: {relpath!r}")
    root = repo_root.resolve()
    candidate = (root / relpath).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"rejected escape from repo root: {relpath!r}")
    return candidate


def is_link(path: Path) -> bool:
    """True for symlinks and (Windows) junctions. Neither is ever followed."""
    try:
        if os.path.islink(path):
            return True
    except OSError:
        return True  # unreadable: treat as link (skip, never follow)
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None:
        try:
            if isjunction(path):
                return True
        except OSError:
            return True
    return False


def is_excluded_filename(name: str) -> bool:
    if name in EXCLUDED_NAMES:
        return True
    lowered = name.lower()
    if any(lowered.endswith(s) for s in EXCLUDED_SUFFIXES):
        return True
    if any(name.startswith(p) for p in EXCLUDED_PREFIXES):
        return True
    return False


def is_submodule(path: Path, repo_root: Path) -> bool:
    """Detect git submodule (gitlink) without fetching anything.

    A directory is treated as a submodule if it contains a `.git` *file*
    (gitlink pointer) or is listed in the repo `.gitmodules` file.
    """
    try:
        if path.is_dir() and (path / ".git").is_file():
            return True
    except OSError:
        return False
    try:
        gitmodules = repo_root / ".gitmodules"
        if gitmodules.is_file():
            text = gitmodules.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(repo_root).as_posix()
            # Match `path = <rel>` lines with surrounding whitespace.
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("path"):
                    _, _, value = stripped.partition("=")
                    if value.strip().strip('"').strip("'") == rel:
                        return True
    except (OSError, ValueError):
        pass
    return False


def decide_file(path: Path, repo_root: Path) -> FilterDecision:
    """Decide whether a filesystem entry should be indexed.

    `path` must be an absolute or repo-root-relative path. Symlinks are
    detected via lstat (never followed) and always skipped.
    """
    try:
        rel = path.relative_to(repo_root.resolve())
    except ValueError:
        return FilterDecision(False, "outside_root")
    # Excluded directories at any depth.
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return FilterDecision(False, "excluded_dir")
    try:
        if is_link(path):
            return FilterDecision(False, "symlink")
    except OSError:
        return FilterDecision(False, "unreadable")
    try:
        if path.is_dir():
            if is_submodule(path, repo_root.resolve()):
                return FilterDecision(False, "submodule")
            return FilterDecision(False, "directory")
    except OSError:
        return FilterDecision(False, "unreadable")
    name = path.name
    if is_excluded_filename(name):
        return FilterDecision(False, "excluded_filename")
    if name in LOCKFILE_NAMES:
        try:
            if path.stat().st_size > LOCKFILE_MAX_BYTES:
                return FilterDecision(False, "lockfile_size")
        except OSError:
            return FilterDecision(False, "unreadable")
    suffix = path.suffix.lower()
    if name not in ALLOWED_BASENAMES and suffix not in ALLOWED_EXTENSIONS:
        return FilterDecision(False, "extension")
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return FilterDecision(False, "size")
    except OSError:
        return FilterDecision(False, "unreadable")
    # Binary detection: NUL byte in the first 8 KiB.
    try:
        with open(path, "rb") as fh:
            if b"\x00" in fh.read(8192):
                return FilterDecision(False, "binary")
    except OSError:
        return FilterDecision(False, "unreadable")
    return FilterDecision(True, None)


def guess_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".json": "json",
        ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".md": "markdown",
        ".sql": "sql", ".html": "html", ".css": "css", ".ini": "ini",
        ".cfg": "cfg",
    }.get(suffix, "text" if path.name in ALLOWED_BASENAMES else "other")

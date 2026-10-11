"""Repository acquisition: verify pinned SHA and working-tree cleanliness.

Reads but never executes repository code. All subprocess calls use arg
lists (no shell=True).
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AcquireError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise AcquireError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


@dataclass(frozen=True)
class RepoInfo:
    path: Path
    pinned_sha: str
    head_sha: str
    dirty: bool


def check_repo(repo: Path, pinned_sha: str, allow_dirty: bool = False) -> RepoInfo:
    """Verify repo is at pinned_sha and (unless allowed) clean."""
    if not (repo / ".git").exists():
        # Worktree without .git dir is still possible (.git file); check rev-parse.
        pass
    head = _git(repo, "rev-parse", "HEAD")
    if head != pinned_sha:
        raise AcquireError(f"HEAD {head} != pinned {pinned_sha}")
    status = _git(repo, "status", "--porcelain")
    dirty = bool(status.strip())
    if dirty and not allow_dirty:
        raise AcquireError("working tree is dirty (use --allow-dirty to override)")
    return RepoInfo(path=repo, pinned_sha=pinned_sha, head_sha=head, dirty=dirty)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a pinned repository checkout.")
    parser.add_argument("--repo", required=True, help="Local repository path")
    parser.add_argument("--sha", required=True, help="Pinned commit SHA")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    info = check_repo(Path(args.repo), args.sha, args.allow_dirty)
    print(f"OK repo={info.path} sha={info.head_sha} dirty={info.dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

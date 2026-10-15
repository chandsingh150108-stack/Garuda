"""Install an opt-in post-commit hook running `mentor reindex` (Phase 17, D17.4).

The hook is NEVER installed automatically: this script only writes
`<repo>/.git/hooks/post-commit` when the operator runs it explicitly with
`--install`. The hook itself runs `mentor reindex` against the working tree
so tour/answer caches notice stale dependencies after each commit.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

HOOK_BODY = """#!/bin/sh
# Codebase Mentor freshness hook (opt-in, Phase 17 D17.4).
# Re-index only changed rows after each commit. Safe to delete.
python -m mentor.cli reindex --repo "{repo}" --index "{index}" --cache "{cache}" \
  >> "{log}" 2>&1
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the opt-in post-commit hook.")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--index", default="data/indexes/fst.sqlite")
    parser.add_argument("--cache", default="data/cache")
    parser.add_argument("--install", action="store_true",
                        help="actually write .git/hooks/post-commit")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    hook = repo / ".git" / "hooks" / "post-commit"
    body = HOOK_BODY.format(repo=repo, index=Path(args.index).resolve(),
                            cache=Path(args.cache).resolve(),
                            log=str(repo / ".git" / "mentor-reindex.log"))
    if not args.install:
        print("dry run (pass --install to write):")
        print(body)
        print(f"target: {hook}")
        return 0
    if not (repo / ".git").is_dir():
        print(f"not a git repo: {repo}")
        return 1
    hook.write_text(body, encoding="utf-8")
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass
    print(f"wrote {hook} (opt-in; delete to remove)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

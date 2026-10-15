"""Scripted demo edit for the freshness story (Phase 17, used in Phase 21).

Default mode creates a scratch file `<repo>/demo_live_edit_scratch.py`
(zero risk to pinned sources); `--target REL` instead appends one comment
line to a tracked file. `--revert` undoes the change (git checkout for
tracked files, delete for the scratch file). Prints content hashes before
and after so the stale badge is demonstrable.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import subprocess
from pathlib import Path

MARKER = "# demo-live-edit"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scripted demo edit.")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--target", default=None,
                        help="tracked file to append a comment to"
                             " (default: create a scratch file)")
    parser.add_argument("--revert", action="store_true",
                        help="undo the demo edit")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if args.target:
        target = repo / args.target
        if args.revert:
            subprocess.run(["git", "-C", str(repo), "checkout", "--",
                            args.target], check=False)
            print(f"reverted {args.target}")
            return 0
        before = _sha256_file(target) if target.is_file() else "missing"
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(f"\n{MARKER} {stamp}\n")
        print(f"edited {args.target}")
        print(f"  before={before[:12]} after={_sha256_file(target)[:12]}")
        return 0
    scratch = repo / "demo_live_edit_scratch.py"
    if args.revert:
        scratch.unlink(missing_ok=True)
        print("removed demo_live_edit_scratch.py")
        return 0
    scratch.write_text(
        '"""Scratch file for the live-edit freshness demo (untracked)."""\n'
        "\n"
        "DEMO_SCRATCH = True\n", encoding="utf-8")
    print(f"created {scratch.relative_to(repo)}")
    print(f"  sha256={_sha256_file(scratch)[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

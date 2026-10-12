"""`mentor` command-line entry point (spec Phase 4: `mentor index ...`).

Run as `python -m mentor.cli index --repo data/repos/fst --sha <SHA>
--out data/indexes/fst.sqlite`. Later phases add `search`, `ask`, `serve`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def cmd_index(args) -> int:
    from mentor.index import store as store
    stats = store.build(Path(args.repo), Path(args.manifest), Path(args.parses),
                        Path(args.out), repo_id=args.repo_id, timeout_s=args.timeout)
    counts = store.table_counts(Path(args.out))
    print(f"files={stats['files']} chunks={stats['chunks']} symbols={stats['symbols']} "
          f"failed={stats['failed']}")
    print("counts:", " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mentor", description="Codebase Mentor")
    sub = parser.add_subparsers(dest="command", required=True)
    idx = sub.add_parser("index", help="Build a SQLite index for a pinned repo")
    idx.add_argument("--repo", default="data/repos/fst")
    idx.add_argument("--sha", default=PINNED_SHA)
    idx.add_argument("--manifest", default=None)
    idx.add_argument("--parses", default=None)
    idx.add_argument("--out", default="data/indexes/fst.sqlite")
    idx.add_argument("--repo-id", default="fst")
    idx.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.command == "index":
        if args.manifest is None:
            args.manifest = f"data/manifests/{args.sha}.json"
        if args.parses is None:
            args.parses = f"data/parses/{args.sha}.json"
        return cmd_index(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Manifest builder: walk repo, filter, secret-scan, hash (spec Phase 2).

Writes data/manifests/<sha>.json with per-file path/size/sha256/language
and skipped reasons. Secret values are never stored -- only line hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from mentor.ingest import filters as F
from mentor.ingest import secrets as S


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(repo_root: Path, pinned_sha: str) -> dict:
    root = repo_root.resolve()
    entries: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        # Prune excluded dirs without following symlinks.
        dirnames[:] = [d for d in dirnames if d not in F.EXCLUDED_DIRS]
        # Drop symlinked dirs (never follow).
        kept: list[str] = []
        for d in dirnames:
            full = Path(dirpath) / d
            if F.is_link(full):
                rel = os.path.relpath(str(full), root).replace("\\", "/")
                entries.append({
                    "path": rel,
                    "size": 0, "sha256": None,
                    "language": "other", "skipped": "symlink",
                })
            elif F.is_submodule(full, root):
                entries.append({
                    "path": os.path.relpath(str(full), root).replace("\\", "/"),
                    "size": 0, "sha256": None,
                    "language": "other", "skipped": "submodule",
                })
                # Do not descend into submodules.
            else:
                kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            full = Path(dirpath) / name
            rel = os.path.relpath(str(full), root).replace("\\", "/")
            if F.is_link(full):
                entries.append({"path": rel, "size": 0, "sha256": None,
                                "language": "other", "skipped": "symlink"})
                continue
            decision = F.decide_file(full, root)
            if not decision.include:
                entries.append({"path": rel, "size": 0, "sha256": None,
                                "language": F.guess_language(full),
                                "skipped": decision.reason})
                continue
            findings = S.scan_file(full)
            if findings:
                entries.append({
                    "path": rel,
                    "size": int(full.stat().st_size),
                    "sha256": sha256_file(full),
                    "language": F.guess_language(full),
                    "skipped": "secret",
                    "secret_categories": sorted({f.category for f in findings}),
                    "secret_line_hashes": [f.line_hash for f in findings],
                })
                continue
            entries.append({
                "path": rel,
                "size": int(full.stat().st_size),
                "sha256": sha256_file(full),
                "language": F.guess_language(full),
                "skipped": None,
            })
    entries.sort(key=lambda e: e["path"])
    return {"sha": pinned_sha, "repo": root.name, "count": len(entries), "files": entries}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an ingest manifest.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    manifest = build_manifest(Path(args.repo), args.sha)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({manifest['count']} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

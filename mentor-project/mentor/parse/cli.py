"""Parse CLI: symbols/imports/routes/models for a pinned repo (spec Phase 3).

Reads the Phase 2 manifest for the file list, parses each file in an
isolated worker, joins model inheritance repo-wide, builds edges, extracts
config facts, and writes `data/parses/<sha>.json` for Phase 4.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mentor.parse import config_extract, edges as E
from mentor.parse import parse_worker as W
from mentor.parse import treesitter as T

PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def load_manifest(repo: Path, sha: str) -> list[str]:
    manifest = json.loads((Path("data/manifests") / f"{sha}.json").read_text(encoding="utf-8"))
    rels = []
    for entry in manifest["files"]:
        if entry.get("skipped") is not None:
            continue
        suffix = Path(entry["path"]).suffix.lower()
        if suffix in T.LANGUAGE_FOR_EXT:
            rels.append(entry["path"])
    return sorted(rels)


def join_models(files: dict[str, dict]) -> list[dict]:
    """Keep table=True classes whose bases chain to SQLModel (same-file
    first, then repo-wide by simple name)."""
    simple_bases: dict[str, set[str]] = {}
    own: dict[tuple[str, str], set[str]] = {}
    for path, parsed in files.items():
        if parsed.get("status") != "parsed" or parsed.get("language") != "python":
            continue
        for sym in parsed.get("symbols", []):
            if sym.get("kind") != "class":
                continue
            bases = set(sym.get("bases") or [])
            own[(path, sym["name"])] = bases
            simple_bases.setdefault(sym["name"], set()).update(bases)
    sqlmodelish = {"SQLModel"}
    changed = True
    while changed:
        changed = False
        for name, bases in simple_bases.items():
            if name in sqlmodelish:
                continue
            simple = {b.split(".")[-1] for b in bases}
            if simple & sqlmodelish:
                sqlmodelish.add(name)
                changed = True
    models = []
    for path, parsed in files.items():
        if parsed.get("status") != "parsed":
            continue
        for model in parsed.get("models", []):
            bases = own.get((path, model["class"]), set())
            simple = {b.split(".")[-1] for b in bases}
            chain = [b for b in bases if b.split(".")[-1] in sqlmodelish]
            if "SQLModel" in simple or simple & sqlmodelish or chain:
                model = dict(model)
                model["sqlmodel_chain"] = sorted(simple & sqlmodelish or set(chain))
                models.append(model)
    return sorted(models, key=lambda m: (m["file"], m["lines"][0]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse a pinned repository.")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--sha", default=PINNED_SHA)
    parser.add_argument("--out", default=None)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    rels = load_manifest(repo, args.sha)

    def progress(done: int, total: int):
        if done == total or done % 100 == 0:
            print(f"parse {done}/{total}", file=sys.stderr, flush=True)

    files = W.parse_many(repo, rels, timeout_s=args.timeout, progress=progress)
    parsed = sum(1 for r in files.values() if r.get("status") == "parsed")
    failed = sorted(p for p, r in files.items() if r.get("status") != "parsed")
    edge_data = E.build_edges(files)
    config = config_extract.extract_repo_config(repo)
    routes = sorted(
        ({**r} for p, f in files.items() if f.get("status") == "parsed" for r in f.get("routes", [])),
        key=lambda r: (r["file"], r["decorator_line"]),
    )
    models = join_models(files)
    include_notes = sorted(
        ({**i, "file": p} for p, f in files.items()
         if f.get("status") == "parsed" for i in f.get("include_routers", [])),
        key=lambda i: (i["file"], i["line"]),
    )
    out = {
        "sha": args.sha, "files": files, "routes": routes, "models": models,
        "include_routers": include_notes, "edges": edge_data, "config": config,
        "coverage": {"total": len(rels), "parsed": parsed,
                     "failed": failed, "failed_count": len(failed),
                     "pct": round(100 * parsed / len(rels), 2) if rels else 100.0},
    }
    out_path = Path(args.out or f"data/parses/{args.sha}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    cov = out["coverage"]
    print(f"parsed {cov['parsed']}/{cov['total']} ({cov['pct']}%), "
          f"failed={cov['failed_count']}, routes={len(routes)}, models={len(models)}")
    for f in failed:
        print(f"FAILED {f}: {files[f].get('reason')}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Counterfactual gold builder (spec Phase 6, D2.4 map applied to gold).

Renames do not move lines (whole-word/whole-string substitutions), so gold
ranges keep their line numbers; validity means every renamed symbol in an
original range appears under its new name in the counterfactual range.
Questions and must_include facts are renamed the same way so the set does
not leak original identifiers.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml


def apply_map(text: str, rename_map: dict) -> str:
    idents = rename_map.get("identifiers", {})
    for old in sorted(idents, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(old)}\b", idents[old], text)
    routes = rename_map.get("routes", {})
    for old in sorted(routes, key=len, reverse=True):
        text = text.replace(old, routes[old])
    return text


def range_text(repo: Path, path: str, start: int, end: int) -> str:
    lines = (repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[start - 1:end])


def build(v1_path: Path, map_path: Path, out_path: Path) -> dict:
    rename_map = json.loads(map_path.read_text(encoding="utf-8"))
    doc = yaml.safe_load(v1_path.read_text(encoding="utf-8"))
    for item in doc["items"]:
        item["question"] = apply_map(item["question"], rename_map)
        item["must_include"] = [apply_map(m, rename_map) for m in item.get("must_include", [])]
        item["counterfactual_of"] = item["id"]
    doc["derived_from"] = {"gold": v1_path.name, "map": map_path.name,
                           "identifiers": len(rename_map.get("identifiers", {})),
                           "routes": len(rename_map.get("routes", {}))}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
                        encoding="utf-8")
    return {"items": len(doc["items"]), "out": str(out_path)}


def check(v1_path: Path, cf_path: Path, map_path: Path,
          repo: Path, cf_repo: Path) -> list[str]:
    """Every renamed symbol in an original range must appear renamed in the
    counterfactual range at the same lines."""
    rename_map = json.loads(map_path.read_text(encoding="utf-8"))
    idents = rename_map.get("identifiers", {})
    v1 = yaml.safe_load(v1_path.read_text(encoding="utf-8"))["items"]
    cf = {i["counterfactual_of"]: i
          for i in yaml.safe_load(cf_path.read_text(encoding="utf-8"))["items"]}
    problems = []
    for item in v1:
        other = cf.get(item["id"])
        if other is None:
            problems.append(f"{item['id']}: missing in counterfactual set")
            continue
        for g in item.get("gold", []):
            original = range_text(repo, g["path"], g["start_line"], g["end_line"])
            mirrored = range_text(cf_repo, g["path"], g["start_line"], g["end_line"])
            for old, new in idents.items():
                if re.search(rf"\b{re.escape(old)}\b", original):
                    if not re.search(rf"\b{re.escape(new)}\b", mirrored):
                        problems.append(f"{item['id']}: {g['path']}:{g['start_line']}"
                                        f" lacks renamed {new}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build counterfactual gold set.")
    parser.add_argument("--map", default="evals/counterfactual_map.json")
    parser.add_argument("--gold", default="evals/gold/v1.yaml")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--cf-repo", default="data/repos/fst-cf")
    parser.add_argument("--out", default="evals/gold/v1_counterfactual.yaml")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.check_only:
        info = build(Path(args.gold), Path(args.map), Path(args.out))
        print(f"wrote {info['out']} ({info['items']} items)")
    problems = check(Path(args.gold), Path(args.out), Path(args.map),
                     Path(args.repo), Path(args.cf_repo))
    if problems:
        print("INVALID:")
        for p in problems:
            print(f"  {p}")
        return 1
    print("counterfactual gold valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

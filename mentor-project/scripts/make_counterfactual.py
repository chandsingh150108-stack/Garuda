"""Build a counterfactual repository copy (spec Phase 2, D2.4).

Copies src -> dst (excluding .git and caches), renames 20 identifiers
chosen from defined symbols with >2 references, changes 5 route path
strings and 3 configuration default values. Writes a rename map JSON.

The copy is never executed. Replacement is whole-word over text files so
no occurrence of an old identifier remains (intentionally-kept list is
therefore empty and recorded as such).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path

CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEXT_EXTS = CODE_EXTS | {".json", ".yml", ".yaml", ".toml", ".md"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "dist", "build"}

DEF_RE = re.compile(r"^\s*(?:class|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", re.MULTILINE)
ROUTE_RE = re.compile(r'"((?:/[a-z0-9_\-]+)+/?)"')
CONFIG_LINE_RE = re.compile(r"^(\s*[A-Z][A-Z0-9_]*\s*[:=]\s*)(.+?)\s*$")


def _iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_EXTS:
            yield path


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def pick_identifiers(root: Path, limit: int = 20) -> list[str]:
    """Defined symbols (class/def) with >2 whole-word references."""
    defined: set[str] = set()
    for path in _iter_text_files(root):
        if path.suffix.lower() not in CODE_EXTS:
            continue
        text = _read(path)
        if text is None:
            continue
        defined.update(DEF_RE.findall(text))
    counts: Counter[str] = Counter()
    for path in _iter_text_files(root):
        if path.suffix.lower() not in CODE_EXTS:
            continue
        text = _read(path)
        if text is None:
            continue
        for name in defined:
            # Whole-word count; skip dunder and very short names (noise).
            if name.startswith("__") or len(name) < 3:
                continue
            counts[name] += len(re.findall(rf"\b{re.escape(name)}\b", text))
    ranked = sorted(
        (n for n, c in counts.items() if c > 2),
        key=lambda n: (-counts[n], n),
    )
    return ranked[:limit]


def pick_routes(root: Path, limit: int = 5) -> list[str]:
    found: set[str] = set()
    routes_dir = root / "backend" / "app" / "api" / "routes"
    search_roots = [routes_dir] if routes_dir.is_dir() else [root]
    for base in search_roots:
        for path in sorted(base.rglob("*.py")):
            text = _read(path)
            if text is None:
                continue
            found.update(ROUTE_RE.findall(text))
    # Prefer API-like paths, deterministic order. The signup/register flow is
    # the demo's key tour, so a signup-like route is always included when
    # present (stronger contamination control for the most-asked question).
    preferred = [p for p in sorted(found) if len(p) > 1]
    preferred.sort(key=lambda p: (0 if "signup" in p or "register" in p else 1, p))
    return preferred[:limit]


def apply_counterfactual(src: Path, dst: Path) -> dict:
    if dst.exists():
        raise SystemExit(f"dst exists: {dst} (delete and regenerate)")
    shutil.copytree(src, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(*IGNORE_DIRS, ".git"))
    idents = pick_identifiers(dst, 20)
    if len(idents) < 20:
        raise SystemExit(f"only {len(idents)} rename candidates found (need 20)")
    ident_map = {old: f"{old}_cf" for old in idents}
    route_olds = pick_routes(dst, 5)
    if len(route_olds) < 5:
        raise SystemExit(f"only {len(route_olds)} route candidates found (need 5)")
    route_map = {old: (old.rstrip("/") + "-cf") for old in route_olds}

    # Apply identifier + route renames over code/text files.
    for path in _iter_text_files(dst):
        text = _read(path)
        if text is None:
            continue
        new = text
        for old in sorted(ident_map, key=len, reverse=True):
            new = re.sub(rf"\b{re.escape(old)}\b", ident_map[old], new)
        for old in sorted(route_map, key=len, reverse=True):
            # Whole-literal forms first, then substring occurrences inside
            # longer paths (e.g. f"{API}/login/access-token"). The lookahead
            # prevents corrupting longer segments (e.g. `/me` in `/memory`).
            new = new.replace(f'"{old}"', f'"{route_map[old]}"')
            new = new.replace(f"'{old}'", f"'{route_map[old]}'")
            new = re.sub(re.escape(old) + r"(?![A-Za-z0-9_-])",
                         route_map[old], new)
        if new != text:
            path.write_text(new, encoding="utf-8")

    # Config defaults: first 3 UPPER_CASE assignments with a value in
    # backend/app/core/config.py (fallback: any *config*.py), value suffixed.
    config_map: dict[str, dict[str, str]] = {}
    candidates = sorted((dst / "backend" / "app" / "core").glob("config*.py"))
    if not candidates:
        candidates = sorted(dst.rglob("*config*.py"))[:3]
    for cfg in candidates[:1]:
        lines = cfg.read_text(encoding="utf-8").splitlines()
        changed = 0
        out: list[str] = []
        for line in lines:
            match = CONFIG_LINE_RE.match(line)
            if match and changed < 3 and '"' in line:
                prefix, value = match.group(1), match.group(2)
                new_value = re.sub(r'"([^"]*)"', r'"\1-cf"', value, count=1)
                if new_value != value:
                    key = re.split(r"[:=]", line, maxsplit=1)[0].strip()
                    config_map[key] = {"old": value.strip(), "new": new_value.strip()}
                    line = prefix + new_value
                    changed += 1
            out.append(line)
        cfg.write_text("\n".join(out) + "\n", encoding="utf-8")
        if changed >= 3:
            break
    if len(config_map) < 3:
        raise SystemExit(f"only {len(config_map)} config defaults changed (need 3)")

    return {
        "identifiers": ident_map,
        "routes": route_map,
        "config": config_map,
        "intentionally_kept_string_literals": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build counterfactual repo copy.")
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    parser.add_argument("--map", required=True)
    args = parser.parse_args(argv)
    rename_map = apply_counterfactual(Path(args.src), Path(args.dst))
    map_path = Path(args.map)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(rename_map, indent=2), encoding="utf-8")
    print(f"renamed {len(rename_map['identifiers'])} identifiers, "
          f"{len(rename_map['routes'])} routes, "
          f"{len(rename_map['config'])} config defaults -> {map_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

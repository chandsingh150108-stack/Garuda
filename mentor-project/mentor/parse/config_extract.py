"""Configuration fact extraction (spec Phase 3).

Parses compose YAML (services, images, ports, environment KEY NAMES only),
`pyproject.toml` (dependencies, scripts), and `package.json` (scripts,
dependencies). Secret-looking values are never emitted: environment entries
contribute names only; the SECRET|KEY|PASSWORD|TOKEN rule is enforced by
construction (values are dropped before they reach the output).
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

SECRET_NAME = re.compile(r"SECRET|KEY|PASSWORD|TOKEN")

COMPOSE_GLOBS = ("compose.yml", "compose.yaml", "docker-compose.yml",
                 "docker-compose.yaml", "compose.*.yml", "compose.*.yaml")
PYPROJECT_NAMES = ("pyproject.toml",)
PACKAGE_NAMES = ("package.json",)


def _env_keys(env) -> list[str]:
    """Environment key names only. Values are dropped unconditionally."""
    keys: list[str] = []
    if isinstance(env, dict):
        keys.extend(str(k) for k in env.keys())
    elif isinstance(env, list):
        for item in env:
            if not isinstance(item, str):
                continue
            key = item.split("=", 1)[0].strip()
            if key:
                keys.append(key)
    return sorted(set(keys))


def extract_compose(path: Path) -> dict:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"file": None, "status": "parse_failed", "reason": f"yaml: {exc}"}
    if not isinstance(doc, dict):
        return {"file": None, "status": "parse_failed", "reason": "not-a-mapping"}
    services = {}
    for name, svc in (doc.get("services") or {}).items():
        if not isinstance(svc, dict):
            continue
        ports = [str(p) for p in (svc.get("ports") or [])]
        services[str(name)] = {
            "image": svc.get("image"),
            "ports": ports,
            "environment_keys": _env_keys(svc.get("environment")),
        }
    return {"status": "parsed", "services": services}


def extract_pyproject(path: Path) -> dict:
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "parse_failed", "reason": f"toml: {exc}"}
    project = doc.get("project", {}) if isinstance(doc, dict) else {}
    deps = project.get("dependencies", []) or []
    return {"status": "parsed",
            "dependencies": [str(d) for d in deps],
            "scripts": dict(project.get("scripts", {}) or {}),
            "requires_python": project.get("requires-python")}


def extract_package_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "parse_failed", "reason": f"json: {exc}"}
    if not isinstance(doc, dict):
        return {"status": "parse_failed", "reason": "not-an-object"}
    return {"status": "parsed",
            "scripts": dict(doc.get("scripts", {}) or {}),
            "dependencies": dict(doc.get("dependencies", {}) or {}),
            "devDependencies": dict(doc.get("devDependencies", {}) or {})}


def discover_config_files(repo_root: Path) -> dict[str, list[str]]:
    """Deterministic discovery of config files (sorted)."""
    root = repo_root.resolve()
    compose = sorted(p.relative_to(root).as_posix()
                     for pat in COMPOSE_GLOBS for p in root.glob(pat)
                     if p.is_file())
    pyproject = sorted(p.relative_to(root).as_posix()
                       for name in PYPROJECT_NAMES
                       for p in (root / name, root / "backend" / name)
                       if p.is_file())
    package = sorted(p.relative_to(root).as_posix()
                     for name in PACKAGE_NAMES
                     for p in (root / name, root / "frontend" / name,
                               root / "packages" / "react-email" / name)
                     if p.is_file())
    return {"compose": compose, "pyproject": pyproject, "package_json": package}


def extract_repo_config(repo_root: Path) -> dict:
    root = repo_root.resolve()
    found = discover_config_files(root)
    out: dict = {"files": found, "compose": {}, "pyproject": {}, "package_json": {}}
    for rel in found["compose"]:
        result = extract_compose(root / rel)
        result["file"] = rel
        out["compose"][rel] = result
    for rel in found["pyproject"]:
        result = extract_pyproject(root / rel)
        result["file"] = rel
        out["pyproject"][rel] = result
    for rel in found["package_json"]:
        result = extract_package_json(root / rel)
        result["file"] = rel
        out["package_json"][rel] = result
    return out

"""Phase 3 gate: config extraction goldens + secret-value exclusion (spec Phase 3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mentor.ingest import secrets as S
from mentor.parse import config_extract as C

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"


@pytest.mark.parametrize("name,fn", [
    ("compose.yml", C.extract_compose),
    ("pyproject.toml", C.extract_pyproject),
    ("package.json", C.extract_package_json),
])
def test_golden_config(name: str, fn):
    out = dict(fn(GOLDEN / name))
    out["file"] = name
    expected = json.loads((GOLDEN / f"{name}.expected.json").read_text(encoding="utf-8"))
    assert out == expected


def test_secret_values_never_emitted():
    out = C.extract_compose(GOLDEN / "compose.yml")
    blob = json.dumps(out)
    # Key names are facts and must be present ...
    assert "SECRET_KEY" in blob and "POSTGRES_PASSWORD" in blob and "API_TOKEN" in blob
    # ... but values must never appear.
    assert "supersecret-value" not in blob
    assert "${SECRET_KEY" not in blob
    assert "abc123" not in blob
    assert S.scan_text(blob) == []


def test_env_key_forms():
    assert C._env_keys({"A": "1", "B": "2"}) == ["A", "B"]
    assert C._env_keys(["X=1", "Y", "SECRET_KEY=${SECRET_KEY:?x}"]) == [
        "SECRET_KEY", "X", "Y"]
    assert C._env_keys(None) == []


def test_fst_config_discovery_and_hygiene():
    repo = ROOT / "data" / "repos" / "fst"
    if not (repo / ".git").exists():
        pytest.skip("primary repo not cloned")
    found = C.discover_config_files(repo)
    assert set(found["compose"]) == {
        "compose.yml", "compose.deploy.yml", "compose.override.yml"}
    assert "backend/pyproject.toml" in found["pyproject"]
    assert "frontend/package.json" in found["package_json"]
    out = C.extract_repo_config(repo)
    blob = json.dumps(out)
    assert S.scan_text(blob) == []
    services = out["compose"]["compose.yml"]["services"]
    assert set(services) >= {"db", "backend"}
    assert services["db"]["image"] == "postgres:18"
    assert "POSTGRES_PASSWORD" in services["db"]["environment_keys"]

"""Phase 3 gate: Python parsing goldens, invariants, worker, edges (spec Phase 3).

Golden files freeze exact extractor output for hand-verified fixtures.
The line-invariant test enforces the spec rule (first text line of a symbol
is its signature line) plus range validity on goldens AND the full fst run.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from mentor.parse import edges as E
from mentor.parse import parse_worker as W
from mentor.parse import py_extract as P

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"

PY_GOLDENS = ["py_basic.py", "py_routes.py", "py_models.py", "py_imports.py"]


def _extract_fixture(name: str) -> dict:
    path = GOLDEN / name
    return P.extract_py(path, path.read_bytes(), GOLDEN)


def _expected(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", PY_GOLDENS)
def test_golden_python(name: str):
    assert _extract_fixture(name) == _expected(name)


def _lines_for(parsed: dict) -> list[str]:
    return (GOLDEN / parsed["path"]).read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("name", PY_GOLDENS)
def test_line_invariant_goldens(name: str):
    parsed = _expected(name)
    assert W.check_ranges(parsed, _lines_for(parsed)) == []


def test_import_resolution_unit(tmp_path: Path):
    backend = tmp_path / "backend" / "app" / "api"
    backend.mkdir(parents=True)
    (tmp_path / "backend" / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "backend" / "app" / "crud.py").write_text("X = 1\n", encoding="utf-8")
    importer = backend / "routes.py"
    importer.write_text("from app import crud\nimport missing_xyz\n", encoding="utf-8")
    out = P.extract_py(importer, importer.read_bytes(), tmp_path)
    by_module = {i["module"]: i for i in out["imports"]}
    # Module-level resolution: `app` is the package (name-level `crud`
    # resolution is edges' job, not the extractor's).
    assert by_module["app"]["resolved"] == "backend/app/__init__.py"
    assert by_module["missing_xyz"]["resolved"] is None


def test_relative_import_unit(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "sub.py").write_text("Y = 2\n", encoding="utf-8")
    importer = pkg / "main.py"
    importer.write_text("from .sub import y\n", encoding="utf-8")
    out = P.extract_py(importer, importer.read_bytes(), tmp_path)
    assert out["imports"][0]["resolved"] == "pkg/sub.py"
    assert out["imports"][0]["level"] == 1


def test_include_router_recorded(tmp_path: Path):
    src = ("from fastapi import APIRouter\n"
           "api_router = APIRouter()\n"
           "api_router.include_router(users.router)\n"
           "app.include_router(api_router, prefix=\"/api/v1\")\n")
    importer = tmp_path / "main.py"
    importer.write_text(src, encoding="utf-8")
    out = P.extract_py(importer, importer.read_bytes(), tmp_path)
    assert {"object": "api_router", "router": None, "prefix": None,
            "prefix_known": False, "line": 3} in out["include_routers"]
    assert {"object": "app", "router": "api_router", "prefix": "/api/v1",
            "prefix_known": True, "line": 4} in out["include_routers"]


def test_edges_resolved_and_likely():
    files = {
        "a.py": {"status": "parsed", "language": "python",
                 "symbols": [
                     {"kind": "function", "name": "f", "qualname": "f",
                      "start_line": 1, "end_line": 3,
                      "calls": [{"name": "g", "line": 2},
                                {"name": "os.getcwd", "line": 2},
                                {"name": "helper", "line": 3}]},
                     {"kind": "function", "name": "g", "qualname": "g",
                      "start_line": 5, "end_line": 6, "calls": []}],
                 "imports": [
                     {"module": "os", "line": 1, "resolved": None},
                     {"module": "lib", "line": 2, "resolved": "lib.py",
                      "names": [{"name": "helper", "alias": None}]}]},
        "lib.py": {"status": "parsed", "language": "python",
                   "symbols": [], "imports": []},
    }
    edges = E.build_edges(files)
    by_to = {(e["to"], e["label"]) for e in edges["imports"]}
    assert ("lib.py", "resolved") in by_to
    assert (None, "unresolved") in by_to
    labels = {e["label"] for e in edges["calls"]}
    assert labels == {"likely"}  # D3.3: name-based edges are only ever `likely`
    assert {e["to"] for e in edges["calls"]} >= {"g", "helper"}


def _sleep_secs(n: float):
    import time as _t
    _t.sleep(n)
    return "awake"


def test_worker_timeout_mechanism():
    t0 = time.perf_counter()
    res = W.run_isolated(_sleep_secs, (30.0,), timeout_s=2.0)
    dt = time.perf_counter() - t0
    assert res == {"ok": None, "reason": "timeout"}
    assert dt < 10.0


def test_pathological_nesting_does_not_hang(tmp_path: Path):
    nest = "x = " + "(" * 3000 + "1" + ")" * 3000 + "\n"
    victim = tmp_path / "nest.py"
    victim.write_bytes(nest.encode())
    t0 = time.perf_counter()
    res = W.parse_one(tmp_path, "nest.py", timeout_s=10.0)
    dt = time.perf_counter() - t0
    # Either outcome is safe: parsed quickly, or contained as parse_failed
    # within the timeout while the indexer continues.
    assert res["status"] in ("parsed", "parse_failed")
    assert dt < 10.0


def test_fst_artifact_coverage_routes_models_invariants():
    parses = ROOT / "data" / "parses" / f"{PINNED_SHA}.json"
    if not parses.is_file():
        pytest.skip("run: python -m mentor.parse.cli --repo data/repos/fst "
                    f"--sha {PINNED_SHA} (Phase 3 gate step 1)")
    doc = json.loads(parses.read_text(encoding="utf-8"))
    assert doc["sha"] == PINNED_SHA
    assert doc["coverage"]["pct"] >= 99.0, doc["coverage"]["failed"]
    assert doc["coverage"]["failed"] == []
    signups = [r for r in doc["routes"] if r["path"] == "/signup"]
    assert len(signups) == 1
    signup = signups[0]
    assert signup["file"] == "backend/app/api/routes/users.py"
    assert signup["handler_lines"] == [147, 159]
    assert signup["router_prefix"] == "/users" and not signup["prefix_unknown"]
    tables = {m["class"]: m["table"] for m in doc["models"]}
    assert tables == {"User": "user", "Item": "item"}
    repo = ROOT / "data" / "repos" / "fst"
    problems = []
    for rel, parsed in doc["files"].items():
        if parsed.get("status") != "parsed":
            continue
        src = (repo / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        problems.extend(f"{rel}: {p}" for p in W.check_ranges(parsed, src))
    assert problems == []

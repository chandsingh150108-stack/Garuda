"""Phase 3 gate: TypeScript parsing goldens, invariants, client calls (spec Phase 3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mentor.parse import parse_worker as W
from mentor.parse import ts_extract as X

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"

TS_GOLDENS = ["ts_basic.ts", "ts_client.ts", "ts_classes.tsx"]
GRAMMAR = {"ts_basic.ts": "typescript", "ts_client.ts": "typescript",
           "ts_classes.tsx": "tsx"}


def _extract_fixture(name: str) -> dict:
    path = GOLDEN / name
    return X.extract_ts(path, path.read_bytes(), GOLDEN, GRAMMAR[name])


def _expected(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TS_GOLDENS)
def test_golden_typescript(name: str):
    assert _extract_fixture(name) == _expected(name)


@pytest.mark.parametrize("name", TS_GOLDENS)
def test_line_invariant_goldens(name: str):
    parsed = _expected(name)
    lines = (GOLDEN / name).read_text(encoding="utf-8").splitlines()
    assert W.check_ranges(parsed, lines) == []


def test_client_calls_are_not_routes():
    parsed = _expected("ts_client.ts")
    assert parsed["routes"] == []
    by_callee = {c["callee"]: c for c in parsed["client_calls"]}
    assert by_callee["fetch"]["path"] == "/api/login/access-token"
    assert by_callee["fetch"]["line"] == 4
    assert by_callee["axios.post"]["path"] == "/api/items"
    assert by_callee["axios.post"]["line"] == 11


def test_import_resolution_unit(tmp_path: Path):
    src = tmp_path / "frontend" / "src"
    (src / "lib").mkdir(parents=True)
    (src / "lib" / "x.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (src / "hooks").mkdir(exist_ok=True)
    (src / "hooks" / "index.ts").write_text("export {};\n", encoding="utf-8")
    importer = src / "app.ts"
    importer.write_text(
        'import { x } from "@/lib/x";\n'
        'import { h } from "./hooks";\n'
        'import React from "react";\n', encoding="utf-8")
    out = X.extract_ts(importer, importer.read_bytes(), tmp_path, "typescript")
    by_module = {i["module"]: i for i in out["imports"]}
    assert by_module["@/lib/x"]["resolved"] == "frontend/src/lib/x.ts"
    assert by_module["./hooks"]["resolved"] == "frontend/src/hooks/index.ts"
    assert by_module["react"]["resolved"] is None  # bare package: external


def test_exported_const_arrow_symbol():
    parsed = _expected("ts_basic.ts")
    helper = next(s for s in parsed["symbols"] if s["name"] == "helper")
    assert helper["kind"] == "const" and helper["const_kind"] == "arrow"
    assert helper["exported"] is True
    load = next(s for s in parsed["symbols"] if s["qualname"] == "Store.load")
    assert load["kind"] == "method" and load["parent"] == "Store"

"""Phase 12 gate: component model — evidence coverage, golden match, titles."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from mentor.api import app as APP
from mentor.api import routes as R
from mentor.features import arch as A
from mentor.features import summaries as SU

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"
GOLDEN = Path(__file__).parent / "golden" / "arch_fst.json"


def test_every_node_and_edge_has_evidence():
    model = A.extract(DB, SHA)
    assert len(model["nodes"]) >= 6
    for node in model["nodes"]:
        assert node["evidence"], f"{node['id']} has no evidence"
        assert node["id"].startswith("N") and node["kind"] and node["label"]
    assert model["edges"]
    for edge in model["edges"]:
        assert edge["evidence"], f"{edge['from']}->{edge['to']} unevidenced"


def test_golden_matches_reviewed_layout():
    model = A.extract(DB, SHA)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert [(n["id"], n["kind"]) for n in model["nodes"]] == \
           [(n["id"], n["kind"]) for n in golden["nodes"]]
    assert {(e["from"], e["to"]) for e in model["edges"]} == \
           {(e["from"], e["to"]) for e in golden["edges"]}
    kinds = {n["kind"] for n in model["nodes"]}
    assert {"entrypoint", "api-layer", "model-layer", "frontend",
            "external-database", "configuration", "test"} <= kinds


def test_key_flow_edges_present():
    model = A.extract(DB, SHA)
    pairs = {(e["from"], e["to"]) for e in model["edges"]}
    assert ("N1", "N2") in pairs  # entrypoint assembles the API router
    assert ("N2", "N4") in pairs  # routes call CRUD services
    assert ("N4", "N3") in pairs  # services use models
    assert ("N5", "N2") in pairs  # frontend calls the API


def test_title_validation_rejects_unevidenced():
    node = {"id": "N2", "label": "API routes",
            "evidence": [{"chunk_id": "c"}]}
    assert SU.accept_title("API routes overview",
                           "API routes live in backend/app/api/routes") is True
    assert SU.accept_title("Billing dashboard",
                           "API routes live in backend/app/api/routes") is False
    model = {"nodes": [dict(node)]}
    out, report = SU.apply_titles(
        model, {"N2": "Billing dashboard", "N9": "Ghost"}, DB, SHA)
    assert report["N2"]["accepted"] is False
    assert out["nodes"][0]["label"] == "API routes"  # deterministic stands
    assert "N9" not in report  # unknown ids ignored


def test_architecture_endpoint_returns_model_with_links():
    import shutil
    R.REGISTRY.clear()
    db = Path("data/cache/arch_test.sqlite")
    db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(DB, db)
    R.REGISTRY["g"] = {"id": "g", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    try:
        body = TestClient(APP.create_app()).get(
            "/api/repos/g/architecture").json()
    finally:
        R.REGISTRY.clear()
    assert len(body["nodes"]) >= 6
    assert body["mermaid"].startswith("flowchart")
    assert all(n["evidence"] for n in body["nodes"])

"""Phase 15 gate: deterministic scoring, evidence, ranges, risk, tour links."""
import math
from pathlib import Path

from mentor import config as CFG
from mentor.features import tasks as TS

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def test_scoring_matches_configured_formula():
    tasks = TS.collect(DB, SHA)
    assert tasks, "fst must yield candidates"
    for task in tasks:
        expect = round(CFG.TASK_W1 * math.log(max(1, task["lines"])) +
                       CFG.TASK_W2 * task["files_touched"] +
                       CFG.TASK_W3 * task["fan_in"], 3)
        assert task["difficulty"] == expect, task["id"]
        assert task["risk"] >= 0 and task["high_risk"] == \
            (task["risk"] >= CFG.TASK_HIGH_RISK)


def test_no_task_without_evidence_and_ranges_exist():
    tasks = TS.rank(TS.collect(DB, SHA), 50)
    assert len(tasks) >= 5
    assert TS.validate(DB, SHA, tasks, Path("evals/tours")) == []
    for task in tasks:
        assert task["evidence"], task["id"]
        assert 1 <= task["start"] <= task["end"]


def test_high_risk_excluded_from_top_five():
    tasks = [{"id": f"t{i}", "difficulty": float(i), "risk": 0,
              "high_risk": False} for i in range(7)]
    tasks.append({"id": "risky-easy", "difficulty": -1.0, "risk": 99,
                  "high_risk": True})
    top = TS.rank(tasks, 10)
    assert [t["id"] for t in top[:5]] != "risky-easy"
    assert all(not t["high_risk"] for t in top[:5])
    assert top[-1]["id"] == "risky-easy"  # listed, never hidden


def test_tour_links_resolve():
    tasks = TS.link_tours(TS.collect(DB, SHA), Path("evals/tours"),
                          Path("data/cache"))
    known = {p.stem for p in Path("evals/tours").glob("*.yaml")}
    for task in tasks:
        assert all(t in known for t in task["tours"]), task["id"]
    # The crud tour touches models touched by Item tasks.
    item_tasks = [t for t in tasks if t["file"] == "backend/app/models.py"]
    assert item_tasks and all("crud" in t["tours"] or not t["tours"]
                              for t in item_tasks)


def test_tasks_endpoint_lists_validated_tasks():
    import shutil
    from fastapi.testclient import TestClient
    from mentor.api import app as APP
    from mentor.api import routes as R
    R.REGISTRY.clear()
    db = Path("data/cache/tasks_ep_test.sqlite")
    db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(DB, db)
    R.REGISTRY["k"] = {"id": "k", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    try:
        body = TestClient(APP.create_app()).get("/api/repos/k/tasks",
                                                 params={"limit": 10}).json()
    finally:
        R.REGISTRY.clear()
        db.unlink(missing_ok=True)
    assert body["sha"] == SHA and len(body["tasks"]) >= 5
    assert all(t["evidence"] for t in body["tasks"])

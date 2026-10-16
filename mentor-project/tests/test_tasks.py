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


def test_source_test_split_is_layout_agnostic():
    src = ["backend/app/crud.py", "sklearn/ensemble/_forest.py",
           "frontend/src/api/client.ts", "pkg/util.js", "src/lib/index.tsx"]
    for p in src:
        assert TS._is_source_path(p), p
    tst = ["backend/tests/test_crud.py", "sklearn/ensemble/tests/test_forest.py",
           "frontend/tests/user.spec.ts", "test_main.py", "tests/utils/utils.py",
           "sklearn/tests/test_common.py", "foo.test.js", "bar.spec.ts"]
    for p in tst:
        assert TS._is_test_path(p), p
        assert not TS._is_source_path(p), p
    assert not TS._is_source_path("sklearn/ensemble/_forest.pyx")
    assert not TS._is_source_path("doc/whats_new.rst")


def test_exclusions_match_segments_not_roots():
    assert TS._excluded("backend/app/alembic/env.py")
    assert TS._excluded("db/migrations/001_init.py")
    assert TS._excluded("frontend/src/client/sdk.gen.ts")
    assert TS._excluded("static/bundle.min.js")
    assert not TS._excluded("backend/app/crud.py")
    assert not TS._excluded("sklearn/ensemble/_forest.py")


def test_collect_fires_all_applicable_kinds_on_second_repo():
    import pytest as _pytest
    db = Path("data/indexes/sklearn.sqlite")
    if not db.is_file():
        _pytest.skip("probe artifact absent: index sklearn@85593ca first")
    kinds = {t["kind"] for t in TS.collect(
        db, "85593ca7a07a9956ac891f6bfc3fedca53b74f72")}
    assert "todo" in kinds
    assert "missing-tests" in kinds or "missing-docstring" in kinds


def test_high_risk_excluded_from_top_five():
    tasks = [{"id": f"t{i}", "difficulty": float(i), "risk": 0,
              "high_risk": False} for i in range(7)]
    tasks.append({"id": "risky-easy", "difficulty": -1.0, "risk": 99,
                  "high_risk": True})
    top = TS.rank(tasks, 10)
    assert [t["id"] for t in top[:5]] != "risky-easy"
    assert all(not t["high_risk"] for t in top[:5])
    assert top[-1]["id"] == "risky-easy"  # listed, never hidden


def test_richer_bodies_validate():
    tasks = TS.rank(TS.collect(DB, SHA), 50)
    assert TS.validate(DB, SHA, tasks, Path("evals/tours")) == []
    for task in tasks:
        assert len(task["acceptance"]) >= 2, task["id"]
        assert task["acceptance"][-1].startswith("Verify: `pytest"), task["id"]
        assert task["verify"].startswith("pytest"), task["id"]
        assert task["open_first"] is not None, task["id"]
        first = task["open_first"]
        assert first["path"] == task["file"], task["id"]
        if task["example_test"] is not None:
            assert task["verify"].split(" ")[1] == task["example_test"], task["id"]


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

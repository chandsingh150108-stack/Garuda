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
    assert TS._excluded("sklearn/externals/array_api_compat/common/_helpers.py")
    assert TS._excluded("pkg/vendor/lib.py")
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


def test_bandit_mapping_filters_and_ranks():
    import sqlite3 as _sq
    con = _sq.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        findings = [
            {"test_id": "B105", "severity": "LOW",
             "path": "backend/app/core/config.py", "line": 61,
             "issue_text": "Possible hardcoded password"},
            {"test_id": "B101", "severity": "LOW",
             "path": "backend/tests/test_x.py", "line": 5,
             "issue_text": "assert used"},
            {"test_id": "B101", "severity": "LOW",
             "path": "frontend/src/client/sdk.gen.ts", "line": 9,
             "issue_text": "generated"},
            {"test_id": "B999", "severity": "HIGH",
             "path": "backend/app/core/security.py", "line": 35,
             "issue_text": "contrived high"},
            {"test_id": "B000", "severity": "LOW",
             "path": "nowhere/nothing.py", "line": 3,
             "issue_text": "no chunks"},
        ]
        tasks = TS._bandit_tasks_from_findings(con, SHA, findings, {})
        by_id = {t["id"]: t for t in tasks}
        assert len(tasks) == 2, [t["id"] for t in tasks]
        assert by_id["security-learn-config-config-61"]["evidence"]
        high = by_id["security-learn-security-security-35"]
        assert high["high_risk"] is True
        ranked = TS.rank(tasks, 10)
        assert ranked[-1]["id"] == high["id"]  # sinks, still listed
        assert TS.validate(DB, SHA, ranked, Path("evals/tours")) == []
    finally:
        con.close()


def test_bandit_scan_round_trip_on_scratch_copy(tmp_path: Path):
    import shutil
    db = tmp_path / "bandit.sqlite"
    shutil.copy(DB, db)
    n = TS.store_bandit_scan(db, Path("data/repos/fst"), SHA)
    assert n > 0
    assert TS.read_bandit_scan(db, SHA) != []
    assert TS.read_bandit_scan(db, "deadbeef") == []
    tasks = TS.collect(db, SHA)
    assert any(t["kind"] == "security-learn" for t in tasks)
    assert TS.validate(db, SHA, TS.rank(tasks, 50),
                       Path("evals/tours")) == []


def test_gh_mapping_links_evidence_and_gates():
    import sqlite3 as _sq
    from mentor import config as CFG
    con = _sq.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        issues = [{"number": 4242,
                   "title": "register_user signup flow follow-up",
                   "body": "Please polish the signup handler.",
                   "url": "https://example.invalid/i/4242",
                   "labels": ["good first issue"]},
                  {"number": 4243, "title": "zzzz-no-such-code-qqq",
                   "body": "", "url": "https://example.invalid/i/4243",
                   "labels": ["help wanted"]}]
        tasks = TS._github_tasks_from_issues(DB, SHA, issues, {})
        by_id = {t["id"]: t for t in tasks}
        assert "good-first-issue-4242" in by_id
        task = by_id["good-first-issue-4242"]
        assert task["title"].startswith("#4242:")
        assert task["evidence"] and task["acceptance"] and task["verify"]
        assert TS.validate(DB, SHA, tasks, Path("evals/tours")) == []
    finally:
        con.close()


def test_gh_issue_without_indexed_evidence_is_skipped(monkeypatch):
    from mentor.retrieve import search as SR
    monkeypatch.setattr(SR, "search", lambda *a, **k: {"hits": []})
    issues = [{"number": 1, "title": "anything", "body": "",
               "url": "https://example.invalid/i/1", "labels": []}]
    assert TS._github_tasks_from_issues(DB, SHA, issues, {}) == []


def test_gh_gates_default_off_and_offline(monkeypatch):
    from mentor import config as CFG
    assert CFG.ALLOW_GH_TASKS is False
    assert TS.collect(DB, SHA, gh_repo="owner/repo") == TS.collect(DB, SHA)
    monkeypatch.setattr(CFG, "ALLOW_GH_TASKS", True)
    monkeypatch.setenv("MENTOR_MODE", "LOCAL-OFFLINE")
    try:
        assert TS.collect(DB, SHA, gh_repo="owner/repo") == TS.collect(DB, SHA)
    finally:
        monkeypatch.delenv("MENTOR_MODE")


def test_fetch_gh_issues_without_binary_is_empty(monkeypatch):
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda *a, **k: None)
    assert TS.fetch_gh_issues("owner/repo") == []


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

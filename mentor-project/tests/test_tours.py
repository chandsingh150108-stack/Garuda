"""Phase 13 gate: caps, evidence rule, labels, determinism, golden signup."""
import json
import sqlite3
from pathlib import Path

from mentor.features import tours as T

DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def _mini_db(path: Path) -> None:
    """Synthetic index: chain root->a->b->c->d->e plus a 10-fan at root."""
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE files (snapshot_sha TEXT, path TEXT, sha256 TEXT);
        CREATE TABLE routes (snapshot_sha TEXT, method TEXT, path TEXT,
            handler TEXT, file TEXT, handler_start INT, handler_end INT);
        CREATE TABLE symbols (snapshot_sha TEXT, path TEXT, qualname TEXT,
            name TEXT, start_line INT, end_line INT, params TEXT);
        CREATE TABLE chunks (chunk_id TEXT, snapshot_sha TEXT, path TEXT,
            start_line INT, end_line INT, text TEXT);
        CREATE TABLE imports (snapshot_sha TEXT, path TEXT, module TEXT,
            names_json TEXT, resolved TEXT);
        CREATE TABLE edges (snapshot_sha TEXT, kind TEXT, label TEXT,
            from_ref TEXT, to_ref TEXT, detail_json TEXT);
    """)
    sha = "test"
    con.execute("INSERT INTO files VALUES (?, 's.py', 'h')", (sha,))
    con.execute("INSERT INTO routes VALUES (?, 'post', '/seed', 'root',"
                " 's.py', 1, 10)", (sha,))
    syms = [("root", 1, 10), ("a", 20, 30), ("b", 40, 50), ("c", 60, 70),
            ("d", 80, 90), ("e", 100, 110)]
    for name, s, e in syms:
        con.execute("INSERT INTO symbols VALUES (?, 's.py', ?, ?, ?, ?, '')",
                    (sha, name, name, s, e))
        con.execute("INSERT INTO chunks VALUES (?, ?, 's.py', ?, ?, ?)",
                    (f"c-{name}", sha, s, e, f"def {name}():\n    pass"))
    for i in range(10):
        con.execute("INSERT INTO edges VALUES (?, 'call', 'likely', 'root', ?, ?)",
                    (sha, f"fan{i}",
                     json.dumps({"from_file": "s.py", "from_line": 6})))
    chain = [("root", "a", 5), ("a", "b", 25), ("b", "c", 45),
             ("c", "d", 65), ("d", "e", 85)]
    for src, dst, line in chain:
        con.execute("INSERT INTO edges VALUES (?, 'call', 'likely', ?, ?, ?)",
                    (sha, src, dst, json.dumps({"from_file": "s.py",
                                                "from_line": line})))
    con.commit()
    con.close()


def test_caps_respected_on_fixture(tmp_path):
    db = tmp_path / "mini.sqlite"
    _mini_db(db)
    seed = {"symbol": "root", "file": "s.py", "start": 1, "end": 10,
            "hop": "route", "hop_detail": "POST /seed",
            "evidence": [{"chunk_id": "c-root", "path": "s.py", "lines": "1-10"}]}
    steps, _drops = T.traverse(db, "test", seed)
    # Fan: root's chain edge (line 5) sorts before the 10 fan edges (line 6);
    # at most MAX_FAN children survive: a + 7 fans.
    root_kids = [s for s in steps if s["n"] in (1, 2, 3, 4, 5, 6, 7, 8)]
    assert len(root_kids) <= T.MAX_FAN
    # Depth: chain root->a->b->c stops at depth 3 (no d, no e).
    syms = {s["symbol"] for s in steps}
    assert {"root", "a", "b", "c"} <= syms
    assert "d" not in syms and "e" not in syms


def test_evidence_rule_drops_and_logs(tmp_path):
    db = tmp_path / "mini.sqlite"
    _mini_db(db)
    con = sqlite3.connect(str(db))
    # Edge pointing at a line covered by no chunk: dropped with a reason.
    con.execute("INSERT INTO edges VALUES ('test', 'call', 'likely', 'b',"
                " 'ghost', ?)",
                (json.dumps({"from_file": "s.py", "from_line": 999}),))
    con.commit()
    con.close()
    seed = {"symbol": "b", "file": "s.py", "start": 40, "end": 50,
            "hop": "route", "hop_detail": "x",
            "evidence": [{"chunk_id": "c-b", "path": "s.py", "lines": "40-50"}]}
    steps, drops = T.traverse(db, "test", seed)
    assert all(s["symbol"] != "ghost" for s in steps)
    assert any(d["callee"] == "ghost" and d["reason"] == "no evidence chunk"
               for d in drops)


def test_label_rule_resolved_vs_likely(tmp_path):
    db = tmp_path / "mini.sqlite"
    _mini_db(db)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO imports VALUES ('test', 's.py', 'm', ?, 't.py')",
                (json.dumps([{"name": "a", "alias": None}]),))
    con.execute("INSERT INTO files VALUES ('test', 't.py', 'h')")
    con.execute("INSERT INTO symbols VALUES ('test', 't.py', 'a', 'a',"
                " 1, 5, '')")
    con.execute("INSERT INTO chunks VALUES ('c-a2', 'test', 't.py', 1, 5,"
                " 'def a(): pass')")
    con.commit()
    con.close()
    seed = {"symbol": "root", "file": "s.py", "start": 1, "end": 10,
            "hop": "route", "hop_detail": "x",
            "evidence": [{"chunk_id": "c-root", "path": "s.py", "lines": "1-10"}]}
    # Fake the call site line so attr matching is skipped; bare `a` resolves.
    steps, _ = T.traverse(db, "test", seed)
    by_sym = {s["symbol"]: s for s in steps}
    assert by_sym["a"]["hop"] == "calls"  # import-resolved: stated as fact
    assert "likely" not in by_sym["a"]["hop"]
    fan_likely = [s for s in steps if s["hop"] == "likely calls, by name"]
    assert fan_likely  # unresolved fan stays honestly labelled


def test_determinism_on_real_index():
    seed = {"symbol": "register_user",
            "file": "backend/app/api/routes/users.py", "start": 147, "end": 159,
            "hop": "route", "hop_detail": "POST /signup",
            "evidence": [{"chunk_id": "x", "path": "backend/app/api/routes/users.py",
                          "lines": "147-159"}]}
    first, _ = T.traverse(DB, SHA, seed)
    second, _ = T.traverse(DB, SHA, seed)
    assert [(s["symbol"], s["file"], s["hop"]) for s in first] == \
           [(s["symbol"], s["file"], s["hop"]) for s in second]


def test_golden_signup_first_step():
    golden = json.loads(
        (Path(__file__).parent / "golden" / "tour_signup.json").read_text(
            encoding="utf-8"))
    definition = T.load_definition(Path("evals/tours/signup.yaml"))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        seed = T.find_seed(con, SHA, definition)
    finally:
        con.close()
    assert seed["symbol"] == golden["seed"]["handler"] == "register_user"
    assert (seed["file"], seed["start"], seed["end"]) == (
        "backend/app/api/routes/users.py", 147, 159)
    steps, _drops = T.traverse(DB, SHA, seed)
    assert steps[0]["symbol"] == "register_user"
    assert len(steps) >= 3
    assert all(s["evidence"] for s in steps)
    assert {s["symbol"] for s in steps} >= set(golden["must_include_symbols"])


def test_sequence_diagram_checks():
    tour = {"steps": [
        {"file": "a/x.py", "title": "Enter at `root`", "hop": "route",
         "hop_detail": "POST /seed"},
        {"file": "a/y.py", "title": "calls `mid`", "hop": "calls",
         "hop_detail": "mid"}]}
    text = T.sequence_mermaid(tour)
    assert text.startswith("sequenceDiagram\n")
    assert T.check_sequence(text) == []
    assert T.check_sequence("flowchart LR\n    N1-->N2") != []


def test_tours_endpoints_serve_cached_tour():
    import shutil
    from fastapi.testclient import TestClient
    from mentor.api import app as APP
    from mentor.api import routes as R
    R.REGISTRY.clear()
    src = Path("data/indexes/fst.sqlite")
    db = Path("data/cache/tour_ep_test.sqlite")
    db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, db)
    R.REGISTRY["e"] = {"id": "e", "path": str(Path("data/repos/fst").resolve()),
                       "sha": SHA, "index": str(db)}
    definition = T.load_definition(Path("evals/tours/signup.yaml"))
    tour = T.build(db, SHA, definition)
    cache_path = Path("data/cache/tour_e_signup.json")
    try:
        T.save(cache_path, tour)
        client = TestClient(APP.create_app())
        listing = client.get("/api/repos/e/tours").json()
        assert {t["name"] for t in listing} >= {"signup", "login", "crud"}
        body = client.get("/api/repos/e/tours/signup").json()
        assert body["name"] == "signup" and len(body["steps"]) >= 3
        assert body["sequence"].startswith("sequenceDiagram")
        assert body["stale"] is False
        assert client.get("/api/repos/e/tours/nope").status_code == 404
    finally:
        R.REGISTRY.clear()
        cache_path.unlink(missing_ok=True)
        db.unlink(missing_ok=True)

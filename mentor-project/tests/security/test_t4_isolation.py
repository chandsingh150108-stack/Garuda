"""T4: cross-repository leakage via caches or indexes. Boundary: storage.

Controls: one SQLite file per repository; cache keys bind repo_id + SHA +
schema version. Tests: a term unique to repo B never surfaces from repo A's
index, and identical questions on A/B produce different cache keys.
"""
from mentor.answer import cache as CA
from mentor.retrieve import search as S
from tests.test_freshness import build_fixture


def test_query_against_a_never_returns_chunks_from_b(tmp_path):
    fa = build_fixture(tmp_path / "a")
    fb = build_fixture(tmp_path / "b")
    (fb["repo"] / "pkg" / "zebra_module.py").write_text(
        "ZEBRA_UNIQUE_TOKEN = 1\n", encoding="utf-8")
    from mentor.ingest import manifest as M
    from mentor.index import store as ST
    from mentor.parse import parse_worker as W
    manifest = M.build_manifest(fb["repo"], fb["sha"])
    rels = ["pkg/zebra_module.py"]
    files = W.parse_many(fb["repo"], rels, timeout_s=10.0)
    parses = {"sha": fb["sha"], "files": files, "routes": [], "models": [],
              "config": {}}
    import json
    mp = tmp_path / "mb.json"
    pp = tmp_path / "pb.json"
    mp.write_text(json.dumps({"sha": fb["sha"], "count": 1,
                              "files": [e for e in manifest["files"]
                                        if e["path"] in rels]}),
                  encoding="utf-8")
    pp.write_text(json.dumps(parses), encoding="utf-8")
    ST.build(fb["repo"], mp, pp, tmp_path / "b2.sqlite", repo_id="fresh")
    res = S.search(fa["index"], fa["sha"], "ZEBRA_UNIQUE_TOKEN", k=10)
    assert all(h["path"].startswith("pkg/") for h in res["hits"])
    assert "zebra_module.py" not in {h["path"] for h in res["hits"]}


def test_cache_keys_bind_repo_and_sha(tmp_path):
    fa = build_fixture(tmp_path / "a")
    fb = build_fixture(tmp_path / "b")
    ka = CA.make_key("a", fa["sha"], "same question", "llamacpp", "m", "p9", 10)
    kb = CA.make_key("b", fb["sha"], "same question", "llamacpp", "m", "p9", 10)
    assert ka != kb
    assert CA.lookup(fa["index"], kb) is None

"""Demo gate check (spec Phase 21).

Verifies, without launching a browser or needing a model server, that every
fixed-sequence step returns its expected KIND of response through the
in-process API: server boots, index matches the pinned SHA, cache present,
status/arch/ask-cached/tours/tasks/code all 200 with contract shapes, the
impossible question abstains (script adapter stands in for the model on
that step only — live abstention is covered by rehearsals/e2e), and the
stale predicate fires on edited lines.

Usage: python scripts/demo_check.py [--index ...] [--cache ...]
Exit 0 only when every step passes; prints per-step PASS/FAIL + timings.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from mentor import demo as D  # noqa: E402
from mentor.api import app as APP  # noqa: E402
from mentor.api import routes as R  # noqa: E402
from mentor.index import freshness as FR  # noqa: E402


class AbstainAdapter:
    def complete(self, messages, schema, options, timeout_s):
        return '{"status": "abstain", "segments": [], "missing": ["no billing code"]}'


CHECKS: list[str] = []


def check(name: str):
    def wrap(fn):
        CHECKS.append(name)
        fn.check_name = name
        return fn
    return wrap


@check("verify index + cache (blocks a broken demo)")
def c_verify(args, client):
    res = D.verify(Path(args.index), args.sha, Path(args.cache))
    assert res["ok"], res["notes"]
    return f"index+cache ok"


@check("status current at pinned SHA")
def c_status(args, client):
    body = client.get(f"/api/repos/{args.repo_id}/status").json()
    assert body["sha"] == args.sha, body["sha"]
    assert body["dirty"] is False, body["dirty_files"]
    return f"files={body['files']} chunks={body['chunks']}"


@check("architecture >=6 components")
def c_arch(args, client):
    body = client.get(f"/api/repos/{args.repo_id}/architecture").json()
    assert len(body["nodes"]) >= 6, len(body["nodes"])
    assert body["mermaid"].strip()
    return f"nodes={len(body['nodes'])} edges={len(body['edges'])}"


@check("signup answer cached with chips + provider")
def c_ask(args, client):
    body = client.post(f"/api/repos/{args.repo_id}/ask",
                       json={"question": "How does user registration "
                                        "(`register_user`) work?",
                             "k": 10}).json()
    assert body["status"] == "answer" and body["cached"] is True
    assert body["evidence"] and body["segments"][0]["evidence_ids"]
    return f"segments={len(body['segments'])} evidence={len(body['evidence'])}"


@check("signup tour has validated steps")
def c_tour(args, client):
    body = client.get(f"/api/repos/{args.repo_id}/tours/signup").json()
    assert len(body["steps"]) >= 3 and not body["stale"]
    return f"steps={len(body['steps'])}"


@check("citation opens exact lines at SHA")
def c_code(args, client):
    ev = client.post(f"/api/repos/{args.repo_id}/ask",
                     json={"question": "How does user registration "
                                      "(`register_user`) work?",
                           "k": 10}).json()["evidence"][0]
    start, end = ev["lines"].split("-", 1)
    r = client.get(f"/api/repos/{args.repo_id}/code",
                   params={"path": ev["path"], "start": start, "end": end})
    assert r.status_code == 200
    assert r.json()["sha"] == args.sha
    return f"{ev['path']}:{ev['lines']}"


@check("impossible question abstains (script adapter)")
def c_abstain(args, client):
    old = R.adapter_factory
    R.adapter_factory = lambda: AbstainAdapter()
    try:
        body = client.post(f"/api/repos/{args.repo_id}/ask",
                           json={"question": "How does billing work?",
                                 "k": 10}).json()
    finally:
        R.adapter_factory = old
    assert body["status"] == "abstain" and body["missing"]
    return f"missing={len(body['missing'])}"


@check("starter tasks >=5 validated")
def c_tasks(args, client):
    body = client.get(f"/api/repos/{args.repo_id}/tasks?limit=10").json()
    assert len(body["tasks"]) >= 5
    return f"tasks={len(body['tasks'])}"


@check("stale predicate fires on edited lines")
def c_stale(args, client):
    assert FR.content_stale(Path(args.index), args.sha, "pkg/a.py",
                            "999-1005", "whatever") is True
    return "fail-visible ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo gate check.")
    parser.add_argument("--index", default="data/indexes/fst.sqlite")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--repo-id", default="fst")
    parser.add_argument("--sha",
                        default="7257e606cb94eada1dca40173e2b7f99dd549bc6")
    parser.add_argument("--cache", default="data/demo_cache")
    args = parser.parse_args(argv)
    R.REGISTRY.clear()
    R.REGISTRY[args.repo_id] = {"id": args.repo_id,
                                "path": str(Path(args.repo).resolve()),
                                "sha": args.sha, "index": args.index}
    client = TestClient(APP.create_app())
    # Order matters: module-level CHECKS preserves definition order.
    fns = [c_verify, c_status, c_arch, c_ask, c_tour, c_code, c_abstain,
           c_tasks, c_stale]
    failed = 0
    total_t = 0.0
    for fn in fns:
        t0 = time.perf_counter()
        try:
            detail = fn(args, client)
            dt = time.perf_counter() - t0
            print(f"PASS {fn.check_name} ({dt:.2f}s) — {detail}")
        except Exception as exc:
            dt = time.perf_counter() - t0
            print(f"FAIL {fn.check_name} ({dt:.2f}s) — {exc}")
            failed += 1
        total_t += dt
    R.REGISTRY.clear()
    print(f"demo_check: {len(fns) - failed}/{len(fns)} in {total_t:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

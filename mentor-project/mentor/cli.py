"""`mentor` command-line entry point (spec Phase 4: `mentor index ...`).

Run as `python -m mentor.cli index --repo data/repos/fst --sha <SHA>
--out data/indexes/fst.sqlite`. Later phases add `search`, `ask`, `serve`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED_SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


def cmd_index(args) -> int:
    from mentor.index import store as store
    stats = store.build(Path(args.repo), Path(args.manifest), Path(args.parses),
                        Path(args.out), repo_id=args.repo_id, timeout_s=args.timeout)
    counts = store.table_counts(Path(args.out))
    print(f"files={stats['files']} chunks={stats['chunks']} symbols={stats['symbols']} "
          f"failed={stats['failed']}")
    print("counts:", " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"wrote {args.out}")
    return 0


def cmd_search(args) -> int:
    from mentor.retrieve import search as search
    res = search.search(Path(args.index), args.sha, args.query, k=args.k)
    for i, hit in enumerate(res["hits"], start=1):
        print(f"{i}. [{hit['chunk_id']}] {hit['path']}:{hit['start_line']}-{hit['end_line']}"
              f" score={hit['score']:.4f} via={','.join(hit['retrievers'])}")
        print(f"   {hit['header'][:120]}")
    conf = res["confidence"]
    print(f"confidence: top_score={conf['top_score']:.4f} "
          f"coverage={conf['identifier_coverage']:.2f} "
          f"agreement={conf['two_retriever_agreement']}")
    return 0


def cmd_eval_retrieval(args) -> int:
    import json
    from mentor.eval import gold as gold_mod
    from mentor.eval import harness as harness
    gold = gold_mod.load(Path(args.gold))
    problems = gold_mod.validate(gold, Path("data/repos/fst"))
    if problems:
        print("GOLD INVALID:")
        for p in problems:
            print(f"  {p}")
        return 1
    res = harness.run(gold, Path(args.index), args.sha, args.baseline)
    print(f"baseline={res['baseline']} n={res['n']}")
    for key, val in res["summary"].items():
        print(f"  {key}: mean={val['mean']} full_rate={val['full_rate']}"
              f" ci95={val['full_rate_ci95']} n={val['n']}")
    print(json.dumps(res["summary"]))
    return 0


def cmd_ask(args) -> int:
    from mentor.answer import qa as QA
    out = QA.ask(Path(args.index), args.sha, args.query, k=args.k,
                 timeout_s=args.timeout)
    print(f"status={out['status']} repairs={out['repairs']} "
          f"model={out['model']} prompt={out['prompt_version']}")
    for seg in out["segments"]:
        print(f"- [{seg['kind']}] {seg['text']}")
        for eid in seg["evidence_ids"]:
            print(f"    [{eid}]")
    if out["status"] == "abstain":
        print("missing:")
        for m in out["missing"]:
            print(f"  - {m}")
        for c in out.get("closest", []):
            print(f"  closest: {c['path']}:{c['lines']}")
    else:
        for e in out.get("evidence", []):
            print(f"  evidence: [{e['id']}] {e['path']}:{e['lines']}")
    return 0


def cmd_eval_answers(args) -> int:
    import json
    import random
    from mentor.answer import qa as QA
    from mentor.eval import gold as gold_mod
    from mentor.eval import stats as ST
    gold = gold_mod.load(Path(args.gold))
    problems = gold_mod.validate(gold, Path("data/repos/fst"))
    if problems:
        print("GOLD INVALID:")
        for p in problems:
            print(f"  {p}")
        return 1
    ids = [i.id for i in gold.items]
    random.Random(args.seed).shuffle(ids)
    half = len(ids) // 2
    want = set(ids[:half] if args.split == "dev" else ids[half:])
    items = [i for i in gold.items if i.id in want]
    rows = []
    for item in items:
        out = QA.ask(Path(args.index), args.sha, item.question, k=args.k,
                     timeout_s=args.timeout)
        rows.append({"id": item.id, "expected": item.expected_status,
                     "got": out["status"], "repairs": out["repairs"]})
        print(f"{item.id}: expected={item.expected_status} got={out['status']}")
    ans = [r for r in rows if r["expected"] == "answer"]
    abs_ = [r for r in rows if r["expected"] == "abstain"]
    fa = sum(1 for r in abs_ if r["got"] == "answer")
    fab = sum(1 for r in ans if r["got"] == "abstain")
    summary = {
        "split": args.split, "seed": args.seed, "n": len(rows),
        "false_answer": {"n": fa, "of": len(abs_),
                         "rate": round(fa / len(abs_), 3) if abs_ else 0.0,
                         "ci95": list(ST.wilson(fa / len(abs_), len(abs_)))
                         if abs_ else [0.0, 1.0]},
        "false_abstain": {"n": fab, "of": len(ans),
                          "rate": round(fab / len(ans), 3) if ans else 0.0,
                          "ci95": list(ST.wilson(fab / len(ans), len(ans)))
                          if ans else [0.0, 1.0]},
    }
    print(json.dumps(summary))
    if args.out:
        Path(args.out).write_text(json.dumps({"rows": rows,
                                              "summary": summary}, indent=1),
                                  encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn
    from mentor.api import app as APP
    from mentor.api import routes as R
    APP.resolve_bind(args.host, args.unsafe_bind)
    R.REGISTRY["fst"] = {"id": "fst", "path": str(Path(args.repo).resolve()),
                         "sha": args.sha, "index": args.index}
    print(f"serving fst@{args.sha[:12]} on http://{args.host}:{args.port} "
          f"(index {args.index})")
    uvicorn.run(APP.create_app(), host=args.host, port=args.port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mentor", description="Codebase Mentor")
    sub = parser.add_subparsers(dest="command", required=True)
    idx = sub.add_parser("index", help="Build a SQLite index for a pinned repo")
    idx.add_argument("--repo", default="data/repos/fst")
    idx.add_argument("--sha", default=PINNED_SHA)
    idx.add_argument("--manifest", default=None)
    idx.add_argument("--parses", default=None)
    idx.add_argument("--out", default="data/indexes/fst.sqlite")
    idx.add_argument("--repo-id", default="fst")
    idx.add_argument("--timeout", type=float, default=10.0)
    sea = sub.add_parser("search", help="Fused retrieval over an index")
    sea.add_argument("query")
    sea.add_argument("--k", type=int, default=10)
    sea.add_argument("--index", default="data/indexes/fst.sqlite")
    sea.add_argument("--sha", default=PINNED_SHA)
    evl = sub.add_parser("eval", help="Run evaluation harnesses")
    evl.add_argument("what", choices=["retrieval", "answers"])
    evl.add_argument("--gold", default="evals/gold/v1.yaml")
    evl.add_argument("--index", default="data/indexes/fst.sqlite")
    evl.add_argument("--baseline", default="B3", choices=["B1", "B3"])
    evl.add_argument("--sha", default=PINNED_SHA)
    evl.add_argument("--split", default="test", choices=["dev", "test"])
    evl.add_argument("--seed", type=int, default=7)
    evl.add_argument("--k", type=int, default=10)
    evl.add_argument("--timeout", type=float, default=120.0)
    evl.add_argument("--out", default=None)
    ask = sub.add_parser("ask", help="Grounded answer with evidence citations")
    ask.add_argument("query")
    ask.add_argument("--k", type=int, default=10)
    ask.add_argument("--index", default="data/indexes/fst.sqlite")
    ask.add_argument("--sha", default=PINNED_SHA)
    ask.add_argument("--timeout", type=float, default=120.0)
    srv = sub.add_parser("serve", help="Serve the loopback QA API")
    srv.add_argument("--index", default="data/indexes/fst.sqlite")
    srv.add_argument("--repo", default="data/repos/fst")
    srv.add_argument("--sha", default=PINNED_SHA)
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--unsafe-bind", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "index":
        if args.manifest is None:
            args.manifest = f"data/manifests/{args.sha}.json"
        if args.parses is None:
            args.parses = f"data/parses/{args.sha}.json"
        return cmd_index(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "eval" and args.what == "retrieval":
        return cmd_eval_retrieval(args)
    if args.command == "eval" and args.what == "answers":
        return cmd_eval_answers(args)
    if args.command == "ask":
        return cmd_ask(args)
    if args.command == "serve":
        return cmd_serve(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

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
                 timeout_s=args.timeout, why=args.why,
                 repo_path=Path(args.repo) if args.why else None)
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
    if getattr(args, "category", None):
        # Category runs (e.g. the four why questions) span the frozen split.
        items = [i for i in gold.items if i.category == args.category]
    rows = []
    for item in items:
        out = QA.ask(Path(args.index), args.sha, item.question, k=args.k,
                     timeout_s=args.timeout, why=args.why,
                     repo_path=Path("data/repos/fst") if args.why else None)
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
    from mentor import config as CFG
    from mentor.api import app as APP
    from mentor.api import routes as R
    APP.resolve_bind(args.host, args.unsafe_bind)
    R.REGISTRY["fst"] = {"id": "fst", "path": str(Path(args.repo).resolve()),
                         "sha": args.sha, "index": args.index}
    print(f"serving fst@{args.sha[:12]} on http://{args.host}:{args.port} "
          f"(index {args.index})")
    print(CFG.mode_banner())
    uvicorn.run(APP.create_app(), host=args.host, port=args.port, log_level="info")
    return 0


def cmd_arch(args) -> int:
    import json
    from mentor.features import arch as A
    from mentor.features import mermaid as M
    model = A.extract(Path(args.index), args.sha)
    if args.format == "json":
        text = json.dumps(model, indent=1, sort_keys=True)
    else:
        text = M.render(model)
        problems = M.check(text)
        if problems:
            print(f"MERMAID CHECK FAILED: {problems}")
            return 1
    out = Path(args.out) if args.out else (
        Path("data/cache") / f"arch_{Path(args.index).stem}.mmd")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"nodes={len(model['nodes'])} edges={len(model['edges'])}")
    print(f"wrote {out}")
    return 0


def cmd_tours(args) -> int:
    import json
    from mentor.features import tours as T
    out_dir = Path(args.out)
    if args.action == "show":
        tour = T.load(out_dir / f"tour_fst_{args.name}.json")
        print(f"{tour['name']}: {tour['question']}")
        for s in tour["steps"]:
            print(f"  [{s['n']}] {s['hop']}: {s['title']}")
            print(f"      {s['file']}:{s['start']}-{s['end']} ({s['narrated_by']})")
        return 0
    adapter = None
    if args.narrate:
        from mentor.answer import qa as QA
        adapter = QA.default_adapter()
    names = 0
    for path in sorted(Path(args.tours).glob("*.yaml")):
        definition = T.load_definition(path)
        if args.name and definition["name"] != args.name:
            continue
        tour = T.build(Path(args.index), args.sha, definition, adapter)
        problems = T.check_sequence(tour["sequence"])
        if problems:
            print(f"{definition['name']}: SEQUENCE CHECK FAILED {problems}")
            return 1
        if len(tour["steps"]) < 3:
            print(f"{definition['name']}: only {len(tour['steps'])} steps "
                  f"(need >=3); drops={tour['drops']}")
            return 1
        T.save(out_dir / f"tour_fst_{definition['name']}.json", tour)
        llm = sum(1 for s in tour["steps"] if s["narrated_by"] == "llm")
        print(f"{definition['name']}: steps={len(tour['steps'])} "
              f"drops={len(tour['drops'])} narrated_llm={llm}")
        names += 1
    if not names:
        print("no tour definitions matched")
        return 1
    return 0


def cmd_tasks(args) -> int:
    from mentor.features import tasks as TS
    if args.bandit_scan:
        stored = TS.store_bandit_scan(Path(args.index), Path(args.repo),
                                      args.sha)
        print(f"bandit findings stored: {stored}")
    tasks = TS.rank(TS.link_tours(
        TS.collect(Path(args.index), args.sha,
                   gh_repo=args.gh_repo), Path(args.tours),
        Path(args.cache)), args.limit)
    problems = TS.validate(Path(args.index), args.sha, tasks, Path(args.tours))
    if problems:
        print("TASK VALIDATION FAILED:")
        for p in problems:
            print(f"  {p}")
        return 1
    for t in tasks:
        flag = " [HIGH RISK]" if t["high_risk"] else ""
        print(f"d={t['difficulty']:.2f} r={t['risk']}{flag} [{t['kind']}] {t['title']}")
        print(f"    {t['file']}:{t['start']}-{t['end']} tours={t['tours']} "
              f"prereq={t['prerequisites']}")
    return 0


def cmd_reindex(args) -> int:
    """Refresh only changed rows (spec Phase 17, D17.4).

    Rollback for any freshness failure is a full `mentor index` rebuild
    from scratch (recorded, never silent).
    """
    import json
    from mentor.index import freshness as FR
    stats = FR.reindex(Path(args.repo), Path(args.index),
                       Path(args.manifest), Path(args.parses),
                       args.sha, timeout_s=args.timeout)
    print(f"added={len(stats['added'])} modified={len(stats['modified'])} "
          f"deleted={len(stats['deleted'])} renamed={len(stats['renamed'])} "
          f"dirty={stats['dirty']} elapsed={stats['elapsed_s']}s")
    for rel in stats["added"]:
        print(f"  A {rel}")
    for rel in stats["modified"]:
        print(f"  M {rel}")
    for rel in stats["deleted"]:
        print(f"  D {rel}")
    for src, dst in stats["renamed"]:
        print(f"  R {src} -> {dst}")
    if stats["failed"]:
        print("FAILED:")
        for f in stats["failed"]:
            print(f"  {f}")
    affected = FR.tours_affected(Path(args.cache), stats["added"] + stats["modified"]
                                 + stats["deleted"])
    if affected:
        print(f"stale tours (regen lazily with `mentor tours precompute`): "
              f"{', '.join(affected)}")
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    print(f"manifest entries={manifest['count']} "
          f"index files={stats['files']} chunks={stats['chunks']}")
    return 0


def cmd_precompute(args) -> int:
    """Warm the demo cache with local inference (spec Phase 19, D19.3)."""
    from mentor.answer import qa as QA
    from mentor.features import precompute as PC
    adapter = QA.default_adapter()
    summary = PC.run(Path(args.index), args.sha, args.repo_id,
                     Path(args.out), tours_dir=Path(args.tours),
                     adapter=adapter, limit=args.limit,
                     polish_tasks=args.polish_tasks)
    print(f"arch nodes={summary['arch']['nodes']} "
          f"edges={summary['arch']['edges']}")
    print(f"tours={summary['tours']}")
    print(f"tasks={summary['tasks']} "
          f"polished={summary.get('tasks_polished', 0)}")
    print(f"cached answers={summary['questions']} "
          f"abstained={summary['abstained']}")
    if args.install:
        copied = PC.install(Path(args.out), args.repo_id, Path(args.cache))
        print(f"installed into {args.cache}: {', '.join(copied)}")
    print(f"wrote {args.out}/precompute_manifest.json")
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
    evl.add_argument("--category", default=None,
                     help="filter gold items (e.g. why)")
    evl.add_argument("--why", action="store_true",
                     help="attach history blocks (needs live repo)")
    evl.add_argument("--k", type=int, default=10)
    evl.add_argument("--timeout", type=float, default=120.0)
    evl.add_argument("--out", default=None)
    ask = sub.add_parser("ask", help="Grounded answer with evidence citations")
    ask.add_argument("query")
    ask.add_argument("--k", type=int, default=10)
    ask.add_argument("--index", default="data/indexes/fst.sqlite")
    ask.add_argument("--sha", default=PINNED_SHA)
    ask.add_argument("--timeout", type=float, default=120.0)
    ask.add_argument("--why", action="store_true")
    ask.add_argument("--repo", default="data/repos/fst")
    srv = sub.add_parser("serve", help="Serve the loopback QA API")
    srv.add_argument("--index", default="data/indexes/fst.sqlite")
    srv.add_argument("--repo", default="data/repos/fst")
    srv.add_argument("--sha", default=PINNED_SHA)
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--unsafe-bind", action="store_true")
    arc = sub.add_parser("arch", help="Deterministic architecture overview")
    arc.add_argument("--index", default="data/indexes/fst.sqlite")
    arc.add_argument("--sha", default=PINNED_SHA)
    arc.add_argument("--out", default=None,
                     help="default: data/cache/arch_<index stem>.mmd")
    arc.add_argument("--format", default="mmd", choices=["mmd", "json"])
    trs = sub.add_parser("tours", help="Precomputed guided tours")
    trs.add_argument("action", choices=["precompute", "show"])
    trs.add_argument("--index", default="data/indexes/fst.sqlite")
    trs.add_argument("--sha", default=PINNED_SHA)
    trs.add_argument("--tours", default="evals/tours")
    trs.add_argument("--name", default=None)
    trs.add_argument("--out", default="data/cache")
    trs.add_argument("--narrate", action="store_true",
                     help="ask the model for titles/explanations (needs server)")
    tsk = sub.add_parser("tasks", help="Starter tasks for newcomers")
    tsk.add_argument("--index", default="data/indexes/fst.sqlite")
    tsk.add_argument("--sha", default=PINNED_SHA)
    tsk.add_argument("--repo", default="data/repos/fst")
    tsk.add_argument("--tours", default="evals/tours")
    tsk.add_argument("--cache", default="data/cache")
    tsk.add_argument("--limit", type=int, default=10)
    tsk.add_argument("--bandit-scan", action="store_true",
                     help="run Bandit over --repo and store findings in "
                     "the index before listing")
    tsk.add_argument("--gh-repo", default=None,
                     help="fetch good-first-issue/help-wanted items for "
                     "OWNER/REPO (needs ALLOW_GH_TASKS=true, never offline)")
    rdx = sub.add_parser("reindex", help="Refresh only changed index rows")
    rdx.add_argument("--repo", default="data/repos/fst")
    rdx.add_argument("--index", default="data/indexes/fst.sqlite")
    rdx.add_argument("--manifest", default=None)
    rdx.add_argument("--parses", default=None)
    rdx.add_argument("--sha", default=PINNED_SHA)
    rdx.add_argument("--cache", default="data/cache")
    rdx.add_argument("--timeout", type=float, default=10.0)
    pre = sub.add_parser("precompute", help="Warm the demo cache (local only)")
    pre.add_argument("--index", default="data/indexes/fst.sqlite")
    pre.add_argument("--sha", default=PINNED_SHA)
    pre.add_argument("--repo", default="data/repos/fst")
    pre.add_argument("--repo-id", default="fst")
    pre.add_argument("--out", default="data/demo_cache")
    pre.add_argument("--tours", default="evals/tours")
    pre.add_argument("--cache", default="data/cache")
    pre.add_argument("--limit", type=int, default=10)
    pre.add_argument("--install", action="store_true",
                     help="copy tour JSONs into the serving cache dir")
    pre.add_argument("--polish-tasks", action="store_true",
                     help="polish task blurbs with local inference "
                     "(needs ALLOW_TASK_POLISH=true; deterministic fallback)")
    dem = sub.add_parser("demo", help="Verify + open + serve the demo")
    dem.add_argument("--index", default="data/indexes/fst.sqlite")
    dem.add_argument("--repo", default="data/repos/fst")
    dem.add_argument("--sha", default=PINNED_SHA)
    dem.add_argument("--repo-id", default="fst")
    dem.add_argument("--cache", default="data/demo_cache")
    dem.add_argument("--host", default="127.0.0.1")
    dem.add_argument("--port", type=int, default=8000)
    dem.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "index":
        if args.manifest is None:
            args.manifest = f"data/manifests/{args.sha}.json"
        if args.parses is None:
            args.parses = f"data/parses/{args.sha}.json"
        return cmd_index(args)
    if args.command == "reindex":
        if args.manifest is None:
            args.manifest = f"data/manifests/{args.sha}.json"
        if args.parses is None:
            args.parses = f"data/parses/{args.sha}.json"
        return cmd_reindex(args)
    if args.command == "precompute":
        return cmd_precompute(args)
    if args.command == "demo":
        from mentor import demo as D
        return D.run(Path(args.index), Path(args.repo), args.sha,
                     args.repo_id, Path(args.cache), args.host, args.port,
                     args.no_browser)
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
    if args.command == "arch":
        return cmd_arch(args)
    if args.command == "tours":
        return cmd_tours(args)
    if args.command == "tasks":
        return cmd_tasks(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

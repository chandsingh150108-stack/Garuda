"""Demo precompute (spec Phase 19, D19.3).

Generates validated artifacts with local inference into `--out`
(`data/demo_cache/`, git-ignored runtime, shipped as a separate archive —
never committed): architecture diagram, narrated tours, ranked tasks, and
validated answers to the ten demonstration questions. Answers are ALSO
warmed into the index answer-cache under the exact key the serve path
computes, so demo questions hit cache with the `cached` label and need no
model at showtime. `--install` copies the JSON artifacts into the serving
cache dir (`data/cache`) for the file-backed endpoints.
"""
from __future__ import annotations

import json
from pathlib import Path

# Ten demonstration questions (all answerable gold items: 4 where/how,
# 3 arch, 3 flow — signup/login/crud/arch coverage). Abstention is demoed
# live with q25 (billing), which is never cached by design.
DEMO_QUESTIONS: list[tuple[str, str, int]] = [
    ("q01", "How does user registration (`register_user`) work?", 10),
    ("q03", "How is password hashing configured and done?", 10),
    ("q04", "How does login issue access tokens?", 10),
    ("q05", "How are items created (`create_item`)?", 10),
    ("q09", "How is the FastAPI application assembled from routers?", 10),
    ("q10", "What database models exist and what tables do they use?", 10),
    ("q12", "What frontend pages exist and how is the signup page built?", 10),
    ("q15", "Walk through user signup end to end.", 10),
    ("q16", "Walk through login end to end.", 10),
    ("q17", "Walk through creating an item.", 10),
]


def run(index: Path, sha: str, repo_id: str, out_dir: Path,
        tours_dir: Path = Path("evals/tours"),
        adapter=None, questions: list[tuple[str, str, int]] | None = None,
        limit: int = 10, polish_tasks: bool = False) -> dict:
    """Build every artifact. Returns a summary (also written as manifest)."""
    from mentor.answer import cache as CA
    from mentor.answer import prompts as P
    from mentor.answer import qa as QA
    from mentor.features import arch as A
    from mentor.features import mermaid as M
    from mentor.features import tasks as TS
    from mentor.features import tours as T
    from mentor import config as CFG

    out_dir.mkdir(parents=True, exist_ok=True)
    questions = DEMO_QUESTIONS if questions is None else questions
    summary: dict = {"sha": sha, "repo_id": repo_id,
                     "model": CFG.LLM_MODEL, "provider": CFG.LLM_PROVIDER,
                     "prompt_version": P.PROMPT_VERSION,
                     "questions": [], "tours": [], "abstained": []}
    model = A.extract(index, sha)
    mmd = M.render(model)
    problems = M.check(mmd)
    if problems:
        raise ValueError(f"mermaid check failed: {problems}")
    (out_dir / f"arch_{repo_id}.mmd").write_text(mmd, encoding="utf-8")
    (out_dir / f"arch_{repo_id}.json").write_text(
        json.dumps(model, indent=1, sort_keys=True), encoding="utf-8")
    summary["arch"] = {"nodes": len(model["nodes"]),
                       "edges": len(model["edges"])}
    for path in sorted(tours_dir.glob("*.yaml")):
        definition = T.load_definition(path)
        tour = T.build(index, sha, definition, adapter)
        problems = T.check_sequence(tour["sequence"])
        if problems:
            raise ValueError(f"{definition['name']}: bad sequence {problems}")
        if len(tour["steps"]) < 3:
            raise ValueError(f"{definition['name']}: only "
                             f"{len(tour['steps'])} steps")
        (out_dir / f"tour_{repo_id}_{definition['name']}.json").write_text(
            json.dumps(tour, indent=1, sort_keys=True), encoding="utf-8")
        summary["tours"].append(definition["name"])
    tasks = TS.rank(TS.link_tours(TS.collect(index, sha), tours_dir,
                                  out_dir), limit)
    problems = TS.validate(index, sha, tasks, tours_dir)
    if problems:
        raise ValueError(f"task validation failed: {problems}")
    polished = 0
    if polish_tasks and CFG.ALLOW_TASK_POLISH and adapter is not None:
        from mentor.features import task_polish as TP
        tasks = TP.polish_tasks(index, sha, tasks, adapter, limit)
        polished = sum(1 for t in tasks if "polished" in t)
    (out_dir / f"tasks_{repo_id}.json").write_text(
        json.dumps(tasks, indent=1), encoding="utf-8")
    summary["tasks"] = len(tasks)
    summary["tasks_polished"] = polished
    for qid, question, k in questions:
        res = QA.ask(index, sha, question, k=k, adapter=adapter)
        key = CA.make_key(repo_id, sha, question, CFG.LLM_PROVIDER,
                          CFG.LLM_MODEL, P.PROMPT_VERSION, k)
        if res["status"] == "answer":
            CA.store(index, key, repo_id, sha, res)
            summary["questions"].append(qid)
        else:
            summary["abstained"].append(qid)
        (out_dir / f"answer_{repo_id}_{qid}.json").write_text(
            json.dumps({"question": question, "response": res}, indent=1),
            encoding="utf-8")
    (out_dir / "precompute_manifest.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    return summary


def install(out_dir: Path, repo_id: str, cache_dir: Path) -> list[str]:
    """Copy file-backed artifacts into the serving cache dir."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(out_dir.glob(f"tour_{repo_id}_*.json")):
        dest = cache_dir / path.name
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(dest.name)
    tasks_file = out_dir / f"tasks_{repo_id}.json"
    if tasks_file.is_file():
        try:
            keep = any(isinstance(t, dict) and "polished" in t
                       for t in json.loads(tasks_file.read_text(
                           encoding="utf-8")))
        except (OSError, ValueError):
            keep = False
        if keep:
            dest = cache_dir / tasks_file.name
            dest.write_text(tasks_file.read_text(encoding="utf-8"),
                            encoding="utf-8")
            copied.append(dest.name)
    return copied

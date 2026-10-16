"""F12 contamination comparison + G3 file-precision measurement (Phase 22).

B6 (no-retrieval): the loopback model answers gold questions with NO
evidence; answers are graded by must_include keyword hit (content signal,
not citation validity — B6 cannot cite). Run on the original and the
counterfactual indexes' question sets; a B6 that knows the original but
fails the renamed copy flags memorization. Needs the model server up.

G3: mean file-level P@10 (CodeGrep definition) for B1/B3 over the 22
answerable gold items. Usage: python redteam/attacks/family12_g3.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mentor import config as CFG  # noqa: E402
from mentor.answer import prompts as P  # noqa: E402
from mentor.eval import baselines as B  # noqa: E402
from mentor.eval import gold as G  # noqa: E402
from mentor.eval import metrics as M  # noqa: E402
from mentor.eval import stats as ST  # noqa: E402
from mentor.llm import gateway as GW  # noqa: E402
from mentor.llm import llamacpp_adapter as LC  # noqa: E402

B6_QUESTIONS = ["q01", "q03", "q05", "q09", "q10", "q15"]


def g3_precision(gold_path: str, index: str, sha: str) -> dict:
    gold = G.load(Path(gold_path))
    items = G.answerable(gold)
    out = {}
    for baseline in ("B1", "B3"):
        vals = []
        for item in items:
            hits = B.run(baseline, Path(index), sha, item.question, k=10)
            files = [h["path"] for h in hits]
            rel = {g.path for g in item.gold}
            vals.append(M.file_precision_at_k(files, rel, 10))
        n = len(vals)
        out[baseline] = {"mean": round(statistics.fmean(vals), 3), "n": n,
                         "full_rate": 0.0}
    return out


def b6_sample(gold_path: str, ids: list[str], adapter) -> dict:
    gold = G.load(Path(gold_path))
    items = [i for i in G.answerable(gold) if i.id in ids]
    schema = {"type": "object",
              "properties": {"status": {"type": "string"},
                             "segments": {"type": "array"},
                             "missing": {"type": "array"}},
              "required": ["status", "segments"]}
    rows = []
    for item in items:
        messages = [{"role": "system",
                     "content": "Answer with JSON only. " + CFG.LLM_SYSTEM_SUFFIX},
                    {"role": "user",
                     "content": f"Question: {item.question}\n"
                                "Respond with the JSON answer object only."}]
        try:
            parsed = GW.generate(adapter, messages, schema,
                                 {"max_tokens": 512}, timeout_s=180.0)
            text = json.dumps(parsed).lower()
            hits = sum(1 for kw in (item.must_include or [])
                       if kw.lower() in text)
            rows.append({"id": item.id, "keywords_hit": hits,
                         "keywords_of": len(item.must_include or [])})
        except GW.GatewayError as exc:
            rows.append({"id": item.id, "error": exc.kind})
    return {"rows": rows}


def main() -> int:
    adapter = LC.LlamaCppAdapter(CFG.LLM_MODEL, endpoint=CFG.LLM_ENDPOINT,
                                 num_ctx=CFG.LLM_CTX)
    g3_orig = g3_precision("evals/gold/v1.yaml", "data/indexes/fst.sqlite",
                           "7257e606cb94eada1dca40173e2b7f99dd549bc6")
    g3_cf = g3_precision("evals/gold/v1_counterfactual.yaml",
                         "data/indexes/fst-cf.sqlite",
                         "7257e606cb94eada1dca40173e2b7f99dd549bc6-cf")
    b6_orig = b6_sample("evals/gold/v1.yaml", B6_QUESTIONS, adapter)
    b6_cf = b6_sample("evals/gold/v1_counterfactual.yaml",
                      B6_QUESTIONS, adapter)
    out = {"g3_original": g3_orig, "g3_counterfactual": g3_cf,
           "b6_original": b6_orig, "b6_counterfactual": b6_cf,
           "model": CFG.LLM_MODEL}
    Path("redteam/results").mkdir(parents=True, exist_ok=True)
    Path("redteam/results/f12_contamination.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

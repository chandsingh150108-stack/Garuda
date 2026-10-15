"""Question-answering orchestration (spec Phase 9, task 6).

Pipeline: retrieve -> pre-generation gate -> evidence -> gateway ->
validate -> ONE repair -> validated answer or abstention. The repair re-sends
the same evidence with the validator's error messages; a second failure
abstains deterministically (rollback rule: never loosen validation to pass).

`adapter=None` selects from mentor.config (Phase 8 G2 values). Tests inject a
script adapter; the gateway's transport retries still apply.
"""
from __future__ import annotations

from pathlib import Path

from mentor.answer import abstain as AB
from mentor.answer import contract as C
from mentor.answer import evidence as EV
from mentor.answer import prompts as P
from mentor.answer import validator as V
from mentor import config as CFG
from mentor.llm import gateway as GW
from mentor.llm import llamacpp_adapter as LC
from mentor.llm import ollama_adapter as OA
from mentor.retrieve import search as S


def default_adapter():
    """Build the configured adapter (G2 values; loopback only via egress)."""
    if CFG.LLM_PROVIDER == "ollama":
        return OA.OllamaAdapter(CFG.LLM_MODEL, endpoint=CFG.LLM_ENDPOINT,
                                num_ctx=CFG.LLM_CTX)
    return LC.LlamaCppAdapter(CFG.LLM_MODEL, endpoint=CFG.LLM_ENDPOINT,
                              num_ctx=CFG.LLM_CTX)


def _messages(query: str, blocks: list[dict]) -> list[dict]:
    system = P.build_system(CFG.LLM_SYSTEM_SUFFIX)
    body = "\n\n".join([P.EVIDENCE_HEADER] + [EV.render(b) for b in blocks])
    user = (f"Question: {query}\n\n{body}\n\n"
            "Respond with the JSON answer object only.")
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


def _repair_message(errors: list[V.VError]) -> dict:
    lines = "\n".join(f"- {e.code}: {e.message}" for e in errors)
    return {"role": "user",
            "content": ("Your previous output was REJECTED for:\n" + lines +
                        "\nRespond again with a corrected single JSON object "
                        "matching the schema, citing only the evidence IDs "
                        "given. No other text.")}


def ask(db: Path, sha: str, query: str, k: int = 10, adapter=None,
        evidence_budget: int = EV.EVIDENCE_BUDGET_TOKENS,
        timeout_s: float = 120.0, max_tokens: int = 1024,
        tau_score: float = AB.TAU_SCORE,
        tau_cov: float = AB.TAU_COV) -> dict:
    """End-to-end grounded answer. Always returns a contract-shaped dict."""
    res = S.search(db, sha, query, k=k)
    gate = AB.pre_gate(res["confidence"],
                       bool(res["analysis"]["identifiers"]),
                       tau_score, tau_cov)
    env = EV.build(db, sha, res["hits"], budget_tokens=evidence_budget)
    blocks = env["blocks"]
    if gate["abstain"]:
        out = AB.abstention(blocks, ["retrieval confidence too low"], gate["reason"])
        return {**out, "repairs": 0, "prompt_version": P.PROMPT_VERSION,
                "model": CFG.LLM_MODEL, "evidence_tokens": env["used_tokens"]}
    if adapter is None:
        adapter = default_adapter()
    messages = _messages(query, blocks)
    options = {"max_tokens": max_tokens}
    try:
        parsed = GW.generate(adapter, messages, C.ANSWER_SCHEMA, options,
                             timeout_s=timeout_s)
    except GW.GatewayError as exc:
        out = AB.abstention(blocks, ["model call failed"], f"gateway {exc.kind}")
        return {**out, "repairs": 0, "prompt_version": P.PROMPT_VERSION,
                "model": CFG.LLM_MODEL, "evidence_tokens": env["used_tokens"]}
    errors = V.validate(parsed, blocks)
    repairs = 0
    if errors:
        repairs = 1
        messages = messages + [_repair_message(errors)]
        try:
            parsed = GW.generate(adapter, messages, C.ANSWER_SCHEMA, options,
                                 timeout_s=timeout_s)
        except GW.GatewayError as exc:
            out = AB.abstention(blocks, ["model call failed on repair"],
                                f"gateway {exc.kind}")
            return {**out, "repairs": repairs,
                    "prompt_version": P.PROMPT_VERSION, "model": CFG.LLM_MODEL,
                    "evidence_tokens": env["used_tokens"]}
        errors = V.validate(parsed, blocks)
    if errors:
        missing = [f"{e.code}: {e.message}" for e in errors]
        out = AB.abstention(blocks, missing, "validation failed after repair")
        return {**out, "repairs": repairs, "prompt_version": P.PROMPT_VERSION,
                "model": CFG.LLM_MODEL, "evidence_tokens": env["used_tokens"]}
    answer = C.Answer.model_validate(parsed)
    closest = []
    if answer.status == "abstain":
        closest = [{"id": b["id"], "path": b["path"],
                    "lines": f"{b['start_line']}-{b['end_line']}",
                    "header": b["header"]} for b in blocks[:3]]
    return {"status": answer.status,
            "segments": [s.model_dump() for s in answer.segments],
            "missing": list(answer.missing),
            "repairs": repairs, "prompt_version": P.PROMPT_VERSION,
            "model": CFG.LLM_MODEL, "evidence_tokens": env["used_tokens"],
            "closest": closest,
            "evidence": [{"id": b["id"], "path": b["path"],
                          "lines": f"{b['start_line']}-{b['end_line']}"}
                         for b in blocks]}

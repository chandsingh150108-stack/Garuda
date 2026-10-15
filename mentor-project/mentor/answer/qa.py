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
from mentor.llm import budget as BU
from mentor.llm import gateway as GW
from mentor.llm import llamacpp_adapter as LC
from mentor.llm import ollama_adapter as OA
from mentor.llm import redact as RD
from mentor.retrieve import search as S


def default_adapter():
    """Build the configured adapter (G2 values; loopback only via egress)."""
    if CFG.LLM_PROVIDER == "ollama":
        return OA.OllamaAdapter(CFG.LLM_MODEL, endpoint=CFG.LLM_ENDPOINT,
                                num_ctx=CFG.LLM_CTX)
    return LC.LlamaCppAdapter(CFG.LLM_MODEL, endpoint=CFG.LLM_ENDPOINT,
                              num_ctx=CFG.LLM_CTX)


def _cloud_adapter(provider: str, model: str, key: str):
    if provider == "groq":
        from mentor.llm import groq_adapter as GQ
        return GQ.GroqAdapter(model, key)
    from mentor.llm import gemini_adapter as GE
    return GE.GeminiAdapter(model, key)


def _serve_with_cloud(db: Path, sha: str, query: str, blocks: list[dict],
                      local_adapter, timeout_s: float, max_tokens: int,
                      allowlisted_public: bool) -> tuple:
    """Groq primary -> Gemini fallback -> local last (D11.2).

    Returns (gen_parsed_or_raise, serving_provider, serving_model, fallback,
    cloud_status, use_blocks). Raises GatewayError only when the FINAL local
    attempt fails (callers abstain). Redacted blocks feed every attempt so a
    429-fallback never leaks unredacted text anywhere.
    """
    import os
    red_blocks, _report = RD.redact_blocks(blocks)
    tokens = sum(b.get("approx_tokens", EV.approx_tokens(b["text"]))
                 for b in red_blocks)
    notes: list[str] = []
    for provider in ("groq", "gemini"):
        model = getattr(CFG, f"CLOUD_{provider.upper()}_MODEL", "") or ""
        key = os.environ.get(f"{provider.upper()}_API_KEY", "")
        if not model or not key:
            notes.append(f"{provider}: unconfigured (model/key missing)")
            continue
        limits = getattr(CFG, f"{provider.upper()}_LIMITS", {})
        ok, why = BU.allowed(Path(CFG.CLOUD_BUDGET_DB), provider, limits)
        allowed, gate_why = GW.check_cloud_allowed(
            allow_free_cloud=CFG.ALLOW_FREE_CLOUD,
            allowlisted_public=allowlisted_public,
            scan_clean=RD.manifest_scan_clean(sha), redacted=True,
            within_cap=tokens <= CFG.CLOUD_MAX_TOKENS,
            budget_ok=ok, budget_reason=why, provider=provider)
        if not allowed:
            notes.append(gate_why)
            continue
        messages = _messages(query, red_blocks)
        try:
            parsed = GW.generate(_cloud_adapter(provider, model, key),
                                 messages, C.ANSWER_SCHEMA,
                                 {"max_tokens": max_tokens},
                                 timeout_s=timeout_s)
            BU.record(Path(CFG.CLOUD_BUDGET_DB), provider,
                      tokens + max_tokens)
            return parsed, provider, model, False, f"cloud:{provider}", \
                red_blocks
        except GW.GatewayError as exc:
            # Any cloud failure falls through to the next provider, then
            # local. Schema failures included: unparseable cloud text never
            # reaches the validator; the local attempt decides the outcome.
            notes.append(f"{provider}: {exc.kind}")
            continue
    status = "; ".join(notes) if notes else "cloud unavailable"
    return None, CFG.LLM_PROVIDER, CFG.LLM_MODEL, True, status, red_blocks


MAX_HISTORY_BLOCKS = 6


def _attach_history(repo_path: Path, sha: str,
                    blocks: list[dict]) -> tuple[list[dict], list[str]]:
    """Append commit-record H-blocks for the top evidence files (D14.1).

    Blame covers each block's range; file log adds recency. At most
    MAX_HISTORY_BLOCKS across the top-3 distinct files, rank order. Never
    raises: git failures yield fewer (or zero) blocks, and the caller then
    has no HISTORY to cite — the model must infer or abstain.
    """
    from mentor.features import why as HY
    seen_files: list[str] = []
    for b in blocks:
        if b["path"] not in seen_files:
            seen_files.append(b["path"])
        if len(seen_files) >= 3:
            break
    hblocks: list[dict] = []
    notes: list[str] = []
    for path in seen_files:
        anchor = next(b for b in blocks if b["path"] == path)
        history = HY.history_for_symbol(repo_path, path, anchor["start_line"],
                                        anchor["end_line"])
        new = HY.history_blocks(history, path,
                                start_id=len(hblocks) + 1)
        if len(hblocks) + len(new) > MAX_HISTORY_BLOCKS:
            new = new[:MAX_HISTORY_BLOCKS - len(hblocks)]
        hblocks.extend(new)
        if not new:
            notes.append(f"no history for {path}")
        if len(hblocks) >= MAX_HISTORY_BLOCKS:
            break
    if CFG.GH_PR_LOOKUP and hblocks:
        import re as _re
        prs = _re.findall(r"#(\d+)",
                          " ".join(b.get("text", "") for b in hblocks))
        if prs and len(hblocks) < MAX_HISTORY_BLOCKS + 2:
            pr = HY.gh_pr(int(prs[0]), enabled=True)
            if pr and pr.get("url"):
                hblocks.append({
                    "id": f"H{len(hblocks) + 1}", "kind": "history",
                    "path": "", "lines": "-",
                    "text": (f"PR #{pr['pr']} by {pr['author']} "
                             f"({pr['url']}) titled: {pr['title']}"),
                    "sha": "", "author": pr["author"], "date": ""})
    return blocks + hblocks, notes


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
        tau_cov: float = AB.TAU_COV, cloud: bool = False,
        allowlisted_public: bool = False, why: bool = False,
        repo_path: Path | None = None) -> dict:
    """End-to-end grounded answer. Always returns a contract-shaped dict.

    cloud=True requests cloud acceleration (D11): Groq primary, Gemini
    fallback, local last. Every fallback keeps the output contract; the
    response carries provider/fallback/cloud_status labels (Phase 16 UI).

    why=True appends commit-record H-blocks for the top evidence files
    (Phase 14): causal claims then need H citations (V9) or inference kind.
    Requires repo_path (the checkout); without it, no history is attached.
    """
    res = S.search(db, sha, query, k=k)
    gate = AB.pre_gate(res["confidence"],
                       bool(res["analysis"]["identifiers"]),
                       tau_score, tau_cov)
    env = EV.build(db, sha, res["hits"], budget_tokens=evidence_budget)
    blocks = env["blocks"]
    if gate["abstain"]:
        out = AB.abstention(blocks, ["retrieval confidence too low"], gate["reason"])
        return {**out, "repairs": 0, "prompt_version": P.PROMPT_VERSION,
                "model": CFG.LLM_MODEL, "provider": CFG.LLM_PROVIDER,
                "fallback": False, "cloud_status": "local-only",
                "evidence_tokens": env["used_tokens"]}
    if adapter is None:
        adapter = default_adapter()
    serving, serving_model = CFG.LLM_PROVIDER, CFG.LLM_MODEL
    fallback, cloud_status = False, "local-only"
    use_blocks, first_parsed = list(blocks), None
    history_notes: list[str] = []
    if why and repo_path is not None:
        use_blocks, history_notes = _attach_history(
            repo_path, sha, blocks)
    if cloud:
        first_parsed, serving, serving_model, fallback, cloud_status, \
            use_blocks = _serve_with_cloud(
                db, sha, query, blocks, adapter, timeout_s, max_tokens,
                allowlisted_public)
    messages = _messages(query, use_blocks)
    options = {"max_tokens": max_tokens}
    h_tokens = sum(EV.approx_tokens(b.get("text", "")) for b in use_blocks
                   if b["id"].startswith("H"))
    base = {"repairs": 0, "prompt_version": P.PROMPT_VERSION,
            "model": serving_model, "provider": serving, "fallback": fallback,
            "cloud_status": cloud_status,
            "evidence_tokens": env["used_tokens"] + h_tokens,
            "history_notes": history_notes}
    if first_parsed is None:
        try:
            parsed = GW.generate(adapter, messages, C.ANSWER_SCHEMA, options,
                                 timeout_s=timeout_s)
        except GW.GatewayError as exc:
            out = AB.abstention(blocks, ["model call failed"],
                                f"gateway {exc.kind}")
            return {**out, **base}
    else:
        parsed = first_parsed
    errors = V.validate(parsed, use_blocks)
    repairs = 0
    if errors:
        repairs = 1
        # Repair always runs locally: guaranteed available, no quota spent.
        messages = _messages(query, use_blocks) + [_repair_message(errors)]
        try:
            parsed = GW.generate(adapter, messages, C.ANSWER_SCHEMA, options,
                                 timeout_s=timeout_s)
        except GW.GatewayError as exc:
            out = AB.abstention(blocks, ["model call failed on repair"],
                                f"gateway {exc.kind}")
            return {**out, **base, "repairs": repairs}
        errors = V.validate(parsed, use_blocks)
    if errors:
        missing = [f"{e.code}: {e.message}" for e in errors]
        out = AB.abstention(blocks, missing, "validation failed after repair")
        return {**out, **base, "repairs": repairs}
    answer = C.Answer.model_validate(parsed)
    closest = []
    if answer.status == "abstain":
        closest = [{"id": b["id"], "path": b["path"],
                    "lines": f"{b['start_line']}-{b['end_line']}",
                    "header": b["header"]} for b in blocks[:3]]
    segments = []
    for s in answer.segments:
        seg = s.model_dump()
        # Server-side provenance default (D14.1): derived from pointers, not
        # from the model's label — an explicit model label is kept as-is.
        if seg.get("provenance") is None:
            ids = seg.get("evidence_ids", [])
            if s.kind == "fact" and any(
                    i.startswith("H") for i in ids):
                seg["provenance"] = "history"
            elif s.kind == "fact":
                seg["provenance"] = "proven"
            elif s.kind == "inference":
                seg["provenance"] = "inferred"
            else:
                seg["provenance"] = "unknown"
        segments.append(seg)
    return {"status": answer.status,
            "segments": segments,
            "missing": list(answer.missing),
            "repairs": repairs, "prompt_version": P.PROMPT_VERSION,
            "model": serving_model, "provider": serving, "fallback": fallback,
            "cloud_status": cloud_status,
            "evidence_tokens": env["used_tokens"],
            "closest": closest,
            "evidence": [{"id": b["id"], "path": b["path"], "lines": (
                b["lines"] if "lines" in b
                else f"{b['start_line']}-{b['end_line']}")}
                         for b in use_blocks]}

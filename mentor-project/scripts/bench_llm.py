"""G2 hardware/model benchmark (spec Phase 8).

Measures, for one loaded model: nvidia-smi memory before/after load and
after 4K/8K prompts; TTFT + total per gold question; 10-minute sustained
throughput with temp/power sampling; schema-validity rate without repair on
gold prompts. The server (llama-server or Ollama) is started by the operator;
this script only measures. Prints JSON to stdout (recorded verbatim).

Probe schema is a Phase 9-contract-shaped proxy (status + segments); Phase 9
re-measures validity with the final contract + validator.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "segments": {"type": "array", "items": {
            "type": "object",
            "properties": {"text": {"type": "string"},
                           "evidence": {"type": "array", "items": {"type": "string"}}},
            "required": ["text", "evidence"]}},
    },
    "required": ["status", "segments"],
}

PROMPT_TEMPLATE = ("Answer the repository question with JSON only, matching the "
                   "given schema. Question: {question}\nEvidence:\n{evidence}\n")


def smi() -> dict:
    """One nvidia-smi snapshot (used/free MiB, temp C, power W)."""
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.free,memory.total,"
         "temperature.gpu,power.draw,power.max_limit,driver_version,name",
         "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        return {"available": False}
    parts = [p.strip() for p in out.stdout.strip().split(",")]
    keys = ["used_mib", "free_mib", "total_mib", "temp_c", "power_w",
            "power_max_w", "driver", "name"]
    rec = {"available": True}
    for key, val in zip(keys, parts):
        try:
            rec[key] = float(val)
        except ValueError:
            rec[key] = val if val not in ("[N/A]", "[NOT SUPPORTED]") else None
    return rec


def post(provider: str, endpoint: str, payload: dict, timeout_s: float) -> dict:
    path = "/api/chat" if provider == "ollama" else "/v1/chat/completions"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode())


def stream_times(provider: str, endpoint: str, payload: dict,
                 timeout_s: float) -> tuple[float, float, dict]:
    """Return (ttft_s, total_s, final_body). Parses SSE/event streams."""
    path = "/api/chat" if provider == "ollama" else "/v1/chat/completions"
    payload = dict(payload, stream=True)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + path, data=data,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft = None
    chunks: list[str] = []
    usage: dict = {}
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        while True:
            line = resp.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if text.startswith("data:"):
                text = text[5:].strip()
            if not text or text == "[DONE]":
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                continue
            piece = ""
            if provider == "ollama":
                piece = ((event.get("message") or {}).get("content") or "")
                if event.get("done"):
                    usage = {k: event.get(k) for k in
                             ("prompt_eval_count", "eval_count") if event.get(k)}
            else:
                choices = event.get("choices") or [{}]
                piece = ((choices[0].get("delta") or {}).get("content")
                         or (choices[0].get("message") or {}).get("content") or "")
                if event.get("usage"):
                    usage = event["usage"]
            if piece and ttft is None:
                ttft = time.perf_counter() - t0
            chunks.append(piece)
    total = time.perf_counter() - t0
    return (ttft if ttft is not None else total), total, {"text": "".join(chunks),
                                                         "usage": usage}


def build_body(provider: str, model: str, messages: list[dict], ctx: int,
               max_tokens: int) -> dict:
    if provider == "ollama":
        return {"model": model, "messages": messages, "stream": False,
                "format": PROBE_SCHEMA,
                "options": {"temperature": 0, "num_ctx": ctx}}
    return {"model": model, "messages": messages, "temperature": 0,
            "max_tokens": max_tokens, "stream": False,
            "response_format": {"type": "json_object"}}


def valid_schema(text: str) -> bool:
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(body, dict) or "status" not in body or "segments" not in body:
        return False
    return isinstance(body["segments"], list)


def main() -> int:
    parser = argparse.ArgumentParser(description="G2 model/hardware benchmark.")
    parser.add_argument("--provider", default="llamacpp", choices=["llamacpp", "ollama"])
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080")
    parser.add_argument("--model", required=True)
    parser.add_argument("--ctx", type=int, default=8192)
    parser.add_argument("--gold", default="evals/gold/v1.yaml")
    parser.add_argument("--sustained-minutes", type=float, default=10.0)
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="Ceiling per answer (256 truncates JSON mid-object; "
                             "1024 measures schema adherence, not truncation)")
    parser.add_argument("--no-think-suffix", default="",
                        help="Appended to system prompt (e.g. /no_think for Qwen3)")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    from mentor.eval import gold as G
    items = [i for i in G.load(Path(args.gold)).items if i.expected_status == "answer"]
    system = ("You answer repository questions with JSON only."
              + (f" {args.no_think_suffix}" if args.no_think_suffix else ""))
    if args.provider == "llamacpp":
        # D8.4: llama-server `response_format: json_object` constrains output
        # to valid JSON only, NOT to our schema (V18). The schema must travel
        # in the prompt (Ollama carries it via `format` instead). Without this
        # the model invents its own keys and validity measures ~0 (observed).
        system += (" Respond with a single JSON object matching this schema, "
                   "and no other text: " + json.dumps(PROBE_SCHEMA))

    result: dict = {"model": args.model, "provider": args.provider, "ctx": args.ctx,
                    "smi_idle": smi(), "questions": [], "sustained": {}}
    valid = 0
    for item in items:
        evidence = "\n".join(f"[{g.path}:{g.start_line}-{g.end_line}]" for g in item.gold)
        messages = [{"role": "system", "content": system},
                    {"role": "user",
                     "content": PROMPT_TEMPLATE.format(question=item.question,
                                                       evidence=evidence)}]
        body = build_body(args.provider, args.model, messages, args.ctx, args.max_tokens)
        ttft, total, stream = stream_times(args.provider, args.endpoint, body, args.timeout)
        # Non-streaming call is what validity is judged on (same contract).
        final = post(args.provider, args.endpoint, body, args.timeout)
        if args.provider == "ollama":
            text = (final.get("message") or {}).get("content", "")
            usage = {k: final.get(k) for k in ("prompt_eval_count", "eval_count")}
        else:
            text = ((final.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            usage = final.get("usage", {})
        ok = valid_schema(text)
        valid += bool(ok)
        result["questions"].append({"id": item.id, "ttft_s": round(ttft, 2),
                                   "total_s": round(total, 2), "valid": ok,
                                   "usage": usage})
    result["schema_validity"] = {"valid": valid, "n": len(items),
                                 "rate": round(valid / len(items), 3) if items else 0.0}

    # Memory stages: fixed filler prompts sized to ~4K and ~8K tokens
    # (chars/4 approximation, verified against returned usage).
    for stage, target in (("smi_4k", 4096), ("smi_8k", 8192)):
        filler = ("Repository context filler. " * (target // 7))[:target * 4]
        stage_body = build_body(
            args.provider, args.model,
            [{"role": "system", "content": system},
             {"role": "user", "content": f"Summarize in one sentence: {filler}"}],
            args.ctx, 64)
        final = post(args.provider, args.endpoint, stage_body, args.timeout)
        if args.provider == "ollama":
            used = final.get("prompt_eval_count")
        else:
            used = (final.get("usage") or {}).get("prompt_tokens")
        result[stage] = {"prompt_tokens": used, **smi()}

    # Sustained loop: fixed prompt, per-iteration tok/s + smi sample.
    sustain_prompt = [{"role": "system", "content": system},
                      {"role": "user",
                       "content": PROMPT_TEMPLATE.format(
                           question="Summarize the signup flow in three steps.",
                           evidence="[backend/app/api/routes/users.py:146-159]")}]
    sustain_body = build_body(args.provider, args.model, sustain_prompt,
                              args.ctx, args.max_tokens)
    deadline = time.perf_counter() + args.sustained_minutes * 60.0
    toks, smi_samples = [], []
    iters = 0
    while time.perf_counter() < deadline:
        t0 = time.perf_counter()
        final = post(args.provider, args.endpoint, sustain_body, args.timeout)
        dt = time.perf_counter() - t0
        iters += 1
        if args.provider == "ollama":
            out_n = final.get("eval_count") or 0
        else:
            out_n = ((final.get("usage") or {}).get("completion_tokens")) or 0
        if out_n and dt > 0:
            toks.append(out_n / dt)
        smi_samples.append(smi())
    result["smi_peak"] = max(
        (s.get("used_mib", 0) for s in smi_samples if s.get("available")), default=0)
    result["sustained"] = {
        "iterations": iters, "tok_per_s_mean": round(statistics.fmean(toks), 1) if toks else 0.0,
        "tok_per_s_p50": round(statistics.median(toks), 1) if toks else 0.0,
        "temps_c": [s.get("temp_c") for s in smi_samples if s.get("available")],
        "power_w": [s.get("power_w") for s in smi_samples if s.get("available")],
    }
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

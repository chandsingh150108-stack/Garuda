"""llama.cpp server adapter (A17 fallback, D8.0; OpenAI-compatible).

Used live for G2 because the Ollama installer is network-blocked. Same
contract as the Ollama adapter: temperature 0, JSON-object response mode,
server-side validation downstream. `response_format: json_object` constrains
output to valid JSON, not to the schema — never relied upon alone.
"""
from __future__ import annotations

from mentor.llm import gateway as GW


class LlamaCppAdapter:
    def __init__(self, model: str, endpoint: str = "http://127.0.0.1:8080",
                 num_ctx: int = 8192, max_tokens: int = 1024):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict], schema: dict, options: dict,
                 timeout_s: float) -> str:
        _ = schema  # documented: json_object mode, schema enforced downstream
        body = GW.post_json(f"{self.endpoint}/v1/chat/completions", {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": options.get("max_tokens", self.max_tokens),
            "stream": False,
            "response_format": {"type": "json_object"},
        }, timeout_s)
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GW.GatewayError(GW.GatewayError.SCHEMA,
                                  f"unexpected llama-server body keys: {exc}")

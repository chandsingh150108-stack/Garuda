"""Ollama adapter: local HTTP API on loopback (spec Phase 8, D8.4).

Sends temperature 0, num_ctx, stream=false, and the JSON schema via `format`.
Schema adherence is NOT assumed (V18) — the caller validates.
"""
from __future__ import annotations

from mentor.llm import gateway as GW

DEFAULT_ENDPOINT = "http://127.0.0.1:11434"


class OllamaAdapter:
    def __init__(self, model: str, endpoint: str = DEFAULT_ENDPOINT,
                 num_ctx: int = 8192):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.num_ctx = num_ctx

    def complete(self, messages: list[dict], schema: dict, options: dict,
                 timeout_s: float) -> str:
        body = GW.post_json(f"{self.endpoint}/api/chat", {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": self.num_ctx,
                        **{k: v for k, v in options.items() if k != "temperature"}},
        }, timeout_s)
        try:
            return body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise GW.GatewayError(GW.GatewayError.SCHEMA,
                                  f"unexpected Ollama body keys: {exc}")

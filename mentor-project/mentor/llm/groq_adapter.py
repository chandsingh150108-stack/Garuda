"""Groq adapter: OpenAI-compatible chat API (spec Phase 11, D11.2 primary).

Model names are NEVER hardcoded here: the caller supplies the model chosen
from the provider's live model list (`list_models`), recorded per demo. Keys
come from the GROQ_API_KEY environment variable only — never logged, never
written to any file.
"""
from __future__ import annotations

from mentor.llm import gateway as GW

CHAT_PATH = "/openai/v1/chat/completions"
MODELS_PATH = "/openai/v1/models"
DEFAULT_BASE = "https://api.groq.com"


class GroqAdapter:
    def __init__(self, model: str, api_key: str,
                 base_url: str = DEFAULT_BASE):
        if not model:
            raise ValueError("Groq model must come from the live model list")
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for cloud inference")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._auth = {"Authorization": f"Bearer {api_key}"}

    def complete(self, messages: list[dict], schema: dict, options: dict,
                 timeout_s: float) -> str:
        _ = schema  # json_object mode; schema enforced server-side (Phase 9)
        body = GW.post_json(f"{self.base_url}{CHAT_PATH}", {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": options.get("max_tokens", 1024),
            "stream": False,
            "response_format": {"type": "json_object"},
        }, timeout_s, headers=self._auth, cloud="groq")
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GW.GatewayError(GW.GatewayError.SCHEMA,
                                  f"unexpected Groq body keys: {exc}")


def parse_models(body: dict) -> list[str]:
    """Pure parser for the OpenAI-compatible list shape (unit-tested)."""
    return sorted(m["id"] for m in body.get("data", []) if m.get("id"))


def list_models(api_key: str, base_url: str = DEFAULT_BASE,
                timeout_s: float = 30.0) -> list[str]:
    """Live model list from the provider (spec: never hardcode names)."""
    body = GW.get_json(f"{base_url.rstrip('/')}{MODELS_PATH}", timeout_s,
                       headers={"Authorization": f"Bearer {api_key}"},
                       cloud="groq")
    return parse_models(body)

"""Gemini adapter: generateContent API (spec Phase 11, D11.2 fallback).

Gemini is NEVER used for non-public repositories (enforced by the gateway
gate, D11.1): free-tier prompts may train Google products (Additional Terms,
Unpaid Services — recorded RESEARCH_LOG Phase 11). Model names come from the
live model list only; keys from GEMINI_API_KEY only, never logged.
"""
from __future__ import annotations

from mentor.llm import gateway as GW

DEFAULT_BASE = "https://generativelanguage.googleapis.com"
API_PATH = "/v1beta/models"
ACTION = ":generateContent"


class GeminiAdapter:
    def __init__(self, model: str, api_key: str,
                 base_url: str = DEFAULT_BASE):
        if not model:
            raise ValueError("Gemini model must come from the live model list")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for cloud inference")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _url(self, suffix: str) -> str:
        return f"{self.base_url}{API_PATH}/{self.model}{suffix}"

    def complete(self, messages: list[dict], schema: dict, options: dict,
                timeout_s: float) -> str:
        _ = schema  # responseMimeType JSON; schema enforced server-side
        system = "\n".join(m["content"] for m in messages
                           if m.get("role") == "system")
        turns = [{"role": "user", "parts": [{"text": m["content"]}]}
                 for m in messages if m.get("role") != "system"]
        body = GW.post_json(f"{self._url(ACTION)}?key={self.api_key}", {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": turns,
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": options.get("max_tokens", 1024),
            },
        }, timeout_s, cloud="gemini")
        try:
            parts = body["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise GW.GatewayError(GW.GatewayError.SCHEMA,
                                  f"unexpected Gemini body keys: {exc}")


def parse_models(body: dict) -> list[str]:
    """Pure parser for the Gemini list shape (unit-tested)."""
    return sorted(m["name"].split("/")[-1]
                  for m in body.get("models", []) if m.get("name"))


def list_models(api_key: str, base_url: str = DEFAULT_BASE,
                timeout_s: float = 30.0) -> list[str]:
    """Live model list from the provider (spec: never hardcode names)."""
    body = GW.get_json(f"{base_url.rstrip('/')}{API_PATH}?key={api_key}",
                       timeout_s, cloud="gemini")
    return parse_models(body)

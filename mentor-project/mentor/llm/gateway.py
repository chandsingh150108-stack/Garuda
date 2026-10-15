"""Model gateway: one interface, structured errors (spec Phase 8, D8.4).

generate(messages, schema, options) -> parsed dict. Bounded retries apply to
TRANSPORT errors only (timeout/connection, max 2 attempts). Schema failures
are returned as errors for the validator layer (Phase 9) — never retried
here. Every request passes the egress guard first.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from mentor.llm import egress as EG


class GatewayError(RuntimeError):
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    SCHEMA = "schema"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"

    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def _request(url: str, payload: dict | None, headers: dict | None,
             timeout_s: float, cloud: str | None) -> dict:
    """One HTTP round-trip with egress enforcement. 429 maps to RATE_LIMITED
    (the fallback trigger); every other transport failure stays TRANSPORT."""
    if cloud is None:
        EG.check_url(url)
    else:
        EG.check_cloud_url(url, cloud)
    # Keys travel in headers/query per provider convention and are NEVER
    # logged: this module logs nothing, and errors carry kinds, not bodies.
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    heads = {"Content-Type": "application/json"}
    if headers:
        heads.update(headers)
    request = urllib.request.Request(url, data=data, headers=heads,
                                     method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise GatewayError(GatewayError.RATE_LIMITED,
                               f"provider rate limit (HTTP 429)")
        raise GatewayError(GatewayError.TRANSPORT, f"HTTP {exc.code}")
    except TimeoutError:
        raise GatewayError(GatewayError.TIMEOUT, f"no response in {timeout_s}s")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            raise GatewayError(GatewayError.TIMEOUT, f"no response in {timeout_s}s")
        raise GatewayError(GatewayError.TRANSPORT, str(reason))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GatewayError(GatewayError.SCHEMA, f"non-JSON transport body: {exc}")


def post_json(url: str, payload: dict, timeout_s: float,
              headers: dict | None = None,
              cloud: str | None = None) -> dict:
    """POST JSON with a hard timeout. Transport errors map to GatewayError."""
    return _request(url, payload, headers, timeout_s, cloud)


def get_json(url: str, timeout_s: float, headers: dict | None = None,
             cloud: str | None = None) -> dict:
    """GET JSON (provider model lists). Same error contract as post_json."""
    return _request(url, None, headers, timeout_s, cloud)


def generate(adapter, messages: list[dict], schema: dict,
             options: dict | None = None, retries: int = 2,
             timeout_s: float = 120.0) -> dict:
    """Call an adapter with transport-only retries. Returns the parsed body."""
    options = options or {}
    last: GatewayError | None = None
    for _ in range(max(1, retries)):
        try:
            text = adapter.complete(messages, schema, options, timeout_s)
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise GatewayError(GatewayError.SCHEMA, f"unparseable output: {exc}")
        except GatewayError as exc:
            if exc.kind in (GatewayError.TIMEOUT, GatewayError.TRANSPORT):
                last = exc
                time.sleep(1.0)
                continue
            raise
    assert last is not None
    raise last


# --- Phase 11 cloud gate (D11.1) + fallback --------------------------------

def check_cloud_allowed(*, allow_free_cloud: bool, allowlisted_public: bool,
                        scan_clean: bool, redacted: bool, within_cap: bool,
                        budget_ok: bool, budget_reason: str,
                        provider: str) -> tuple[bool, str]:
    """Ordered gate: every condition must hold. First failure names itself;
    the caller falls back to local inference (CLOUD_BLOCKED contract)."""
    if provider == "gemini":
        # Free-tier prompts may train Google products: never private code.
        if not allowlisted_public:
            return False, "CLOUD_BLOCKED: gemini requires a public repository"
    conditions = [
        (allow_free_cloud, "CLOUD_BLOCKED: allow_free_cloud is false"),
        (allowlisted_public, "CLOUD_BLOCKED: repository not on public allowlist"),
        (scan_clean, "CLOUD_BLOCKED: latest secret scan not clean"),
        (redacted, "CLOUD_BLOCKED: redaction pass did not run"),
        (within_cap, "CLOUD_BLOCKED: payload exceeds size cap"),
        (budget_ok, f"CLOUD_BLOCKED: {budget_reason}"),
    ]
    for ok, reason in conditions:
        if not ok:
            return False, reason
    return True, "cloud allowed"


def generate_auto(cloud_adapter, local_adapter, messages: list[dict],
                  schema: dict, options: dict | None = None,
                  retries: int = 2, timeout_s: float = 120.0,
                  provider: str = "cloud") -> tuple[dict, str, bool]:
    """Try cloud, fall back to local on CLOUD_BLOCKED / 429 / timeout /
    transport failure. Returns (parsed, serving_provider, fallback).

    The output contract is UNCHANGED by fallback (spec failure condition);
    callers surface serving_provider/fallback as labels only. Schema failures
    propagate: they are the validator's job, not a transport problem.
    """
    options = options or {}
    try:
        return generate(cloud_adapter, messages, schema, options,
                        retries=retries,
                        timeout_s=timeout_s), provider, False
    except GatewayError as exc:
        if exc.kind not in (GatewayError.BLOCKED, GatewayError.RATE_LIMITED,
                            GatewayError.TIMEOUT, GatewayError.TRANSPORT):
            raise
    return generate(local_adapter, messages, schema, options,
                    retries=retries,
                    timeout_s=timeout_s), "local", True

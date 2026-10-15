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

    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def post_json(url: str, payload: dict, timeout_s: float) -> dict:
    """POST JSON with a hard timeout. Transport errors map to GatewayError."""
    EG.check_url(url)
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        raise GatewayError(GatewayError.TIMEOUT, f"no response in {timeout_s}s")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            raise GatewayError(GatewayError.TIMEOUT, f"no response in {timeout_s}s")
        raise GatewayError(GatewayError.TRANSPORT, str(reason))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GatewayError(GatewayError.SCHEMA, f"non-JSON transport body: {exc}")


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

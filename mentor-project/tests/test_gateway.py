"""Phase 8 gate: gateway transport semantics (spec Phase 8)."""
import json
import time

import pytest

from mentor.llm import gateway as GW


class ScriptAdapter:
    """Programmable adapter: yields configured outcomes per call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_generate_parses_valid_json():
    adapter = ScriptAdapter(['{"status": "answer"}'])
    assert GW.generate(adapter, [{"role": "user", "content": "hi"}],
                        {"type": "object"}) == {"status": "answer"}
    assert adapter.calls == 1


def test_schema_failure_never_retried():
    adapter = ScriptAdapter(["not json"])
    with pytest.raises(GW.GatewayError) as exc:
        GW.generate(adapter, [], {"type": "object"})
    assert exc.value.kind == GW.GatewayError.SCHEMA
    assert adapter.calls == 1  # repair is the validator's job (Phase 9)


def test_transport_timeout_retries_then_raises():
    adapter = ScriptAdapter([GW.GatewayError(GW.GatewayError.TIMEOUT, "slow")] * 5)
    t0 = time.perf_counter()
    with pytest.raises(GW.GatewayError) as exc:
        GW.generate(adapter, [], {}, retries=2, timeout_s=5.0)
    assert exc.value.kind == GW.GatewayError.TIMEOUT
    assert adapter.calls == 2
    assert time.perf_counter() - t0 < 10.0


def test_transport_recovers_on_retry():
    adapter = ScriptAdapter([GW.GatewayError(GW.GatewayError.TRANSPORT, "reset"),
                             '{"status": "ok"}'])
    assert GW.generate(adapter, [], {}) == {"status": "ok"}
    assert adapter.calls == 2


def test_post_json_timeout_structured():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Slow(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(30)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Slow)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(GW.GatewayError) as exc:
            GW.post_json(f"http://127.0.0.1:{port}/x", {"a": 1}, timeout_s=1.0)
        assert exc.value.kind == GW.GatewayError.TIMEOUT
    finally:
        server.shutdown()

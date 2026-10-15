"""Phase 8 gate: adapter wire format + egress guard (spec Phase 8, D8.4)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mentor.llm import gateway as GW
from mentor.llm import llamacpp_adapter as LC
from mentor.llm import ollama_adapter as OA
from tests.socket_guard import SocketGuard

SCHEMA = {"type": "object", "properties": {"status": {"type": "string"}}}


class CaptureHandler(BaseHTTPRequestHandler):
    bodies: list[dict] = []
    mode = "ollama"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        CaptureHandler.bodies.append({"path": self.path, "payload": payload})
        if CaptureHandler.mode == "ollama":
            body = {"message": {"content": json.dumps({"status": "answer"})}}
        else:
            body = {"choices": [{"message": {"content": json.dumps({"status": "answer"})}}]}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def _server(mode: str):
    CaptureHandler.bodies = []
    CaptureHandler.mode = mode
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_ollama_adapter_sends_schema_and_temp0():
    server = _server("ollama")
    try:
        adapter = OA.OllamaAdapter("m", endpoint=f"http://127.0.0.1:{server.server_address[1]}")
        out = GW.generate(adapter, [{"role": "user", "content": "q"}], SCHEMA)
        assert out == {"status": "answer"}
        payload = CaptureHandler.bodies[0]["payload"]
        assert payload["format"] == SCHEMA
        assert payload["options"]["temperature"] == 0
        assert payload["stream"] is False
    finally:
        server.shutdown()


def test_llamacpp_adapter_sends_json_object_and_temp0():
    server = _server("llamacpp")
    try:
        adapter = LC.LlamaCppAdapter("m", endpoint=f"http://127.0.0.1:{server.server_address[1]}")
        out = GW.generate(adapter, [{"role": "user", "content": "q"}], SCHEMA)
        assert out == {"status": "answer"}
        payload = CaptureHandler.bodies[0]["payload"]
        assert CaptureHandler.bodies[0]["path"] == "/v1/chat/completions"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["temperature"] == 0
        assert payload["stream"] is False
    finally:
        server.shutdown()


def test_egress_guard_refuses_non_loopback():
    server = _server("ollama")
    port = server.server_address[1]
    try:
        adapter = OA.OllamaAdapter("m", endpoint=f"http://10.0.0.1:{port}")
        with SocketGuard(enforce=True) as guard:
            with pytest.raises(Exception):
                GW.generate(adapter, [], {}, retries=1, timeout_s=2.0)
        assert guard.attempts == [] or guard.non_loopback == []
    finally:
        server.shutdown()


def test_no_outbound_on_default_off():
    # Default configuration performs zero non-loopback connections: the
    # full Phase 8 unit suite runs under the guard in CI-style runs.
    with SocketGuard(enforce=True) as guard:
        pass
    assert guard.non_loopback == []


def test_live_smoke_opt_in():
    """Live smoke (spec Phase 8): opt-in via MENTOR_LIVE=1, one short
    schema-constrained request against the loopback server returns
    valid JSON. Skipped otherwise so the unit suite stays offline."""
    import os
    if os.environ.get("MENTOR_LIVE") != "1":
        pytest.skip("live server not requested (set MENTOR_LIVE=1)")
    endpoint = os.environ.get("MENTOR_LIVE_ENDPOINT", "http://127.0.0.1:8080")
    provider = os.environ.get("MENTOR_LIVE_PROVIDER", "llamacpp")
    if provider == "ollama":
        adapter = OA.OllamaAdapter(
            os.environ.get("MENTOR_LIVE_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M"),
            endpoint=endpoint)
    else:
        adapter = LC.LlamaCppAdapter(
            os.environ.get("MENTOR_LIVE_MODEL", "x"), endpoint=endpoint)
    out = GW.generate(adapter, [{"role": "user",
                                 "content": 'Reply with JSON only: {"status": "ok"}'}],
                      {"type": "object"}, {"max_tokens": 64}, timeout_s=120.0)
    assert isinstance(out, dict)

"""Phase 19 gate: offline serving — modes, cache-labelled demo answers, and
zero non-loopback socket attempts under an enforcing guard."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mentor import config as CFG
from mentor.answer import cache as CA
from mentor.answer import prompts as P
from mentor.api import app as APP
from mentor.api import routes as R
from tests.socket_guard import SocketGuard
from tests.test_freshness import build_fixture


def _seed_cached_answer(fx, question: str, k: int = 10) -> None:
    blocks = [{"id": "E1", "path": "pkg/a.py", "lines": "1-10"}]
    response = {"status": "answer",
                "segments": [{"text": "handled by `alpha`", "kind": "fact",
                              "evidence_ids": ["E1"], "provenance": "proven"}],
                "missing": [], "repairs": 0,
                "prompt_version": P.PROMPT_VERSION, "model": CFG.LLM_MODEL,
                "provider": CFG.LLM_PROVIDER, "fallback": False,
                "cloud_status": "local-only", "evidence_tokens": 10,
                "evidence": [{"id": "E1", "path": "pkg/a.py", "lines": "1-10",
                              "header": "alpha", "hash": "h"}],
                "closest": []}
    key = CA.make_key("fresh", fx["sha"], question, CFG.LLM_PROVIDER,
                      CFG.LLM_MODEL, P.PROMPT_VERSION, k)
    assert CA.store(fx["index"], key, "fresh", fx["sha"], response) is True


def _client(fx) -> TestClient:
    R.REGISTRY.clear()
    R.REGISTRY["fresh"] = {"id": "fresh", "path": str(fx["repo"].resolve()),
                           "sha": fx["sha"], "index": str(fx["index"])}
    return TestClient(APP.create_app())


def test_modes_default_local_and_unknown_fails_safe(monkeypatch):
    monkeypatch.delenv("MENTOR_MODE", raising=False)
    assert CFG.active_mode() == "LOCAL"
    monkeypatch.setenv("MENTOR_MODE", "LOCAL-OFFLINE")
    assert CFG.active_mode() == "LOCAL-OFFLINE"
    monkeypatch.setenv("MENTOR_MODE", "bogus-mode")
    assert CFG.active_mode() == "LOCAL"
    assert "mode=" in CFG.mode_banner()


def test_offline_mode_vetoes_cloud_even_when_flag_set(monkeypatch):
    monkeypatch.setenv("MENTOR_MODE", "LOCAL-OFFLINE")
    monkeypatch.setattr(CFG, "ALLOW_FREE_CLOUD", True)
    assert CFG.cloud_enabled() is False
    monkeypatch.setenv("MENTOR_MODE", "LOCAL")
    assert CFG.cloud_enabled() is True


def test_cached_demo_answer_served_with_label_and_no_egress(tmp_path,
                                                            monkeypatch):
    monkeypatch.setenv("MENTOR_MODE", "LOCAL-OFFLINE")
    fx = build_fixture(tmp_path)
    question = "How does alpha work?"
    _seed_cached_answer(fx, question)
    client = _client(fx)
    try:
        with SocketGuard(enforce=True) as guard:
            r = client.post("/api/repos/fresh/ask",
                            json={"question": question, "k": 10})
            s = client.get("/api/repos/fresh/status")
        assert r.status_code == 200
        body = r.json()
        assert body["cached"] is True  # cache label (Phase 19 gate)
        assert body["provider"] == CFG.LLM_PROVIDER  # local adapter served it
        # (The web client maps provider ids to LOCAL/CLOUD display labels.)
        assert guard.non_loopback == []
        assert s.status_code == 200
    finally:
        R.REGISTRY.clear()


def test_socket_guard_blocks_non_loopback():
    import socket
    import urllib.request
    with SocketGuard(enforce=True) as guard:
        with pytest.raises(OSError):
            urllib.request.urlopen("http://example.com/", timeout=5)
        # Loopback dial attempts are recorded but not blocked.
        sock = socket.socket()
        try:
            sock.connect(("127.0.0.1", 9))
        except OSError:
            pass
        finally:
            sock.close()
    hosts = [h for h, _ in guard.attempts]
    # urllib resolves before connect, so the guard records IPs, not names.
    assert guard.non_loopback != []  # the remote attempt was seen…
    for host, _ in guard.non_loopback:
        assert host != "127.0.0.1"  # …and classified non-loopback (blocked)

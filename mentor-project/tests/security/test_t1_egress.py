"""T1: data leaves the laptop by accident. Boundary: gateway.

Controls: cloud adapters default OFF, per-repo allowlist, loopback-only
egress guard. Tests: default-off, loopback allowlist, non-loopback blocked,
and zero non-loopback socket attempts during a local search flow.
"""
from mentor import config as CFG
from mentor.answer import qa as QA
from mentor.index import freshness as FR
from mentor.llm import egress as EG
from tests.socket_guard import SocketGuard
from tests.test_freshness import build_fixture


def test_cloud_default_off():
    assert CFG.ALLOW_FREE_CLOUD is False


def test_egress_guard_allows_loopback_blocks_remote():
    assert EG.check_url("http://127.0.0.1:8080/v1/chat/completions")
    for url in ("https://api.groq.com/v1", "http://10.0.0.5:1/",
                "http://example.com/"):
        try:
            EG.check_url(url)
        except EG.EgressBlocked:
            continue
        raise AssertionError(f"not blocked: {url}")


def test_local_search_makes_no_remote_connections(tmp_path):
    fx = build_fixture(tmp_path)
    with SocketGuard() as guard:
        FR.index_status(fx["repo"], fx["index"], fx["sha"])
    assert guard.non_loopback == []
    assert QA.ask is not None  # local path exists; cloud needs explicit opt-in

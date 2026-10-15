"""Phase 8 gate: egress policy units (spec Phase 8, T1 boundary)."""
import pytest

from mentor.llm import egress as EG


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/api/chat",
    "http://127.0.0.1:8080/v1/chat/completions",
    "http://localhost:11434/",
    "http://[::1]:8080/x",
])
def test_loopback_allowed(url: str):
    assert EG.check_url(url)  # returns host, no raise


@pytest.mark.parametrize("url", [
    "https://api.groq.com/v1",
    "http://10.0.0.5:11434/",
    "http://192.168.1.2:8080/",
    "http://example.com/",
    "not-a-url",
])
def test_non_loopback_blocked_by_default(url: str):
    with pytest.raises(EG.EgressBlocked):
        EG.check_url(url)

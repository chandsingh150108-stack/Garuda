"""Egress guard: the only point evidence may leave the process (spec Phase 8).

Default policy is local-only: any non-loopback destination is refused with a
structured error before any byte is sent. Cloud destinations arrive in
Phase 11 behind allowlist + budget + redaction gates — never by default.
"""
from __future__ import annotations

from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

# Phase 11: the only non-loopback destinations the system may ever contact,
# and only through the cloud gate (D11.1). Anything else is refused.
CLOUD_HOSTS = {
    "groq": "api.groq.com",
    "gemini": "generativelanguage.googleapis.com",
}


class EgressBlocked(RuntimeError):
    def __init__(self, host: str, reason: str):
        super().__init__(f"egress blocked to {host!r}: {reason}")
        self.host = host
        self.reason = reason


def check_url(url: str, *, policy: str = "local-only") -> str:
    """Validate an outbound URL. Returns the normalized host or raises."""
    host = (urlparse(url).hostname or "").lower()
    if policy == "local-only" and host not in LOOPBACK_HOSTS:
        raise EgressBlocked(host, "local-only policy (Phase 11 gates required)")
    if not host:
        raise EgressBlocked(host, "unparseable URL")
    return host


def check_cloud_url(url: str, provider: str) -> str:
    """Allow exactly the provider's API host (D11.1). The gate in gateway.py
    decides WHETHER a cloud call may happen; this decides WHERE it may go."""
    host = (urlparse(url).hostname or "").lower()
    want = CLOUD_HOSTS.get(provider)
    if want is None or host != want:
        raise EgressBlocked(host or "?", f"not the {provider} API host")
    return host

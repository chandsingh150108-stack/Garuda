"""Egress guard: the only point evidence may leave the process (spec Phase 8).

Default policy is local-only: any non-loopback destination is refused with a
structured error before any byte is sent. Cloud destinations arrive in
Phase 11 behind allowlist + budget + redaction gates — never by default.
"""
from __future__ import annotations

from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


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

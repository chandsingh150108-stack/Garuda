"""Socket recorder/guard for egress tests (Phases 8, 11, 14, 19).

Records every attempted TCP destination. In enforcing mode, non-loopback
connections fail fast. A socket guard in tests records intent; it does not
prove OS-level isolation (recorded as a limit wherever claimed).
"""
from __future__ import annotations

import ipaddress
import socket

_RECORDED: list[tuple[str, int]] = []
_ENFORCE = False
_ORIGINAL_CONNECT = socket.socket.connect


def _is_loopback(host: str) -> bool:
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else str(address)
    port = address[1] if isinstance(address, tuple) and len(address) > 1 else 0
    _RECORDED.append((host, port))
    if _ENFORCE and not _is_loopback(host):
        raise OSError(f"SocketGuard: blocked non-loopback {host}:{port}")
    return _ORIGINAL_CONNECT(self, address)


class SocketGuard:
    """Usage: `with SocketGuard(enforce=True) as guard:` then inspect
    `guard.attempts` and `guard.non_loopback`."""

    def __init__(self, enforce: bool = True):
        self.enforce = enforce
        self.attempts: list[tuple[str, int]] = []
        self._prev = None

    def __enter__(self):
        global _ENFORCE
        del _RECORDED[:]
        self._prev = _ENFORCE
        _ENFORCE = self.enforce
        if socket.socket.connect is not _guarded_connect:
            socket.socket.connect = _guarded_connect
        return self

    def __exit__(self, *args):
        global _ENFORCE
        _ENFORCE = self._prev if self._prev is not None else False
        self.attempts = list(_RECORDED)
        return False

    @property
    def non_loopback(self) -> list[tuple[str, int]]:
        return [(h, p) for h, p in self.attempts if not _is_loopback(h)]

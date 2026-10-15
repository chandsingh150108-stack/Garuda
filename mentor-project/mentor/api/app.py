"""Service application factory (spec Phase 10, D10.1).

Binding: loopback only (127.0.0.1, ::1, localhost). A non-loopback host
refuses to start unless `allow_non_loopback=True` (the `--unsafe-bind` CLI
flag, documented as unsupported). CORS allows exactly one local web origin
(FastAPI CORSMiddleware with an explicit allow_origins list, credentials
disabled). A pure-ASGI middleware caps request bodies at MAX_BODY_BYTES.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mentor import config as CFG
from mentor.api import routes as R

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class BindRefused(RuntimeError):
    pass


def resolve_bind(host: str, unsafe_bind: bool = False) -> str:
    """Validate the serve host. Non-loopback needs the explicit unsafe flag."""
    if host.lower() not in LOOPBACK_HOSTS and not unsafe_bind:
        raise BindRefused(
            f"refusing non-loopback bind {host!r} without --unsafe-bind "
            "(unsupported; see D10.1)")
    return host


async def _size_limit_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() \
            and int(length) > CFG.MAX_BODY_BYTES:
        return JSONResponse(status_code=413,
                            content={"detail": "request body too large"})
    return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Codebase Mentor", version="0.10.0")
    app.middleware("http")(_size_limit_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[CFG.WEB_ORIGIN],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        max_age=600,
    )
    app.include_router(R.router)
    return app

"""Localhost mutation protection (audit: "localhost is a trust boundary,
but not an absolute security boundary").

Sentinel is loopback-only by design (Rule 1) and needs no user login. That is
fine as a *deployment* decision, but a browser does not treat localhost as a
special trust domain it refuses to talk to: any page the user has open can
issue simple cross-origin POSTs to 127.0.0.1:8420. It may not be able to read
the response — but the side effect (kill a port, launch a server, drop the
knowledge index, delete a session) has already happened.

The defense, following the audit's own recommendation:
- state-changing requests must carry either Sentinel's own `Origin`, or no
  `Origin` at all (curl, the desktop shell, the CLI — none of which send one);
- an *unexpected* `Origin` is a cross-site request, and is refused with 403;
- GET endpoints are untouched — reads cannot mutate anything.

This deliberately does not require a per-install CSRF token. A bearer token
held by the frontend is exactly what an attacker's page would replay (it can
only make form-shaped requests, not read the token), so it defends nothing
here while adding key management that does not exist today. The Origin check
is what actually closes this hole without a login.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.exceptions import SentinelError

_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _expected_origins() -> set[str]:
    """Origins Sentinel itself serves from: the port it binds, on loopback.

    `localhost` and `127.0.0.1` are separate origins to a browser, so both
    spellings must be allowed — a user reaching the dashboard via either
    host name would otherwise be locked out of every button.
    """
    port = settings.port
    return {f"http://localhost:{port}", f"http://127.0.0.1:{port}"}


def _reject(origin: str) -> JSONResponse:
    detail = (
        f"Cross-origin request refused (Origin: {origin}). This server accepts "
        "mutations only from its own origin — the local dashboard, the CLI, "
        "or the desktop shell."
    )
    return JSONResponse(status_code=403, content={"detail": detail})


class LocalhostMutationGuardMiddleware(BaseHTTPMiddleware):
    """Refuse state-changing requests whose `Origin` is not this server."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.method not in _STATE_CHANGING:
            return await call_next(request)
        origin = request.headers.get("origin")
        if origin is None:
            return await call_next(request)  # non-browser client
        if origin.rstrip("/") not in _expected_origins():
            return _reject(origin)
        return await call_next(request)


class OriginViolationError(SentinelError):
    """A state-changing request arrived with a foreign `Origin`."""

    status_code = 403

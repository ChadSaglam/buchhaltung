"""Security response headers — B-108.

A scan on 2026-09-19 reported ``headers.middleware-missing`` alongside 43 other
findings, and it was one of the two that were real: no Content-Security-Policy,
no X-Frame-Options, no X-Content-Type-Options, no HSTS. The same scan reported
``csrf.absent``, which is *not* real — the token travels in an
``Authorization: Bearer`` header out of ``localStorage``, so no browser signs a
cross-site request on the user's behalf. But the two findings meet in one place:
a token in ``localStorage`` is readable by any script that manages to run, and
without a CSP nothing stops one from running. The CSP is the answer to both.

Deliberately not a framework: four headers, set once, on every response.

``frame-ancestors 'none'`` and ``X-Frame-Options`` say the same thing twice on
purpose — the header is obsolete in modern browsers and still the only one some
older ones read. HSTS is only sent over HTTPS: on plain HTTP it is ignored by
the spec, and in local development it would pin ``localhost`` to HTTPS in the
developer's browser for a year, which is a genuinely unpleasant thing to debug.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: The API serves JSON and a handful of generated PDFs/HTML previews. It loads
#: nothing, so everything is denied and the few things the HTML preview needs
#: (its own inline styles) are allowed explicitly.
CSP = (
    "default-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)

HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response

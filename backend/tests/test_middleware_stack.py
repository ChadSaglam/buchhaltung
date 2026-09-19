"""The order of the middleware stack, which is load-bearing and easy to break.

Starlette applies middleware in reverse — the last one added is the outermost —
so the order in `main.py` reads inside-out and a line moved by one position
changes what the browser sees without changing what any other test asserts.

Both facts below were broken in production and neither was caught here:

* CORS was *inside* RequestContextMiddleware, so the 500 that middleware builds
  for an unhandled exception carried no Access-Control-Allow-Origin. Every
  server error reached the browser as "blocked by CORS policy" and the real
  error was unreachable from the client. Found by the first real end-to-end run
  (2026-09-17), after two hours spent on the wrong suspect.
* MaxBodySizeMiddleware has to stay inside CORS for the same reason (B-54) —
  that one was right, and its own comment is what pointed at the other.
"""

from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import RequestContextMiddleware
from app.core.uploads import MaxBodySizeMiddleware
from app.main import application


def _stack() -> list[type]:
    """Outermost first. `add_middleware` inserts at 0, so this list is already
    in outside-in order."""
    return [m.cls for m in application.user_middleware]


def test_cors_ist_die_aeusserste_middleware():
    stack = _stack()
    assert stack[0] is CORSMiddleware, (
        "CORSMiddleware must be the outermost middleware, otherwise any response "
        f"built further out carries no CORS headers. Current order: {stack}"
    )


def test_fehler_middleware_liegt_innerhalb_von_cors():
    stack = _stack()
    assert stack.index(RequestContextMiddleware) > stack.index(CORSMiddleware), (
        "RequestContextMiddleware builds the 500 response itself. Outside CORS "
        "that response has no Access-Control-Allow-Origin, so the browser shows "
        "a CORS error and the actual server error is invisible."
    )


def test_body_limit_liegt_innerhalb_von_cors():
    # B-54's own reasoning, pinned so it cannot drift back.
    stack = _stack()
    assert stack.index(MaxBodySizeMiddleware) > stack.index(CORSMiddleware), (
        "A 413 built outside CORS reaches the browser as a network error instead of 'file too large'."
    )

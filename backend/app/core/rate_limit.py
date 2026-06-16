from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def _tenant_or_ip(request: Request) -> str:
    """Key by authenticated tenant when available, else client IP."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is not None:
        return f"tenant:{tenant_id}"
    return get_remote_address(request)

limiter = Limiter(key_func=_tenant_or_ip, default_limits=["200/minute"])
"""SSO hand-off endpoint (B-36, chadev-platform/contracts/sso.md).

`POST /api/auth/sso {token}` exchanges billing's single-use SSO token for a
regular buchhaltung session — the response is byte-for-byte what
`/api/auth/login` returns, so the frontend stores it the same way.

404 while `PLATFORM_SHARED_SECRET` is unset (no SSO surface at all),
401 `sso_invalid` / `sso_expired` / `sso_replayed`, 409 `email_taken_locally`.
The default per-IP rate limit applies, exactly like `/login`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.security import issue_access_token
from app.schemas.auth import SsoRequest, TokenResponse
from app.services.sso import SsoError, consume_nonce, decode_sso_token, mirror_tenant, mirror_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/sso", response_model=TokenResponse)
async def sso_login(body: SsoRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    secret = settings.PLATFORM_SHARED_SECRET
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        claims = decode_sso_token(body.token, secret)
        await consume_nonce(db, claims)
        tenant = await mirror_tenant(db, claims)
        user = await mirror_user(db, tenant, claims)
    except SsoError as exc:
        await db.rollback()
        raise ApiError(exc.status_code, exc.code, exc.message) from exc
    await db.commit()
    return TokenResponse(access_token=issue_access_token(user))

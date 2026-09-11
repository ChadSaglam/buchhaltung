"""Inbound platform events (B-37, chadev-platform/contracts/events.md).

`POST /api/platform/events` — server-to-server from billing, authenticated by
the HMAC headers, *not* by a Bearer token (there is no user behind it). The
app-level default rate limit still applies (per IP).

Answers: 202 `{"status":"accepted"}` (booked), 200 `{"status":"duplicate"}`
(already applied), 404 while `PLATFORM_SHARED_SECRET` is unset, 401
`bad_signature` / `stale_timestamp`, 400 `unsupported_version` /
`unsupported_event` / `invalid_payload`, 404 `unknown_tenant` (final for the
sender: that `tid` has never done SSO).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.services.platform_events import (
    EventError,
    apply_invoice_paid,
    parse_invoice_paid,
    resolve_tenant,
    verify_signature,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.post(
    "/events",
    status_code=202,
    responses={200: {"description": "Already applied"}, 202: {"description": "Accepted"}},
)
async def receive_event(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    secret = settings.PLATFORM_SHARED_SECRET
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")
    body = await request.body()
    try:
        verify_signature(
            secret,
            timestamp_header=request.headers.get("X-Platform-Timestamp"),
            signature_header=request.headers.get("X-Platform-Signature"),
            body=body,
        )
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise EventError(400, "invalid_payload", "Der Event-Body ist kein gültiges JSON") from exc
        event = parse_invoice_paid(payload)
        tenant = await resolve_tenant(db, event.tid)
        created = await apply_invoice_paid(db, tenant, event)
    except EventError as exc:
        await db.rollback()
        raise ApiError(exc.status_code, exc.code, exc.message) from exc
    await db.commit()
    if not created:
        return JSONResponse(status_code=200, content={"status": "duplicate"})
    return JSONResponse(status_code=202, content={"status": "accepted"})

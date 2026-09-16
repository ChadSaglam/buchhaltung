"""Onboarding — /api/onboarding (B-20)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps import get_current_user
from app.models.user import User
from app.services.onboarding import DATEINAME, beispiel_pdf

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/beispiel-rechnung.pdf")
async def beispiel_rechnung(user: User = Depends(get_current_user)) -> Response:
    """A Swiss QR invoice to try the product with, for somebody who has none.

    Authenticated, even though it holds no tenant data: B-55 spent real effort
    narrowing the unauthenticated surface, and a first-run helper is not a reason
    to widen it again. It touches no database — the file is generated from
    constants.
    """
    return Response(
        content=beispiel_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{DATEINAME}"'},
    )

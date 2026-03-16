"""PDF upload & parse endpoint."""
from __future__ import annotations
import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.services.pdf_parser import extract_transactions_from_pdf

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.post("/parse")
async def parse_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Nur PDF-Dateien erlaubt.")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "PDF zu gross (max 50MB).")

    try:
        transactions = extract_transactions_from_pdf(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(422, f"PDF konnte nicht gelesen werden: {e}")

    if not transactions:
        raise HTTPException(422, "Keine Transaktionen gefunden.")

    return {"transactions": transactions, "count": len(transactions)}

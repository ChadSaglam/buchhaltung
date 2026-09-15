"""Abgleich — the reconciliation inbox (brainstorm phase 3)."""

from __future__ import annotations

import asyncio
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.core.rate_limit import heavy_limit, limiter
from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
from app.models.match import TIER_REFERENCE, Match
from app.models.user import User
from app.schemas.abgleich import (
    AbgleichItem,
    AbgleichResponse,
    AbgleichSummary,
    BankTransactionOut,
    DecisionResponse,
    ManualMatchRequest,
    MatchedDocument,
    StatementImportResponse,
)
from app.schemas.document import DocumentOut
from app.services.abgleich import AbgleichService
from app.services.pdf_parser import extract_transactions_from_pdf
from app.services.receipts import store_receipt

router = APIRouter(prefix="/api/abgleich", tags=["abgleich"])

MAX_STATEMENT_SIZE = 50 * 1024 * 1024


@router.post("/statements", response_model=StatementImportResponse)
@limiter.limit(heavy_limit)
async def import_statement(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> StatementImportResponse:
    """Upload a Kontoauszug: every line becomes a bank transaction, then proposals are refreshed."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Nur PDF-Dateien erlaubt.")
    content = await file.read()
    if len(content) > MAX_STATEMENT_SIZE:
        raise HTTPException(400, "PDF zu gross (max 50MB).")

    statement_key = await asyncio.to_thread(
        store_receipt,
        user.tenant_id,
        filename=file.filename,
        content_type=file.content_type or "application/pdf",
        content=content,
    )
    try:
        rows = await asyncio.to_thread(extract_transactions_from_pdf, io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(422, f"PDF konnte nicht gelesen werden: {exc}") from exc
    if not rows:
        raise HTTPException(422, "Keine Transaktionen gefunden.")

    service = AbgleichService(db, user)
    result = await service.import_rows(rows, statement_key=statement_key)
    proposals = await service.refresh_proposals()
    await db.commit()
    return StatementImportResponse(
        imported=result.imported, duplicates=result.duplicates, proposals=len({m.transaction_id for m in proposals})
    )


@router.get("/", response_model=AbgleichResponse)
async def abgleich_inbox(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AbgleichResponse:
    """Everything the user needs to decide: proposals, then what is left on either side."""
    service = AbgleichService(db, user)
    matches = await service.proposals()
    transactions = {t.id: t for t in await service.open_transactions()}
    documents = {d.id: d for d in await service.open_documents()}

    items: list[AbgleichItem] = []
    grouped: dict[int, list[Match]] = {}
    for match in matches:
        grouped.setdefault(match.transaction_id, []).append(match)

    for transaction_id, group in grouped.items():
        tx = transactions.get(transaction_id)
        if tx is None:
            continue
        docs = [
            MatchedDocument(
                document=DocumentOut.model_validate(documents[m.document_id]),
                match_id=m.id,
                amount=round(float(m.amount or 0.0), 2),
            )
            for m in group
            if m.document_id in documents
        ]
        if not docs:
            continue
        best = max(group, key=lambda m: m.score)
        items.append(
            AbgleichItem(
                transaction=BankTransactionOut.model_validate(tx),
                documents=docs,
                tier=best.tier,
                score=round(float(best.score or 0.0), 3),
                reason=best.reason,
                is_split=len(docs) > 1,
            )
        )
    items.sort(key=lambda i: (-i.score, i.transaction.id))

    matched_tx_ids = {i.transaction.id for i in items}
    matched_doc_ids = {d.document.id for i in items for d in i.documents}
    return AbgleichResponse(
        items=items,
        open_transactions=[
            BankTransactionOut.model_validate(t) for t in transactions.values() if t.id not in matched_tx_ids
        ],
        open_documents=[DocumentOut.model_validate(d) for d in documents.values() if d.id not in matched_doc_ids],
        summary=AbgleichSummary(
            vorschlaege=len(items),
            offene_zeilen=len(transactions) - len(matched_tx_ids),
            offene_dokumente=len(documents) - len(matched_doc_ids),
            exakt=sum(1 for i in items if i.tier == TIER_REFERENCE),
        ),
    )


@router.post("/refresh", response_model=AbgleichSummary)
@limiter.limit(heavy_limit)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> AbgleichSummary:
    service = AbgleichService(db, user)
    matches = await service.refresh_proposals()
    await db.commit()
    open_tx = (
        await db.execute(
            select(func.count(BankTransaction.id)).where(
                BankTransaction.tenant_id == user.tenant_id, BankTransaction.status == TX_STATUS_OFFEN
            )
        )
    ).scalar() or 0
    proposed_tx = {m.transaction_id for m in matches}
    return AbgleichSummary(
        vorschlaege=len(proposed_tx),
        offene_zeilen=int(open_tx) - len(proposed_tx),
        offene_dokumente=len(await service.open_documents()) - len({m.document_id for m in matches}),
        exakt=len({m.transaction_id for m in matches if m.tier == TIER_REFERENCE}),
    )


@router.post("/{transaction_id}/confirm", response_model=DecisionResponse)
async def confirm(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> DecisionResponse:
    service = AbgleichService(db, user)
    group = [m.document_id for m in await service._group(transaction_id)]
    bookings = await service.confirm(transaction_id)
    await db.commit()
    return DecisionResponse(
        transaction_id=transaction_id,
        status="bestaetigt",
        bookings=[b.id for b in bookings],
        documents=group,
    )


@router.post("/{transaction_id}/reject", response_model=DecisionResponse)
async def reject(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> DecisionResponse:
    service = AbgleichService(db, user)
    await service.reject(transaction_id)
    await db.commit()
    return DecisionResponse(transaction_id=transaction_id, status="abgelehnt")


@router.post("/{transaction_id}/manual", response_model=DecisionResponse)
async def manual(
    transaction_id: int,
    body: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> DecisionResponse:
    service = AbgleichService(db, user)
    bookings = await service.manual(transaction_id, body.document_ids)
    await db.commit()
    return DecisionResponse(
        transaction_id=transaction_id,
        status="bestaetigt",
        bookings=[b.id for b in bookings],
        documents=body.document_ids,
    )


@router.post("/{transaction_id}/ignore", response_model=DecisionResponse)
async def ignore(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> DecisionResponse:
    service = AbgleichService(db, user)
    tx = await service.ignore_transaction(transaction_id)
    await db.commit()
    return DecisionResponse(transaction_id=tx.id, status="ignoriert")

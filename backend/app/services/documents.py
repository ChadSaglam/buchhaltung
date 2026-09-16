"""Document ingestion — one file in, one Document row out (brainstorm phase 1).

Order of truth: Swiss QR-bill (exact) → vision/OCR via ScannerService (guess).
Whatever was read is classified with the tenant's own learners so the row
already carries a proposed Kontierung. Nothing is booked here; that is the
Abgleich (phase 3) or an explicit "buchen".
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import KIND_RECHNUNG, STATUS_FEHLER, STATUS_OFFEN, Document
from app.models.user import User
from app.services.classifier import TenantClassifier
from app.services.plan_limits import PlanLimits
from app.services.qr_bill import QrBill, invoice_number_from_message, read_qr_bill
from app.services.receipts import store_receipt
from app.services.scanner.scanner_service import ScannerService
from app.services.storage_quota import StorageQuota
from app.services.usage_meter import UsageMeter

logger = logging.getLogger(__name__)

_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y")


def parse_date(text: str | None) -> date | None:
    text = (text or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _clean_vendor(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip()[:255]


class DocumentService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user

    async def ingest(self, *, filename: str, content_type: str, content: bytes) -> Document:
        """Store the file, read it (QR first), classify, persist. Never raises for a bad document —
        the row is created with status ``fehler`` so the user sees *which* file failed."""
        ScannerService(self.db, self.user)._validate_upload(content_type=content_type, content=content)
        # B-54: the file is kept whether or not it can be read, so the tenant's
        # quota decides before anything is written. B-23 adds the second
        # ceiling — how many receipts the plan includes this month.
        limits = PlanLimits(self.user.tenant_id, self.db)
        await limits.ensure("belege")
        quota = StorageQuota(self.user.tenant_id, self.db)
        await quota.ensure_room_for(len(content))
        file_key = await asyncio.to_thread(
            store_receipt, self.user.tenant_id, filename=filename, content_type=content_type, content=content
        )
        await quota.record(len(content))
        await UsageMeter(self.user.tenant_id, self.db).record("beleg")
        doc = Document(
            tenant_id=self.user.tenant_id,
            kind=KIND_RECHNUNG,
            status=STATUS_OFFEN,
            file_key=file_key,
            filename=filename[:255],
            uploaded_by=self.user.id,
            # Column defaults apply on INSERT; the row is read before that.
            vendor="",
            currency="CHF",
            invoice_no="",
            qr_iban="",
            qr_reference="",
            qr_message="",
            extraction_source="",
            extraction_confidence=0.0,
            kt_soll="",
            kt_haben="",
            mwst_code="",
            mwst_pct="",
            classification_confidence=0.0,
            error="",
            raw_json="",
        )

        bill = await asyncio.to_thread(read_qr_bill, content, content_type)
        raw: dict[str, Any] = {}
        if bill:
            self._apply_qr(doc, bill)
            raw["qr"] = bill.__dict__ | {"raw": None}
        else:
            try:
                extracted = await ScannerService(self.db, self.user).extract(
                    file_name=filename,
                    content_type=content_type,
                    content=content,
                    # Der Beleg liegt schon (oben), mit Quote und Zähler. Ohne das
                    # hier wurde jede Rechnung ohne QR-Code zweimal abgelegt.
                    bereits_gespeichert=file_key,
                )
                data = extracted.data.model_dump()
                self._apply_extracted(doc, data)
                raw["scanner"] = {k: v for k, v in data.items() if k not in {"scanner_steps", "scanner_attempts"}}
            except HTTPException as exc:
                doc.status = STATUS_FEHLER
                doc.error = str(exc.detail)[:255]

        if doc.status != STATUS_FEHLER:
            await self._classify(doc)
        doc.raw_json = json.dumps(raw, ensure_ascii=False, default=str)[:20000]
        self.db.add(doc)
        await self.db.flush()
        return doc

    def _apply_qr(self, doc: Document, bill: QrBill) -> None:
        doc.vendor = _clean_vendor(bill.creditor_name)
        doc.amount = bill.amount
        doc.currency = (bill.currency or "CHF")[:3]
        doc.qr_iban = bill.iban
        doc.qr_reference = bill.reference
        doc.qr_message = bill.message[:140]
        doc.invoice_no = invoice_number_from_message(bill.message)[:100]
        doc.extraction_source = "qr"
        doc.extraction_confidence = 1.0

    def _apply_extracted(self, doc: Document, data: dict[str, Any]) -> None:
        doc.vendor = _clean_vendor(str(data.get("vendor") or ""))
        amount = data.get("total_amount")
        doc.amount = float(amount) if amount not in (None, "", 0, 0.0) else None
        doc.invoice_no = str(data.get("invoice_number") or "")[:100]
        doc.invoice_date = parse_date(str(data.get("date") or ""))
        doc.extraction_source = "ocr" if data.get("ocr_worked") else "vision"
        doc.extraction_confidence = 0.6 if doc.vendor and doc.amount else 0.3
        if data.get("needs_review"):
            doc.error = str(data.get("review_reason") or "")[:255]
        # The scanner already classified; keep it unless the classifier below is more confident.
        doc.kt_soll = str(data.get("kt_soll") or "")
        doc.kt_haben = str(data.get("kt_haben") or "")
        doc.mwst_code = str(data.get("mwst_code") or "")
        doc.mwst_pct = str(data.get("mwst_pct") or "")
        doc.classification_confidence = float(data.get("classification_confidence") or 0.0)

    async def _classify(self, doc: Document) -> None:
        text = " ".join(p for p in (doc.vendor, doc.qr_message) if p).strip()
        if not text:
            return
        result = await TenantClassifier(self.user.tenant_id, self.db).classify(text, False, doc.amount or 0.0)
        if result.confidence >= (doc.classification_confidence or 0.0):
            doc.kt_soll = result.kt_soll
            doc.kt_haben = result.kt_haben
            doc.mwst_code = result.mwst_code
            doc.mwst_pct = result.mwst_pct
            doc.classification_confidence = result.confidence

"""Offene Posten + Mahnung (B-65).

Two questions the owner asks every week: *wer schuldet uns* (Debitoren) and
*was schulden wir* (Kreditoren). Both live in `documents`; the direction says
which side a document is on. Only our own invoice to a customer can be gemahnt,
and the Mahnung is always a **draft** — the owner reads it before it goes out.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import (
    DIRECTION_AUSGANG,
    MAX_MAHNSTUFE,
    STATUS_OFFEN,
    Document,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.export import fmt_swiss, round_chf

logger = logging.getLogger(__name__)

# No payment term on the invoice → Swiss default of 30 days net.
DEFAULT_TERMS_DAYS = 30
# Days the Mahnung gives the customer to pay.
MAHNUNG_FRIST_DAYS = 10

BUCKET_OFFEN = "nicht_faellig"
BUCKET_1_30 = "1_30"
BUCKET_31_60 = "31_60"
BUCKET_61_90 = "61_90"
BUCKET_OVER_90 = "ueber_90"
BUCKETS = (BUCKET_OFFEN, BUCKET_1_30, BUCKET_31_60, BUCKET_61_90, BUCKET_OVER_90)

STUFE_LABEL = {
    1: "Zahlungserinnerung",
    2: "1. Mahnung",
    3: "Letzte Mahnung",
}


def today_utc() -> date:
    return datetime.now(UTC).date()


def effective_due_date(doc: Document, terms_days: int = DEFAULT_TERMS_DAYS) -> date | None:
    """The due date on the invoice, or invoice date + payment term when it is missing."""
    if doc.due_date:
        return doc.due_date
    if doc.invoice_date:
        return doc.invoice_date + timedelta(days=terms_days)
    return None


def days_overdue(doc: Document, today: date | None = None) -> int:
    """Whole days past the due date; 0 while it is not due (or unknown)."""
    due = effective_due_date(doc)
    if due is None:
        return 0
    delta = (today or today_utc()) - due
    return max(0, delta.days)


def aging_bucket(days: int) -> str:
    if days <= 0:
        return BUCKET_OFFEN
    if days <= 30:
        return BUCKET_1_30
    if days <= 60:
        return BUCKET_31_60
    if days <= 90:
        return BUCKET_61_90
    return BUCKET_OVER_90


def next_mahnstufe(doc: Document) -> int:
    """Escalate by one, never past the last stage."""
    return min(MAX_MAHNSTUFE, int(doc.mahnstufe or 0) + 1)


def mahnstufe_label(stufe: int) -> str:
    return STUFE_LABEL.get(stufe, STUFE_LABEL[MAX_MAHNSTUFE])


def _swiss(day: date | None) -> str:
    return day.strftime("%d.%m.%Y") if day else "—"


def _invoice_line(doc: Document, due: date | None) -> str:
    parts = [f"Rechnung {doc.invoice_no}" if doc.invoice_no else "Rechnung"]
    if doc.invoice_date:
        parts.append(f"vom {_swiss(doc.invoice_date)}")
    parts.append(f"über CHF {fmt_swiss(doc.amount or 0.0)}")
    parts.append(f"(fällig am {_swiss(due)})")
    return " ".join(parts)


def mahnung_subject(doc: Document, stufe: int) -> str:
    label = mahnstufe_label(stufe)
    return f"{label}: Rechnung {doc.invoice_no}" if doc.invoice_no else label


def mahnung_text(
    doc: Document,
    stufe: int,
    *,
    company: str = "",
    today: date | None = None,
    terms_days: int = DEFAULT_TERMS_DAYS,
) -> str:
    """The e-mail body — plain German, escalating in tone, never threatening in stage 1."""
    day = today or today_utc()
    due = effective_due_date(doc, terms_days)
    overdue = days_overdue(doc, day)
    frist = day + timedelta(days=MAHNUNG_FRIST_DAYS)
    invoice = _invoice_line(doc, due)
    greeting = f"Guten Tag{'' if not doc.vendor else f' {doc.vendor}'}"

    if stufe <= 1:
        middle = [
            f"unsere {invoice} ist noch offen.",
            "Vermutlich ist die Zahlung untergegangen — bitte prüfen Sie das kurz.",
            f"Wir bitten Sie um Überweisung bis am {_swiss(frist)}.",
        ]
    elif stufe == 2:
        middle = [
            f"trotz unserer Zahlungserinnerung ist unsere {invoice} weiterhin offen ({overdue} Tage überfällig).",
            f"Bitte überweisen Sie den Betrag bis am {_swiss(frist)}.",
        ]
    else:
        middle = [
            f"unsere {invoice} ist trotz Mahnung noch nicht bezahlt ({overdue} Tage überfällig).",
            f"Wir setzen Ihnen eine letzte Frist bis am {_swiss(frist)}.",
            "Danach müssen wir den Betrag inklusive Verzugszins (Art. 104 OR) auf dem Betreibungsweg"
            " einfordern, was wir gerne vermeiden.",
        ]

    lines = [
        f"{greeting}",
        "",
        *middle,
        "",
        "Falls die Zahlung bereits unterwegs ist, betrachten Sie dieses Schreiben als gegenstandslos.",
        "",
        "Freundliche Grüsse",
        company or "",
    ]
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def mahnung_html(
    doc: Document,
    stufe: int,
    *,
    company: str = "",
    today: date | None = None,
    terms_days: int = DEFAULT_TERMS_DAYS,
) -> str:
    """A print-ready A4 page — the owner prints it to PDF from the browser."""
    day = today or today_utc()
    due = effective_due_date(doc, terms_days)
    body = mahnung_text(doc, stufe, company=company, today=day, terms_days=terms_days)
    paragraphs = "".join(
        f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>" for block in body.split("\n\n") if block.strip()
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>{html.escape(mahnung_subject(doc, stufe))}</title>
<style>
  @page {{ size: A4; margin: 25mm 20mm; }}
  body {{ font: 11pt/1.55 "Helvetica Neue", Arial, sans-serif; color: #111; max-width: 17cm; margin: 0 auto; }}
  header {{ display: flex; justify-content: space-between; font-size: 10pt; color: #444; }}
  h1 {{ font-size: 14pt; margin: 2.5rem 0 1.5rem; }}
  table {{ border-collapse: collapse; margin: 1.5rem 0; font-size: 10pt; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 6px 14px 6px 0; text-align: left; }}
  .betrag {{ font-weight: 600; }}
  footer {{ margin-top: 3rem; font-size: 9pt; color: #666; }}
  @media print {{ .noprint {{ display: none; }} }}
</style></head><body>
<header><span>{html.escape(company or "")}</span><span>{_swiss(day)}</span></header>
<p>{html.escape(doc.vendor or "")}</p>
<h1>{html.escape(mahnung_subject(doc, stufe))}</h1>
{paragraphs}
<table>
  <tr><th>Rechnung</th><td>{html.escape(doc.invoice_no or "—")}</td></tr>
  <tr><th>Rechnungsdatum</th><td>{_swiss(doc.invoice_date)}</td></tr>
  <tr><th>Fällig am</th><td>{_swiss(due)}</td></tr>
  <tr><th>Betrag</th><td class="betrag">CHF {fmt_swiss(doc.amount or 0.0)}</td></tr>
</table>
<footer class="noprint">Entwurf — bitte vor dem Versand prüfen. Drucken oder als PDF speichern: Strg/Cmd + P.</footer>
</body></html>
"""


def mahnung_pdf(
    doc: Document,
    stufe: int,
    *,
    company: str = "",
    company_address: str = "",
    today: date | None = None,
    terms_days: int = DEFAULT_TERMS_DAYS,
) -> bytes:
    """The Mahnung as a file. It is a letter that gets posted — "print the page"
    was never the right answer for the one document that leaves the building on
    paper. Same text as :func:`mahnung_html`, which stays the browser preview.
    """
    from app.services.pdf_render import CONTENT_WIDTH, Column, Meta, PdfDoc, Row, latin1

    day = today or today_utc()
    due = effective_due_date(doc, terms_days)
    body = mahnung_text(doc, stufe, company=company, today=day, terms_days=terms_days)

    document = PdfDoc(
        Meta(
            title=mahnung_subject(doc, stufe),
            company=company,
            company_address=company_address,
            period=_swiss(day),
            # A Mahnung is one page and goes in an envelope; a page number on it
            # only raises the question of what the second page said.
            footer="Entwurf - bitte vor dem Versand prüfen.",
            page_numbers=False,
        )
    )
    pdf = document.pdf

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.cell(0, 5, latin1(doc.vendor or ""), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        pdf.set_font("Helvetica", "", 10.5)
        for line in block.split("\n"):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(CONTENT_WIDTH, 5.2, latin1(line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    document.section("Die offene Rechnung")
    document.table(
        [Column("Position", 55.0, "L"), Column("", CONTENT_WIDTH - 55.0, "L")],
        [
            Row(["Rechnung", doc.invoice_no or "-"]),
            Row(["Rechnungsdatum", _swiss(doc.invoice_date)]),
            Row(["Fällig am", _swiss(due)]),
            Row(["Betrag CHF", fmt_swiss(doc.amount or 0.0)], bold=True, top_line=True),
        ],
    )
    return document.output()


def mahnung_dateiname(doc: Document, stufe: int) -> str:
    """`Mahnung-2-2026-0001.pdf` — recognisable in a folder of letters."""
    nummer = (doc.invoice_no or str(doc.id)).replace("/", "-").replace(" ", "-")
    return f"Mahnung-{stufe}-{nummer}.pdf"


@dataclass
class OpenItem:
    document: Document
    due_date: date | None
    days_overdue: int
    bucket: str
    mahnbar: bool


@dataclass
class Side:
    """One side of the ledger — Debitoren (they owe us) or Kreditoren (we owe)."""

    items: list[OpenItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def total(self) -> float:
        return float(round_chf(sum(float(i.document.amount or 0.0) for i in self.items)))

    @property
    def overdue_count(self) -> int:
        return sum(1 for i in self.items if i.days_overdue > 0)

    @property
    def overdue_total(self) -> float:
        return float(round_chf(sum(float(i.document.amount or 0.0) for i in self.items if i.days_overdue > 0)))

    def buckets(self) -> dict[str, float]:
        out = dict.fromkeys(BUCKETS, 0.0)
        for item in self.items:
            out[item.bucket] += float(item.document.amount or 0.0)
        return {k: float(round_chf(v)) for k, v in out.items()}


def build_items(docs: list[Document], today: date | None = None) -> list[OpenItem]:
    """Most urgent first: longest overdue, then the earliest due date."""
    day = today or today_utc()
    items = [
        OpenItem(
            document=doc,
            due_date=effective_due_date(doc),
            days_overdue=days_overdue(doc, day),
            bucket=aging_bucket(days_overdue(doc, day)),
            mahnbar=doc.direction == DIRECTION_AUSGANG and days_overdue(doc, day) > 0,
        )
        for doc in docs
    ]
    items.sort(key=lambda i: (-i.days_overdue, i.due_date or date.max, i.document.id))
    return items


class OffenePostenService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    async def _company(self) -> str:
        tenant = (await self.db.execute(select(Tenant).where(Tenant.id == self.tenant_id))).scalar_one_or_none()
        return getattr(tenant, "name", "") or ""

    async def company_address(self) -> str:
        """The sender line for the letterhead, from the Firmenprofil (B-68) if there is one."""
        from app.models.company_profile import CompanyProfile
        from app.services.swiss_qr import Party

        row = await self.db.execute(select(CompanyProfile).where(CompanyProfile.tenant_id == self.tenant_id))
        profile = row.scalar_one_or_none()
        if profile is None:
            return ""
        return Party(
            name=profile.name,
            strasse=profile.strasse,
            hausnummer=profile.hausnummer,
            plz=profile.plz,
            ort=profile.ort,
        ).address_line()

    async def _own_document(self, document_id: int) -> Document:
        row = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == self.tenant_id)
        )
        doc = row.scalar_one_or_none()
        if doc is None:
            raise HTTPException(404, "Dokument nicht gefunden.")
        return doc

    async def open_documents(self) -> list[Document]:
        """Documents that are actually owed — B-89.

        ``status == 'offen'`` means *not yet matched to a bank line*, which is
        true of a fuel receipt paid by card at the till. This list answers a
        different question ("wer schuldet uns / was schulden wir"), so it also
        requires that the money has not already left the account.
        """
        rows = await self.db.execute(
            select(Document).where(
                Document.tenant_id == self.tenant_id,
                Document.status == STATUS_OFFEN,
                Document.paid_at_source.is_(False),
            )
        )
        return list(rows.scalars().all())

    async def overview(self, today: date | None = None) -> tuple[Side, Side]:
        docs = await self.open_documents()
        items = build_items(docs, today)
        debitoren = Side([i for i in items if i.document.direction == DIRECTION_AUSGANG])
        kreditoren = Side([i for i in items if i.document.direction != DIRECTION_AUSGANG])
        return debitoren, kreditoren

    async def draft(self, document_id: int, stufe: int | None = None, today: date | None = None):
        """The Mahnung as it would go out — nothing is stored and nothing is sent."""
        doc = await self._own_document(document_id)
        if doc.direction != DIRECTION_AUSGANG:
            raise HTTPException(409, "Eine Mahnung gibt es nur für eigene Rechnungen an Kunden (Debitoren).")
        if doc.status != STATUS_OFFEN:
            raise HTTPException(409, "Diese Rechnung ist nicht mehr offen.")
        level = max(1, min(MAX_MAHNSTUFE, stufe or next_mahnstufe(doc)))
        company = await self._company()
        return doc, level, company

    async def record_mahnung(self, document_id: int, stufe: int | None = None, today: date | None = None):
        """The owner sent it — remember the stage so the next one escalates."""
        doc, level, company = await self.draft(document_id, stufe, today)
        doc.mahnstufe = level
        doc.mahnung_sent_at = datetime.now(UTC)
        await self.db.flush()
        logger.info("mahnung stufe %s recorded for document %s", level, doc.id)
        return doc, level, company

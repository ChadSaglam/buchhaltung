"""Rechnungen schreiben — Debitorenrechnung mit Swiss QR (B-68).

The loop closes here. Until now the system only ever *read* invoices; now it
writes one: customer + positions → a QR-Rechnung the customer can scan, a
Debitorenbuchung ``1100/3000`` on the day it is written, and a reference that
comes back on the bank statement, where phase 3 matches it and books the payment
``1020/1100`` without anybody typing anything.

The invoice header is a ``Document`` with ``direction = ausgang`` — that is what
puts it in Offene Posten, gives it the Mahnung ladder and feeds the Abgleich.
"""

from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.company_profile import CompanyProfile
from app.models.document import (
    DIRECTION_AUSGANG,
    KIND_RECHNUNG,
    STATUS_OFFEN,
    Document,
)
from app.models.invoice_position import InvoicePosition
from app.models.tenant import Tenant
from app.models.user import User
from app.services import swiss_qr
from app.services.export import fmt_swiss, round_chf
from app.services.offene_posten import today_utc

logger = logging.getLogger(__name__)

SOURCE_EIGEN = "eigen"
BOOKING_SOURCE = "rechnung"
MAX_POSITIONS = 60


@dataclass
class PositionInput:
    bezeichnung: str
    menge: float = 1.0
    einheit: str = ""
    einzelpreis: float = 0.0

    @property
    def betrag(self) -> float:
        return float(round_chf(float(self.menge or 0.0) * float(self.einzelpreis or 0.0)))


@dataclass
class Totals:
    netto: float
    mwst: float
    brutto: float
    mwst_pct: float


def totals_for(positions: list[PositionInput], mwst_pct: str) -> Totals:
    """Net from the lines, VAT on top, gross as the amount that is actually owed.

    Prices are net (the Swiss B2B default). The booking then carries the gross
    amount and the VAT code, which is how every other booking in this system —
    and Banana — expresses it.
    """
    netto = float(round_chf(sum(p.betrag for p in positions)))
    try:
        rate = abs(float(mwst_pct or 0.0))
    except ValueError:
        rate = 0.0
    if not rate:
        return Totals(netto=netto, mwst=0.0, brutto=netto, mwst_pct=0.0)
    brutto = float(round_chf(netto * (100 + rate) / 100))
    return Totals(netto=netto, mwst=float(round_chf(brutto - netto)), brutto=brutto, mwst_pct=rate)


def _swiss_date(day: date | None) -> str:
    return day.strftime("%d.%m.%Y") if day else "—"


class RechnungService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # ── Firmenprofil ─────────────────────────────────────────────────────────

    async def profile(self) -> CompanyProfile:
        """The tenant's own data — created empty on first use, never shared."""
        row = await self.db.execute(select(CompanyProfile).where(CompanyProfile.tenant_id == self.tenant_id))
        profile = row.scalar_one_or_none()
        if profile is None:
            tenant = (await self.db.execute(select(Tenant).where(Tenant.id == self.tenant_id))).scalar_one_or_none()
            profile = CompanyProfile(tenant_id=self.tenant_id, name=getattr(tenant, "name", "") or "")
            self.db.add(profile)
            await self.db.flush()
        return profile

    #: Nullable columns a PUT may set back to "not given" (B-71). Every other
    #: field keeps its value when null arrives, so a partial update cannot blank it.
    CLEARABLE = frozenset({"gewinnsteuer_satz"})

    async def update_profile(self, data: dict) -> CompanyProfile:
        profile = await self.profile()
        for field, value in data.items():
            if not hasattr(profile, field):
                continue
            if value is None and field not in self.CLEARABLE:
                continue
            setattr(profile, field, value)
        if profile.iban and not swiss_qr.is_valid_iban(profile.iban):
            raise HTTPException(400, "Diese IBAN ist keine gültige Schweizer oder Liechtensteiner IBAN.")
        profile.iban = swiss_qr.normalize_iban(profile.iban)
        await self.db.flush()
        return profile

    def profile_ready(self, profile: CompanyProfile) -> list[str]:
        """What is still missing before a QR-Rechnung can be written."""
        missing: list[str] = []
        if not (profile.name or "").strip():
            missing.append("Firmenname")
        if not swiss_qr.is_valid_iban(profile.iban):
            missing.append("IBAN")
        if not (profile.plz or "").strip() or not (profile.ort or "").strip():
            missing.append("Adresse (PLZ und Ort)")
        return missing

    # ── Rechnungsnummer ──────────────────────────────────────────────────────

    async def next_invoice_no(self, day: date | None = None) -> str:
        """``JJJJ-NNNN``, continuous per tenant and year — gaps would look like lost invoices."""
        year = (day or today_utc()).year
        prefix = f"{year}-"
        rows = await self.db.execute(
            select(func.max(Document.invoice_no)).where(
                Document.tenant_id == self.tenant_id,
                Document.direction == DIRECTION_AUSGANG,
                Document.invoice_no.like(f"{prefix}%"),
            )
        )
        highest = rows.scalar_one_or_none() or ""
        try:
            number = int(highest.split("-", 1)[1]) + 1
        except (IndexError, ValueError):
            number = 1
        return f"{prefix}{number:04d}"

    # ── Schreiben ────────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        kunde: swiss_qr.Party,
        kunde_email: str = "",
        positions: list[PositionInput],
        invoice_date: date | None = None,
        due_date: date | None = None,
        bemerkung: str = "",
    ) -> tuple[Document, list[InvoicePosition], Booking]:
        positions = [p for p in positions if (p.bezeichnung or "").strip()]
        if not positions:
            raise HTTPException(400, "Eine Rechnung braucht mindestens eine Position.")
        if len(positions) > MAX_POSITIONS:
            raise HTTPException(400, f"Höchstens {MAX_POSITIONS} Positionen pro Rechnung.")
        if not kunde.filled:
            raise HTTPException(400, "Der Kundenname fehlt.")

        profile = await self.profile()
        missing = self.profile_ready(profile)
        if missing:
            raise HTTPException(409, f"Firmenprofil unvollständig: {', '.join(missing)} in den Einstellungen ergänzen.")

        totals = totals_for(positions, profile.mwst_pct)
        if totals.brutto <= 0:
            raise HTTPException(400, "Der Rechnungsbetrag muss grösser als 0 sein.")

        day = invoice_date or today_utc()
        due = due_date or day + timedelta(days=int(profile.zahlungsfrist_tage or 30))
        invoice_no = await self.next_invoice_no(day)

        doc = Document(
            tenant_id=self.tenant_id,
            kind=KIND_RECHNUNG,
            status=STATUS_OFFEN,
            direction=DIRECTION_AUSGANG,
            file_key="",
            filename=f"Rechnung {invoice_no}.html",
            vendor=kunde.name,
            amount=totals.brutto,
            currency="CHF",
            invoice_no=invoice_no,
            invoice_date=day,
            due_date=due,
            qr_iban=swiss_qr.normalize_iban(profile.iban),
            qr_message=f"Rechnung {invoice_no}",
            extraction_source=SOURCE_EIGEN,
            extraction_confidence=1.0,
            # The *payment* leg, for the Abgleich: money in on the bank account
            # settles the Debitor. The revenue and its VAT are booked below, today.
            kt_soll=profile.konto_bank,
            kt_haben=profile.konto_debitoren,
            classification_confidence=1.0,
            contact_email=kunde_email or "",
            uploaded_by=self.user.id,
        )
        self.db.add(doc)
        await self.db.flush()  # the reference is built from the id

        reference_type, reference = swiss_qr.reference_for(
            profile.iban, tenant_id=self.tenant_id, document_id=doc.id, invoice_no=invoice_no
        )
        doc.qr_reference = reference
        doc.raw_json = json.dumps(
            {
                "quelle": "b-68",
                "referenz_typ": reference_type,
                "bemerkung": bemerkung,
                "kunde": {
                    "name": kunde.name,
                    "strasse": kunde.strasse,
                    "hausnummer": kunde.hausnummer,
                    "plz": kunde.plz,
                    "ort": kunde.ort,
                    "land": kunde.land,
                },
                "totals": {"netto": totals.netto, "mwst": totals.mwst, "brutto": totals.brutto},
            },
            ensure_ascii=False,
        )

        rows = [
            InvoicePosition(
                tenant_id=self.tenant_id,
                document_id=doc.id,
                position=index,
                bezeichnung=p.bezeichnung.strip()[:255],
                menge=float(p.menge or 0.0),
                einheit=(p.einheit or "").strip()[:20],
                einzelpreis=float(p.einzelpreis or 0.0),
            )
            for index, p in enumerate(positions, start=1)
        ]
        self.db.add_all(rows)

        booking = Booking(
            tenant_id=self.tenant_id,
            datum=_swiss_date(day),
            beschreibung=f"Rechnung {invoice_no} {kunde.name}".strip(),
            betrag=totals.brutto,
            kt_soll=profile.konto_debitoren,
            kt_haben=profile.konto_ertrag,
            mwst_code=profile.mwst_code if totals.mwst else "",
            mwst_pct=profile.mwst_pct if totals.mwst else "",
            mwst_amount=totals.mwst,
            rechnung=invoice_no,
            source=BOOKING_SOURCE,
        )
        self.db.add(booking)
        await self.db.flush()
        logger.info(
            "rechnung %s written: %s CHF, reference %s (%s)",
            invoice_no,
            totals.brutto,
            reference or "—",
            reference_type,
        )
        return doc, rows, booking

    # ── Lesen ────────────────────────────────────────────────────────────────

    async def own_invoice(self, document_id: int) -> tuple[Document, list[InvoicePosition]]:
        row = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == self.tenant_id)
        )
        doc = row.scalar_one_or_none()
        if doc is None or doc.direction != DIRECTION_AUSGANG:
            raise HTTPException(404, "Rechnung nicht gefunden.")
        rows = await self.db.execute(
            select(InvoicePosition)
            .where(InvoicePosition.tenant_id == self.tenant_id, InvoicePosition.document_id == doc.id)
            .order_by(InvoicePosition.position)
        )
        return doc, list(rows.scalars().all())

    async def list_invoices(self, limit: int = 100) -> list[Document]:
        rows = await self.db.execute(
            select(Document)
            .where(Document.tenant_id == self.tenant_id, Document.direction == DIRECTION_AUSGANG)
            .order_by(Document.id.desc())
            .limit(max(1, min(limit, 500)))
        )
        return list(rows.scalars().all())

    async def payload(self, document_id: int) -> tuple[Document, list[InvoicePosition], CompanyProfile, str]:
        doc, positions = await self.own_invoice(document_id)
        profile = await self.profile()
        kunde = _kunde_from(doc)
        reference_type = _reference_type(doc)
        payload = swiss_qr.build_payload(
            iban=profile.iban,
            creditor=swiss_qr.Party(
                name=profile.name,
                strasse=profile.strasse,
                hausnummer=profile.hausnummer,
                plz=profile.plz,
                ort=profile.ort,
                land=profile.land or "CH",
            ),
            amount=doc.amount,
            currency=doc.currency or "CHF",
            reference_type=reference_type,
            reference=doc.qr_reference,
            message="" if reference_type == swiss_qr.REFERENCE_QRR else doc.qr_message,
            debtor=kunde,
        )
        return doc, positions, profile, payload

    async def html(self, document_id: int) -> str:
        doc, positions, profile, payload = await self.payload(document_id)
        return invoice_html(doc, positions, profile, payload)

    async def pdf(self, document_id: int) -> bytes:
        """The file a customer gets. `html()` stays the browser preview (B-79)."""
        from app.services.rechnung_pdf import invoice_pdf

        doc, positions, profile, payload = await self.payload(document_id)
        totals = _raw(doc).get("totals") or {}
        return invoice_pdf(
            doc,
            positions,
            profile,
            payload,
            kunde=_kunde_from(doc),
            reference=swiss_qr.format_reference(doc.qr_reference, _reference_type(doc)),
            netto=float(totals.get("netto") or doc.amount or 0.0),
            mwst=float(totals.get("mwst") or 0.0),
        )

    def dateiname(self, doc: Document) -> str:
        """`Rechnung-2026-0001.pdf` — what the customer sees in their inbox."""
        nummer = (doc.invoice_no or str(doc.id)).replace("/", "-").replace(" ", "-")
        return f"Rechnung-{nummer}.pdf"


def _raw(doc: Document) -> dict:
    try:
        data = json.loads(doc.raw_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _kunde_from(doc: Document) -> swiss_qr.Party:
    kunde = _raw(doc).get("kunde") or {}
    return swiss_qr.Party(
        name=kunde.get("name") or doc.vendor or "",
        strasse=kunde.get("strasse", ""),
        hausnummer=kunde.get("hausnummer", ""),
        plz=kunde.get("plz", ""),
        ort=kunde.get("ort", ""),
        land=kunde.get("land", "CH") or "CH",
    )


def _reference_type(doc: Document) -> str:
    stored = _raw(doc).get("referenz_typ")
    if stored in (swiss_qr.REFERENCE_QRR, swiss_qr.REFERENCE_SCOR, swiss_qr.REFERENCE_NON):
        return stored
    if swiss_qr.is_valid_qrr(doc.qr_reference):
        return swiss_qr.REFERENCE_QRR
    return swiss_qr.REFERENCE_SCOR if doc.qr_reference else swiss_qr.REFERENCE_NON


def _e(text: str | None) -> str:
    return html.escape(text or "")


def invoice_html(
    doc: Document,
    positions: list[InvoicePosition],
    profile: CompanyProfile,
    payload: str,
) -> str:
    """A print-ready A4 invoice with the payment part at the bottom (Strg/Cmd + P → PDF)."""
    kunde = _kunde_from(doc)
    raw_totals = _raw(doc).get("totals") or {}
    netto = float(raw_totals.get("netto") or doc.amount or 0.0)
    mwst = float(raw_totals.get("mwst") or 0.0)
    brutto = float(doc.amount or 0.0)
    try:
        rate = abs(float(profile.mwst_pct or 0.0))
    except ValueError:
        rate = 0.0

    rows = "".join(
        f"<tr><td>{p.position}</td><td>{_e(p.bezeichnung)}</td>"
        f'<td class="num">{fmt_swiss(p.menge)}{(" " + _e(p.einheit)) if p.einheit else ""}</td>'
        f'<td class="num">{fmt_swiss(p.einzelpreis)}</td>'
        f'<td class="num">{fmt_swiss(round(float(p.menge or 0) * float(p.einzelpreis or 0), 2))}</td></tr>'
        for p in positions
    )
    mwst_row = f'<tr><th scope="row">MWST {rate:.1f} %</th><td class="num">{fmt_swiss(mwst)}</td></tr>' if mwst else ""
    kontakt = " · ".join(p for p in (profile.email, profile.telefon, profile.mwst_nr) if p)
    reference_type = _reference_type(doc)
    reference = swiss_qr.format_reference(doc.qr_reference, reference_type)
    konto_block = f"{swiss_qr.format_iban(profile.iban)}<br>{_e(profile.name)}<br>{_e(swiss_qr.Party(strasse=profile.strasse, hausnummer=profile.hausnummer, plz=profile.plz, ort=profile.ort).address_line())}"
    kunde_block = f"{_e(kunde.name)}<br>{_e(kunde.address_line())}" if kunde.address_line() else _e(kunde.name)

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>Rechnung {_e(doc.invoice_no)}</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ font: 10pt/1.5 "Helvetica Neue", Arial, sans-serif; color: #111; margin: 0; }}
  .seite {{ width: 210mm; min-height: 297mm; margin: 0 auto; display: flex; flex-direction: column; }}
  .brief {{ flex: 1; padding: 20mm 20mm 8mm; }}
  .kopf {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10mm; }}
  .kopf .firma {{ font-weight: 600; }}
  .kontakt {{ font-size: 8.5pt; color: #555; }}
  .adresse {{ margin: 22mm 0 10mm; }}
  h1 {{ font-size: 15pt; margin: 0 0 2mm; }}
  .meta {{ font-size: 9pt; color: #444; margin-bottom: 8mm; }}
  table.positionen {{ width: 100%; border-collapse: collapse; }}
  table.positionen th {{ text-align: left; font-size: 8.5pt; text-transform: uppercase;
    letter-spacing: .04em; color: #555; border-bottom: 1px solid #333; padding: 0 0 2mm; }}
  table.positionen td {{ padding: 2mm 0; border-bottom: 1px solid #e5e5e5; vertical-align: top; }}
  .num {{ text-align: right; white-space: nowrap; }}
  table.summen {{ margin-left: auto; margin-top: 6mm; border-collapse: collapse; min-width: 70mm; }}
  table.summen th {{ text-align: left; font-weight: 400; padding: 1.5mm 8mm 1.5mm 0; }}
  table.summen tr.total th, table.summen tr.total td {{ font-weight: 700; border-top: 1px solid #333; }}
  .hinweis {{ margin-top: 8mm; font-size: 9pt; }}
  .zahlteil {{ display: flex; height: 105mm; border-top: 1px dashed #666; }}
  .empfangsschein {{ width: 62mm; padding: 5mm; border-right: 1px dashed #666; font-size: 8pt; }}
  .teil {{ flex: 1; padding: 5mm; display: flex; gap: 5mm; font-size: 8pt; }}
  .zahlteil h2 {{ font-size: 11pt; margin: 0 0 3mm; font-weight: 700; }}
  .zahlteil h3 {{ font-size: 6pt; margin: 2.5mm 0 0; font-weight: 700; }}
  .zahlteil p {{ margin: 0; }}
  .qr {{ width: 46mm; }}
  .betragzeile {{ display: flex; gap: 6mm; margin-top: 3mm; }}
  .noprint {{ font-size: 8pt; color: #666; padding: 4mm 20mm; }}
  @media print {{ .noprint {{ display: none; }} }}
</style></head><body>
<div class="seite">
  <div class="brief">
    <div class="kopf">
      <div><p class="firma">{_e(profile.name)}</p>
        <p class="kontakt">{_e(swiss_qr.Party(strasse=profile.strasse, hausnummer=profile.hausnummer, plz=profile.plz, ort=profile.ort).address_line())}</p>
        <p class="kontakt">{_e(kontakt)}</p></div>
      <div class="kontakt">{_swiss_date(doc.invoice_date)}</div>
    </div>
    <div class="adresse"><p>{kunde_block}</p></div>
    <h1>Rechnung {_e(doc.invoice_no)}</h1>
    <p class="meta">Rechnungsdatum {_swiss_date(doc.invoice_date)} · Zahlbar bis {_swiss_date(doc.due_date)}
      {f"· Referenz {_e(reference)}" if reference else ""}</p>
    <table class="positionen">
      <thead><tr><th scope="col">Pos.</th><th scope="col">Bezeichnung</th><th scope="col" class="num">Menge</th>
        <th scope="col" class="num">Einzelpreis</th><th scope="col" class="num">Betrag CHF</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <table class="summen">
      <tr><th scope="row">Zwischentotal</th><td class="num">{fmt_swiss(netto)}</td></tr>
      {mwst_row}
      <tr class="total"><th scope="row">Total CHF</th><td class="num">{fmt_swiss(brutto)}</td></tr>
    </table>
    <p class="hinweis">Zahlbar bis {_swiss_date(doc.due_date)} ohne Abzug.
      Bitte bezahlen Sie mit dem QR-Code unten, damit die Zahlung automatisch zugeordnet wird.</p>
  </div>
  <div class="zahlteil">
    <div class="empfangsschein">
      <h2>Empfangsschein</h2>
      <h3>Konto / Zahlbar an</h3><p>{konto_block}</p>
      {f"<h3>Referenz</h3><p>{_e(reference)}</p>" if reference else ""}
      <h3>Zahlbar durch</h3><p>{kunde_block}</p>
      <div class="betragzeile"><div><h3>Währung</h3><p>{_e(doc.currency or "CHF")}</p></div>
        <div><h3>Betrag</h3><p>{fmt_swiss(brutto)}</p></div></div>
      <h3>Annahmestelle</h3>
    </div>
    <div class="teil">
      <div class="qr">
        <h2>Zahlteil</h2>
        {swiss_qr.qr_svg(payload)}
        <div class="betragzeile"><div><h3>Währung</h3><p>{_e(doc.currency or "CHF")}</p></div>
          <div><h3>Betrag</h3><p>{fmt_swiss(brutto)}</p></div></div>
      </div>
      <div>
        <h3>Konto / Zahlbar an</h3><p>{konto_block}</p>
        {f"<h3>Referenz</h3><p>{_e(reference)}</p>" if reference else ""}
        {f"<h3>Zusätzliche Informationen</h3><p>{_e(doc.qr_message)}</p>" if doc.qr_message else ""}
        <h3>Zahlbar durch</h3><p>{kunde_block}</p>
      </div>
    </div>
  </div>
</div>
<p class="noprint">Drucken oder als PDF speichern: Strg/Cmd + P — Ränder auf „keine“, Hintergrundgrafiken an.</p>
</body></html>
"""

"""Die eigene Rechnung per E-Mail verschicken (B-79).

Der Kreis war bis hierher offen: wir schreiben die Rechnung (B-68), wir können
sie als PDF mit Zahlteil drucken (B-77), aber verschickt wurde sie von Hand.

Zwei Vorsichten stecken im Code:

* **Nichts geht ohne Vorschau raus.** ``GET`` liefert Empfänger, Betreff und
  Text; erst ein ``POST`` verschickt. Genau wie bei der Mahnung (B-65) liest
  der Inhaber, was sein Kunde bekommt.
* **Ein Kundenstamm fehlt noch.** Die Adresse kommt aus dem Dokument selbst —
  ``contact_email`` oder ``raw_json.kunde.email``. Fehlt sie, sagt der Entwurf
  das, statt an eine erfundene Adresse zu schicken.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from app.models.company_profile import CompanyProfile
from app.models.document import Document
from app.services.export import fmt_swiss

logger = logging.getLogger(__name__)

# Deliberately loose: the mail server is the real judge of an address. This
# catches the typo and the empty field, not every RFC 5322 corner.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


def valid_email(value: str | None) -> bool:
    return bool(EMAIL_RE.match((value or "").strip()))


def _raw(doc: Document) -> dict:
    try:
        data = json.loads(doc.raw_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def empfaenger(doc: Document) -> str:
    """Where the invoice goes: the contact on the document, else the customer block."""
    if valid_email(doc.contact_email):
        return doc.contact_email.strip()
    kunde = _raw(doc).get("kunde") or {}
    candidate = str(kunde.get("email") or "").strip()
    return candidate if valid_email(candidate) else ""


def _swiss(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def versand_subject(doc: Document, profile: CompanyProfile) -> str:
    absender = (profile.name or "").strip()
    nummer = (doc.invoice_no or "").strip()
    kopf = f"Rechnung {nummer}" if nummer else "Rechnung"
    return f"{kopf} von {absender}" if absender else kopf


def versand_text(
    doc: Document,
    profile: CompanyProfile,
    *,
    reference: str = "",
    kunde_name: str = "",
) -> str:
    """The mail body — short, German, and it says what the attachment is.

    No sales copy: this is a bill. The one thing it asks for is that the
    customer pays with the QR code, because that is what makes the payment
    match itself later (B-68).
    """
    name = (kunde_name or doc.vendor or "").strip()
    greeting = f"Guten Tag {name}" if name else "Guten Tag"
    betrag = fmt_swiss(doc.amount or 0.0)
    waehrung = (doc.currency or "CHF").upper()

    lines = [
        greeting,
        "",
        f"anbei unsere Rechnung {doc.invoice_no or ''}".rstrip() + f" über {waehrung} {betrag}.",
    ]
    if doc.due_date:
        lines.append(f"Zahlbar bis am {_swiss(doc.due_date)} ohne Abzug.")
    lines += [
        "",
        "Die Rechnung im Anhang enthält einen QR-Zahlteil. Wenn Sie ihn in Ihrer",
        "Banking-App scannen, sind Betrag und Referenz bereits ausgefüllt und die",
        "Zahlung wird bei uns automatisch der Rechnung zugeordnet.",
    ]
    if reference:
        lines += ["", f"Referenz: {reference}"]
    lines += [
        "",
        "Bei Fragen zur Rechnung antworten Sie einfach auf diese E-Mail.",
        "",
        "Freundliche Grüsse",
        (profile.name or "").strip(),
    ]
    kontakt = " · ".join(p for p in ((profile.telefon or "").strip(), (profile.email or "").strip()) if p)
    if kontakt:
        lines.append(kontakt)
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


@dataclass
class VersandEntwurf:
    """What would go out, before anything goes out."""

    document_id: int
    empfaenger: str
    subject: str
    text: str
    dateiname: str
    reply_to: str = ""
    bereit: bool = False
    fehlt: list[str] = field(default_factory=list)
    schon_gesendet_am: str = ""


def entwurf(
    doc: Document,
    profile: CompanyProfile,
    *,
    dateiname: str,
    reference: str = "",
    kunde_name: str = "",
    mail_konfiguriert: bool = True,
) -> VersandEntwurf:
    ziel = empfaenger(doc)
    fehlt: list[str] = []
    if not ziel:
        fehlt.append("E-Mail-Adresse des Kunden")
    if not (profile.name or "").strip():
        fehlt.append("Firmenname im Firmenprofil")
    if not mail_konfiguriert:
        fehlt.append("SMTP-Zugang (SMTP_HOST, SMTP_USER, SMTP_PASSWORD)")

    return VersandEntwurf(
        document_id=doc.id,
        empfaenger=ziel,
        subject=versand_subject(doc, profile),
        text=versand_text(doc, profile, reference=reference, kunde_name=kunde_name),
        dateiname=dateiname,
        reply_to=(profile.email or "").strip(),
        bereit=not fehlt,
        fehlt=fehlt,
        schon_gesendet_am=doc.sent_at.strftime("%d.%m.%Y %H:%M") if doc.sent_at else "",
    )

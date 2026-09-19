"""Swiss QR-bill (Swiss Payments Code) — decode from an image or PDF and parse.

A QR-bill carries the exact facts an invoice matcher needs: creditor IBAN,
amount, currency, and a QRR (27-digit) or SCOR (ISO 11649) reference. Decoding
it is deterministic; vision/OCR only has to cover invoices without one.
Spec: SIX "Swiss Payment Standards — Implementation Guidelines QR-bill" v2.x.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SPC_MAGIC = "SPC"
_MAX_PDF_PAGES = 2
_PDF_SCALE = 200 / 72  # 200 dpi is enough for the 46 mm code on an A4/A5 payment part


@dataclass
class QrBill:
    iban: str
    creditor_name: str
    amount: float | None
    currency: str
    reference_type: str  # QRR | SCOR | NON
    reference: str
    message: str = ""
    creditor_address: str = ""
    debtor_name: str = ""
    raw: str = field(default="", repr=False)


def parse_swiss_qr(payload: str) -> QrBill | None:
    """Parse an SPC payload; None when the text is not a Swiss QR-bill."""
    lines = [ln.strip() for ln in payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    if len(lines) < 31 or lines[0] != SPC_MAGIC or lines[1][:2] != "02":
        return None
    iban = lines[3].replace(" ", "").upper()
    if not re.fullmatch(r"(CH|LI)\d{2}[A-Z0-9]{17}", iban):
        return None
    creditor_name = lines[5]
    creditor_address = " ".join(p for p in (lines[6], lines[7], f"{lines[8]} {lines[9]}".strip()) if p).strip()
    amount = _amount(lines[18])
    currency = lines[19] or "CHF"
    debtor_name = lines[21] if len(lines) > 21 else ""
    reference_type = lines[27] if len(lines) > 27 else "NON"
    reference = (lines[28] if len(lines) > 28 else "").replace(" ", "")
    message = lines[29] if len(lines) > 29 else ""
    if reference_type not in {"QRR", "SCOR", "NON"}:
        return None
    if reference_type == "QRR" and not (re.fullmatch(r"\d{27}", reference) and _mod10_recursive(reference)):
        return None
    if reference_type == "NON":
        reference = ""
    return QrBill(
        iban=iban,
        creditor_name=creditor_name,
        amount=amount,
        currency=currency,
        reference_type=reference_type,
        reference=reference,
        message=message,
        creditor_address=creditor_address,
        debtor_name=debtor_name,
        raw=payload,
    )


def _amount(text: str) -> float | None:
    text = (text or "").replace("'", "").replace(" ", "").strip()
    if not text:
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _mod10_recursive(ref: str) -> bool:
    """Check digit of a 27-digit QR reference (same algorithm as the old ESR)."""
    table = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    carry = 0
    for ch in ref[:-1]:
        carry = table[(carry + int(ch)) % 10]
    return (10 - carry) % 10 == int(ref[-1])


def invoice_number_from_message(message: str) -> str:
    """'Rechnung 2026-0042' / 'Re-Nr. 4711' / 'Invoice #A-12' → the number, or ''."""
    m = re.search(
        r"(?:rechnung|re\.?-?nr\.?|invoice|facture|fattura|nr\.?|no\.?|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/._]{2,})",
        message,
        re.I,
    )
    return m.group(1).rstrip(".,;") if m else ""


# ── decoding ─────────────────────────────────────────────────────────────────


def _decode_image(image) -> list[str]:
    import zxingcpp

    results = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    return [r.text for r in results if r.text]


def decode_qr_payloads(content: bytes, content_type: str = "") -> list[str]:
    """Every QR payload found in an image or in the first pages of a PDF (empty on failure)."""
    try:
        from PIL import Image

        if content_type == "application/pdf" or content[:5] == b"%PDF-":
            import pypdfium2 as pdfium

            payloads: list[str] = []
            pdf = pdfium.PdfDocument(io.BytesIO(content))
            for index in range(min(len(pdf), _MAX_PDF_PAGES)):
                page = pdf[index]
                image = page.render(scale=_PDF_SCALE).to_pil()
                payloads.extend(_decode_image(image))
                if payloads:
                    break
            return payloads
        with Image.open(io.BytesIO(content)) as image:
            return _decode_image(image.convert("RGB"))
    except Exception:  # a broken file is not a server error — the caller falls back to vision/OCR
        logger.info("[QR] decode failed", exc_info=True)
        return []


def read_qr_bill(content: bytes, content_type: str = "") -> QrBill | None:
    """First Swiss QR-bill found in the document, or None."""
    for payload in decode_qr_payloads(content, content_type):
        bill = parse_swiss_qr(payload)
        if bill:
            return bill
    return None

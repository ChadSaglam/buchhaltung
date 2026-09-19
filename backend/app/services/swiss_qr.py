"""Swiss QR-bill — the *writing* side (B-68).

``services/qr_bill.py`` reads a QR-bill somebody sent us. This module builds one
for an invoice we write ourselves: the reference the payment will carry back, the
Swiss Payments Code payload, and the QR square with the Swiss cross in it.

Spec: SIX "Swiss Payment Standards — Implementation Guidelines QR-bill" v2.3.
Rules that matter here:

* A **QR-IBAN** (institution id 30000–31999) *must* carry a **QRR** reference —
  27 digits, last one a recursive mod-10 check digit.
* A normal IBAN must not carry QRR; it may carry a **SCOR** reference
  (ISO 11649: ``RF`` + two mod-97 check digits) or none at all.

Pure module: strings in, strings out, no ORM and no I/O, so every rule above is
unit-testable on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REFERENCE_QRR = "QRR"
REFERENCE_SCOR = "SCOR"
REFERENCE_NON = "NON"

QRR_LENGTH = 27
SCOR_MAX_LENGTH = 25
MESSAGE_MAX = 140
# The Swiss cross is 7 mm on a 46 mm code.
CROSS_RATIO = 7 / 46

_MOD10_TABLE = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)
_IBAN_RE = re.compile(r"^(CH|LI)\d{2}[A-Z0-9]{17}$")


def normalize_iban(iban: str) -> str:
    return (iban or "").replace(" ", "").replace("-", "").upper()


def is_valid_iban(iban: str) -> bool:
    """Swiss/Liechtenstein IBAN, checked on length, country and the mod-97 digit."""
    value = normalize_iban(iban)
    if not _IBAN_RE.match(value):
        return False
    shifted = value[4:] + value[:4]
    digits = "".join(str(int(ch, 36)) for ch in shifted)
    return int(digits) % 97 == 1


def is_qr_iban(iban: str) -> bool:
    """A QR-IBAN carries an institution id of 30000–31999 — it *requires* a QRR reference."""
    value = normalize_iban(iban)
    if not _IBAN_RE.match(value):
        return False
    iid = value[4:9]
    return iid.isdigit() and 30000 <= int(iid) <= 31999


def format_iban(iban: str) -> str:
    """'CH4431999123000889012' → 'CH44 3199 9123 0008 8901 2' (how it is printed)."""
    value = normalize_iban(iban)
    return " ".join(value[i : i + 4] for i in range(0, len(value), 4)).strip()


def mod10_recursive(digits: str) -> int:
    """The ESR/QRR check digit for a run of digits."""
    carry = 0
    for ch in digits:
        carry = _MOD10_TABLE[(carry + int(ch)) % 10]
    return (10 - carry) % 10


def qrr_reference(tenant_id: int, document_id: int) -> str:
    """A stable 27-digit QRR reference for one invoice.

    Tenant and document id are what make it unique, and because both are known
    when the invoice is created the reference never has to be looked up again —
    the payment comes back carrying exactly this number.
    """
    base = f"{int(tenant_id) % 10**6:06d}{int(document_id) % 10**20:020d}"
    return base + str(mod10_recursive(base))


def is_valid_qrr(reference: str) -> bool:
    ref = (reference or "").replace(" ", "")
    return bool(re.fullmatch(r"\d{27}", ref)) and mod10_recursive(ref[:-1]) == int(ref[-1])


def scor_reference(text: str) -> str:
    """ISO 11649 creditor reference: 'RF' + two check digits + up to 21 alphanumerics."""
    body = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()[:21] or "0"
    shifted = f"{body}RF00"
    digits = "".join(str(int(ch, 36)) for ch in shifted)
    check = 98 - (int(digits) % 97)
    return f"RF{check:02d}{body}"


def is_valid_scor(reference: str) -> bool:
    ref = (reference or "").replace(" ", "").upper()
    if not re.fullmatch(r"RF\d{2}[A-Z0-9]{1,21}", ref):
        return False
    shifted = ref[4:] + ref[:4]
    return int("".join(str(int(ch, 36)) for ch in shifted)) % 97 == 1


def reference_for(iban: str, *, tenant_id: int, document_id: int, invoice_no: str) -> tuple[str, str]:
    """(type, reference) — QRR on a QR-IBAN, SCOR on a normal one, NON without an IBAN."""
    if not is_valid_iban(iban):
        return REFERENCE_NON, ""
    if is_qr_iban(iban):
        return REFERENCE_QRR, qrr_reference(tenant_id, document_id)
    return REFERENCE_SCOR, scor_reference(invoice_no or f"{tenant_id}-{document_id}")


def format_reference(reference: str, reference_type: str = "") -> str:
    """How a reference is printed: QRR in blocks of five from the right, SCOR in fours."""
    ref = (reference or "").replace(" ", "")
    if not ref:
        return ""
    if reference_type == REFERENCE_SCOR or ref[:2].upper() == "RF":
        return " ".join(ref[i : i + 4] for i in range(0, len(ref), 4))
    head = len(ref) % 5
    blocks = ([ref[:head]] if head else []) + [ref[i : i + 5] for i in range(head, len(ref), 5)]
    return " ".join(blocks)


def format_amount(amount: float | None) -> str:
    """The Zahlteil amount: no thousand separators, always two decimals ('1234.50')."""
    if amount is None:
        return ""
    return f"{float(amount):.2f}"


@dataclass(frozen=True)
class Party:
    """Creditor or debtor as the payload wants it (structured address)."""

    name: str = ""
    strasse: str = ""
    hausnummer: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "CH"

    @property
    def filled(self) -> bool:
        return bool(self.name.strip())

    def address_line(self) -> str:
        strasse = " ".join(p for p in (self.strasse, self.hausnummer) if p).strip()
        ort = " ".join(p for p in (self.plz, self.ort) if p).strip()
        return ", ".join(p for p in (strasse, ort) if p)

    def lines(self) -> list[str]:
        if not self.filled:
            return ["", "", "", "", "", "", ""]
        return [
            "S",
            self.name[:70],
            self.strasse[:70],
            self.hausnummer[:16],
            self.plz[:16],
            self.ort[:35],
            (self.land or "CH")[:2].upper(),
        ]


def build_payload(
    *,
    iban: str,
    creditor: Party,
    amount: float | None,
    currency: str = "CHF",
    reference_type: str = REFERENCE_NON,
    reference: str = "",
    message: str = "",
    debtor: Party | None = None,
) -> str:
    """The Swiss Payments Code that goes into the QR square (31 lines, LF separated)."""
    lines: list[str] = [
        "SPC",
        "0200",
        "1",
        normalize_iban(iban),
        *creditor.lines(),
        *["", "", "", "", "", "", ""],  # Ultimate creditor — reserved, always empty
        format_amount(amount),
        (currency or "CHF").upper()[:3],
        *(debtor or Party()).lines(),
        reference_type,
        (reference or "").replace(" ", ""),
        (message or "")[:MESSAGE_MAX],
        "EPD",
    ]
    return "\n".join(lines)


def qr_matrix(payload: str) -> list[bytearray]:
    """The QR square as rows of 0/1 modules — the source both renderers draw from.

    Kept separate from :func:`qr_svg` because the PDF renderer (B-77) draws the
    modules as vector rectangles rather than parsing SVG: a QR-bill a bank
    scanner rejects because it was rasterised is worse than no QR at all.
    """
    import segno

    code = segno.make(payload, error="m", mode="byte", encoding="utf-8")
    return [bytearray(row) for row in code.matrix]


def cross_geometry(modules: int) -> tuple[float, float, float, float, float]:
    """Swiss cross placement in module units: (side, offset, border, bar_long, bar_short)."""
    cross = modules * CROSS_RATIO
    return cross, (modules - cross) / 2, cross * 0.06, cross * 0.62, cross * 0.19


def qr_svg(payload: str, *, size_mm: float = 46.0) -> str:
    """The QR square as inline SVG, with the Swiss cross in the middle.

    Inline rather than a data URI so the browser prints it as vectors — a QR-bill
    that a bank scanner rejects because it was rasterised is worse than no QR at all.
    """
    matrix = qr_matrix(payload)
    modules = len(matrix)
    dark = "".join(f"M{x} {y}h1v1h-1z" for y, row in enumerate(matrix) for x, value in enumerate(row) if value)
    cross, offset, border, bar_long, bar_short = cross_geometry(modules)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {modules} {modules}" '
        f'width="{size_mm}mm" height="{size_mm}mm" shape-rendering="crispEdges" '
        'role="img" aria-label="Swiss QR-Code">'
        f'<rect width="{modules}" height="{modules}" fill="#fff"/>'
        f'<path d="{dark}" fill="#000"/>'
        f'<rect x="{offset:.3f}" y="{offset:.3f}" width="{cross:.3f}" height="{cross:.3f}" fill="#fff"/>'
        f'<rect x="{offset + border:.3f}" y="{offset + border:.3f}" '
        f'width="{cross - 2 * border:.3f}" height="{cross - 2 * border:.3f}" fill="#000"/>'
        f'<rect x="{offset + (cross - bar_short) / 2:.3f}" y="{offset + (cross - bar_long) / 2:.3f}" '
        f'width="{bar_short:.3f}" height="{bar_long:.3f}" fill="#fff"/>'
        f'<rect x="{offset + (cross - bar_long) / 2:.3f}" y="{offset + (cross - bar_short) / 2:.3f}" '
        f'width="{bar_long:.3f}" height="{bar_short:.3f}" fill="#fff"/>'
        "</svg>"
    )

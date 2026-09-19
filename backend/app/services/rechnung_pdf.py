"""Die Rechnung als PDF, mit einem Zahlteil, den ein Scanner liest (B-77/B-79).

`invoice_html` gibt es weiter — es ist die Druckvorschau im Browser. Verschickt
wird aber eine Datei, und "drucken Sie die Seite als PDF" ist keine Antwort auf
"schick dem Kunden die Rechnung".

Der Zahlteil ist kein freies Layout: die SIX-Vorlage schreibt A4 unten
**105 mm** hoch vor, links **62 mm** Empfangsschein, rechts **148 mm** Zahlteil,
und den QR-Code exakt **46 x 46 mm** mit **5 mm** Ruhezone. Darum steht hier ein
Millimeterraster und keine Textfluss-Logik.

Der QR-Code wird als **Vektorrechtecke** gezeichnet, nicht als Bild: ein
gerasterter QR, den der Bankscanner ablehnt, ist schlimmer als gar keiner.
Waagrechte Läufe werden zu einem Rechteck zusammengefasst, sonst stehen ~2000
Rechtecke im Content-Stream.
"""

from __future__ import annotations

from datetime import date

from app.models.company_profile import CompanyProfile
from app.models.document import Document
from app.models.invoice_position import InvoicePosition
from app.services import swiss_qr
from app.services.export import fmt_swiss
from app.services.pdf_render import CONTENT_WIDTH, MARGIN, Column, Meta, PdfDoc, Row, latin1

# --- Zahlteil-Geometrie (SIX Style Guide, Masse in mm) -----------------------
PAGE_HEIGHT = 297.0
ZAHLTEIL_HEIGHT = 105.0
ZAHLTEIL_TOP = PAGE_HEIGHT - ZAHLTEIL_HEIGHT
EMPFANGSSCHEIN_WIDTH = 62.0
INNER_MARGIN = 5.0
QR_SIZE = 46.0
#: Ruhezone rund um den Code — ohne sie liest der Scanner den Rand als Modul.
QR_QUIET = 5.0

TITLE_SIZE = 11.0
HEADING_SIZE = 6.0
VALUE_SIZE = 8.0
RECEIPT_HEADING_SIZE = 6.0
RECEIPT_VALUE_SIZE = 8.0


def _swiss_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def _lines(party: swiss_qr.Party) -> list[str]:
    out = [party.name]
    address = party.address_line()
    if address:
        out.append(address)
    return [line for line in out if line]


def draw_qr(pdf, payload: str, x: float, y: float, size: float = QR_SIZE) -> None:
    """Den QR-Code als Vektoren zeichnen, inklusive Schweizerkreuz."""
    matrix = swiss_qr.qr_matrix(payload)
    modules = len(matrix)
    step = size / modules

    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, size, size, style="F")
    pdf.set_fill_color(0, 0, 0)
    for row_index, row in enumerate(matrix):
        col = 0
        while col < modules:
            if not row[col]:
                col += 1
                continue
            run = col
            while run < modules and row[run]:
                run += 1
            pdf.rect(x + col * step, y + row_index * step, (run - col) * step, step, style="F")
            col = run

    cross, offset, border, bar_long, bar_short = swiss_qr.cross_geometry(modules)
    cx, cy = x + offset * step, y + offset * step
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(cx, cy, cross * step, cross * step, style="F")
    pdf.set_fill_color(0, 0, 0)
    pdf.rect(
        cx + border * step, cy + border * step, (cross - 2 * border) * step, (cross - 2 * border) * step, style="F"
    )
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(
        cx + (cross - bar_short) / 2 * step,
        cy + (cross - bar_long) / 2 * step,
        bar_short * step,
        bar_long * step,
        style="F",
    )
    pdf.rect(
        cx + (cross - bar_long) / 2 * step,
        cy + (cross - bar_short) / 2 * step,
        bar_long * step,
        bar_short * step,
        style="F",
    )
    pdf.set_fill_color(0, 0, 0)


class _Block:
    """Ein Textblock im Zahlteil: Überschrift klein und fett, Werte darunter."""

    def __init__(self, pdf, x: float, y: float, width: float, heading: float, value: float) -> None:
        self.pdf, self.x, self.y, self.width = pdf, x, y, width
        self.heading_size, self.value_size = heading, value

    def heading(self, text: str) -> None:
        self.pdf.set_xy(self.x, self.y)
        self.pdf.set_font("Helvetica", "B", self.heading_size)
        self.pdf.cell(self.width, self.heading_size * 0.42, latin1(text))
        self.y += self.heading_size * 0.45

    def value(self, text: str) -> None:
        if not text:
            return
        self.pdf.set_xy(self.x, self.y)
        self.pdf.set_font("Helvetica", "", self.value_size)
        self.pdf.multi_cell(self.width, self.value_size * 0.42, latin1(text), new_x="LMARGIN", new_y="NEXT")
        self.y = self.pdf.get_y()

    def values(self, texts: list[str]) -> None:
        for text in texts:
            self.value(text)

    def gap(self, mm: float = 2.0) -> None:
        self.y += mm


def draw_zahlteil(
    pdf,
    *,
    payload: str,
    profile: CompanyProfile,
    kunde: swiss_qr.Party,
    reference: str,
    message: str,
    amount: float,
    currency: str,
) -> None:
    """Empfangsschein und Zahlteil auf den unteren 105 mm der Seite."""
    konto = [
        swiss_qr.format_iban(profile.iban),
        *_lines(
            swiss_qr.Party(
                name=profile.name,
                strasse=profile.strasse,
                hausnummer=profile.hausnummer,
                plz=profile.plz,
                ort=profile.ort,
                land=profile.land or "CH",
            )
        ),
    ]
    zahlbar_durch = _lines(kunde) or ["Keine Angaben"]
    betrag = fmt_swiss(amount)

    pdf.set_draw_color(120, 120, 120)
    pdf.set_line_width(0.2)
    pdf.dashed_line(0, ZAHLTEIL_TOP, 210.0, ZAHLTEIL_TOP, 2, 2)
    pdf.dashed_line(EMPFANGSSCHEIN_WIDTH, ZAHLTEIL_TOP, EMPFANGSSCHEIN_WIDTH, PAGE_HEIGHT, 2, 2)
    pdf.set_draw_color(0, 0, 0)

    # ── Empfangsschein ──────────────────────────────────────────────────────
    left = _Block(
        pdf,
        INNER_MARGIN,
        ZAHLTEIL_TOP + INNER_MARGIN,
        EMPFANGSSCHEIN_WIDTH - 2 * INNER_MARGIN,
        RECEIPT_HEADING_SIZE,
        RECEIPT_VALUE_SIZE,
    )
    pdf.set_xy(left.x, left.y)
    pdf.set_font("Helvetica", "B", TITLE_SIZE)
    pdf.cell(left.width, 5, latin1("Empfangsschein"))
    left.y += 7
    left.heading("Konto / Zahlbar an")
    left.values(konto)
    left.gap()
    if reference:
        left.heading("Referenz")
        left.value(reference)
        left.gap()
    left.heading("Zahlbar durch")
    left.values(zahlbar_durch)

    amount_y = ZAHLTEIL_TOP + ZAHLTEIL_HEIGHT - 28.0
    pdf.set_xy(left.x, amount_y)
    pdf.set_font("Helvetica", "B", RECEIPT_HEADING_SIZE)
    pdf.cell(16, 3, latin1("Währung"))
    pdf.cell(20, 3, latin1("Betrag"))
    pdf.set_xy(left.x, amount_y + 3.2)
    pdf.set_font("Helvetica", "", RECEIPT_VALUE_SIZE)
    pdf.cell(16, 3.5, latin1(currency))
    pdf.cell(20, 3.5, latin1(betrag))
    pdf.set_xy(left.x, ZAHLTEIL_TOP + ZAHLTEIL_HEIGHT - 12.0)
    pdf.set_font("Helvetica", "B", RECEIPT_HEADING_SIZE)
    pdf.cell(left.width, 3, latin1("Annahmestelle"), align="R")

    # ── Zahlteil ────────────────────────────────────────────────────────────
    qr_x = EMPFANGSSCHEIN_WIDTH + INNER_MARGIN
    pdf.set_xy(qr_x, ZAHLTEIL_TOP + INNER_MARGIN)
    pdf.set_font("Helvetica", "B", TITLE_SIZE)
    pdf.cell(60, 5, latin1("Zahlteil"))

    qr_y = ZAHLTEIL_TOP + INNER_MARGIN + 7.0
    draw_qr(pdf, payload, qr_x, qr_y)

    # Die Ruhezone gehört zum Code: nichts darf näher als 5 mm heran.
    amount_y = qr_y + QR_SIZE + QR_QUIET
    pdf.set_xy(qr_x, amount_y)
    pdf.set_font("Helvetica", "B", HEADING_SIZE)
    pdf.cell(18, 3, latin1("Währung"))
    pdf.cell(28, 3, latin1("Betrag"))
    pdf.set_xy(qr_x, amount_y + 3.4)
    pdf.set_font("Helvetica", "", VALUE_SIZE)
    pdf.cell(18, 4, latin1(currency))
    pdf.cell(28, 4, latin1(betrag))

    info_x = qr_x + QR_SIZE + INNER_MARGIN
    right = _Block(
        pdf,
        info_x,
        ZAHLTEIL_TOP + INNER_MARGIN,
        210.0 - info_x - INNER_MARGIN,
        HEADING_SIZE,
        VALUE_SIZE,
    )
    right.heading("Konto / Zahlbar an")
    right.values(konto)
    right.gap()
    if reference:
        right.heading("Referenz")
        right.value(reference)
        right.gap()
    if message:
        right.heading("Zusätzliche Informationen")
        right.value(message)
        right.gap()
    right.heading("Zahlbar durch")
    right.values(zahlbar_durch)


def invoice_pdf(
    doc: Document,
    positions: list[InvoicePosition],
    profile: CompanyProfile,
    payload: str,
    *,
    kunde: swiss_qr.Party,
    reference: str,
    netto: float,
    mwst: float,
    watermark: str = "",
    erstellt: date | None = None,
) -> bytes:
    """Brief oben, Zahlteil unten — die Datei, die der Kunde bekommt.

    ``watermark`` ist leer für echte Rechnungen. Die Beispielrechnung (B-20)
    setzt ihn, damit niemand sie für eine Forderung hält — der Zahlteil zeichnet
    seinen eigenen weissen Grund, der QR-Code bleibt also lesbar.
    """
    brutto = float(doc.amount or 0.0)
    currency = (doc.currency or "CHF").upper()
    try:
        rate = abs(float(profile.mwst_pct or 0.0))
    except ValueError:
        rate = 0.0

    kontakt = " · ".join(p for p in (profile.email, profile.telefon, profile.mwst_nr) if p)
    extra: list[tuple[str, str]] = [("Rechnungsdatum", _swiss_date(doc.invoice_date))]
    if doc.due_date:
        extra.append(("Zahlbar bis", _swiss_date(doc.due_date)))
    if reference:
        extra.append(("Referenz", reference))

    document = PdfDoc(
        Meta(
            title=f"Rechnung {doc.invoice_no}".strip(),
            company=profile.name,
            company_address=swiss_qr.Party(
                name=profile.name,
                strasse=profile.strasse,
                hausnummer=profile.hausnummer,
                plz=profile.plz,
                ort=profile.ort,
            ).address_line(),
            subtitle=kontakt,
            extra=extra,
            # Weder Fusszeile noch Seitenzahl: beide lägen im Zahlteil, und der
            # gehört der SIX-Vorlage.
            footer="",
            page_numbers=False,
            watermark=watermark,
            erstellt=erstellt,
        )
    )
    pdf = document.pdf
    pdf.set_auto_page_break(auto=False)

    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    for line in _lines(kunde) or ["Keine Kundenangaben"]:
        pdf.cell(0, 5, latin1(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    columns = [
        Column("Pos.", 12.0, "L"),
        Column("Bezeichnung", CONTENT_WIDTH - 12.0 - 22.0 - 28.0 - 30.0, "L"),
        Column("Menge", 22.0, "R"),
        Column("Einzelpreis", 28.0, "R", money=True),
        Column(f"Betrag {currency}", 30.0, "R", money=True),
    ]
    rows = [
        Row(
            [
                str(p.position),
                p.bezeichnung,
                f"{fmt_swiss(p.menge)} {p.einheit}".strip(),
                p.einzelpreis,
                round(float(p.menge or 0) * float(p.einzelpreis or 0), 2),
            ]
        )
        for p in positions
    ]
    document.table(columns, rows)

    pdf.ln(3)
    label_width = CONTENT_WIDTH - 30.0
    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(label_width, 5.4, latin1("Zwischentotal"), align="R")
    pdf.cell(30.0, 5.4, latin1(fmt_swiss(netto)), align="R", new_x="LMARGIN", new_y="NEXT")
    if mwst:
        pdf.cell(label_width, 5.4, latin1(f"MWST {rate:.1f} %"), align="R")
        pdf.cell(30.0, 5.4, latin1(fmt_swiss(mwst)), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(label_width, 6.2, latin1(f"Total {currency}"), border="T", align="R")
    pdf.cell(30.0, 6.2, latin1(fmt_swiss(brutto)), border="T", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font("Helvetica", "", 9)
    hinweis = "Zahlbar bis {} ohne Abzug. Bitte bezahlen Sie mit dem QR-Code unten, damit die Zahlung automatisch zugeordnet wird.".format(
        _swiss_date(doc.due_date) or "zum Fälligkeitsdatum"
    )
    pdf.set_x(MARGIN)
    pdf.multi_cell(CONTENT_WIDTH, 4.6, latin1(hinweis), new_x="LMARGIN", new_y="NEXT")

    draw_zahlteil(
        pdf,
        payload=payload,
        profile=profile,
        kunde=kunde,
        reference=reference,
        message=doc.qr_message or "",
        amount=brutto,
        currency=currency,
    )
    return document.output()

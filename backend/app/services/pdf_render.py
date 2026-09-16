"""Der eine PDF-Renderer (B-77).

Bilanz, Erfolgsrechnung, Mahnung, MWST-Formular und das Deckblatt brauchen alle
echtes PDF. Statt für jedes Dokument eine eigene Lösung: **fpdf2** — reines
Python, kein C-Build, kein Wheel-Theater im Docker-Image. reportlab kann mehr,
aber was wir drucken ist Text und Tabellen; die Mehrleistung hätten wir mit
Installationsaufwand bezahlt.

Dieses Modul ist bewusst dumm: A4, eine Schrift, Titel, Tabellen, Summenzeilen.
Es kennt keine Buchhaltung — die Zahlen kommen fertig von den Services, damit
derselbe Renderer für jedes Dokument taugt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.export import fmt_swiss

# fpdf2 core fonts speak latin-1; typographic characters are replaced rather
# than raising deep inside the renderer.
_REPLACEMENTS = {
    "–": "-",
    "—": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "‚": "'",
    "…": "...",
    " ": " ",
    " ": " ",
    "•": "-",
    "→": "->",
    "€": "EUR",
    "✓": "ok",
    "✔": "ok",
}

PAGE_WIDTH = 210.0
MARGIN = 18.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def latin1(text: str | None) -> str:
    """Text fpdf2's core fonts can actually print."""
    value = str(text or "")
    for bad, good in _REPLACEMENTS.items():
        value = value.replace(bad, good)
    return value.encode("latin-1", "replace").decode("latin-1")


@dataclass
class Column:
    """One column of a table: how wide, how aligned, and is it money?"""

    label: str
    width: float
    align: str = "L"
    money: bool = False


@dataclass
class Row:
    cells: list[str | float | None]
    bold: bool = False
    top_line: bool = False
    fill: bool = False


@dataclass
class Meta:
    """The letterhead: who prints this, what it is, for which period."""

    title: str
    subtitle: str = ""
    company: str = ""
    #: Second letterhead line — the sender's address, under the company name.
    company_address: str = ""
    period: str = ""
    footer: str = ""
    extra: list[tuple[str, str]] = field(default_factory=list)
    #: Off for documents whose bottom belongs to something else — the Swiss
    #: QR-bill payment part is a fixed template and nothing may sit in it.
    page_numbers: bool = True


def _fpdf_class():
    from fpdf import FPDF

    class _Doc(FPDF):
        """FPDF mit fester Fusszeile — so steht sie auf *jeder* Seite, auch auf Seite 3."""

        def __init__(self, footer_text: str = "", page_numbers: bool = True) -> None:
            super().__init__(orientation="P", unit="mm", format="A4")
            self.footer_text = footer_text
            self.page_numbers = page_numbers

        def footer(self) -> None:
            if not self.page_numbers and not self.footer_text:
                return
            self.set_y(-15)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(120, 120, 120)
            self.cell(CONTENT_WIDTH / 2, 5, latin1(self.footer_text))
            if self.page_numbers:
                self.cell(CONTENT_WIDTH / 2, 5, latin1(f"Seite {self.page_no()} / {{nb}}"), align="R")
            self.set_text_color(0, 0, 0)

    return _Doc


def _Fpdf(footer_text: str = "", page_numbers: bool = True):
    return _fpdf_class()(footer_text, page_numbers)


class PdfDoc:
    """A4 document with a header, sections, tables and page numbers."""

    def __init__(self, meta: Meta) -> None:
        self.meta = meta
        self.pdf = _Fpdf(meta.footer, meta.page_numbers)
        self.pdf.set_auto_page_break(auto=True, margin=20)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.pdf.set_title(latin1(meta.title))
        if meta.company:
            self.pdf.set_author(latin1(meta.company))
        self.pdf.add_page()
        self._letterhead()

    # ── Aufbau ───────────────────────────────────────────────────────────────

    def _letterhead(self) -> None:
        pdf = self.pdf
        if self.meta.company:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, latin1(self.meta.company), new_x="LMARGIN", new_y="NEXT")
        if self.meta.company_address:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 4.5, latin1(self.meta.company_address), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 9, latin1(self.meta.title), new_x="LMARGIN", new_y="NEXT")
        if self.meta.subtitle:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 5, latin1(self.meta.subtitle), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        if self.meta.period:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 5, latin1(self.meta.period), new_x="LMARGIN", new_y="NEXT")
        for label, value in self.meta.extra:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 4.5, latin1(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    def section(self, title: str, note: str = "") -> None:
        pdf = self.pdf
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 6, latin1(title), new_x="LMARGIN", new_y="NEXT")
        if note:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(90, 90, 90)
            pdf.multi_cell(CONTENT_WIDTH, 4.2, latin1(note), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def paragraph(self, text: str, size: float = 9.5) -> None:
        self.pdf.set_font("Helvetica", "", size)
        self.pdf.multi_cell(CONTENT_WIDTH, 4.6, latin1(text), new_x="LMARGIN", new_y="NEXT")

    def table(self, columns: list[Column], rows: list[Row]) -> None:
        pdf = self.pdf
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(70, 70, 70)
        for column in columns:
            pdf.cell(column.width, 5, latin1(column.label.upper()), border="B", align=column.align)
        pdf.ln(5)
        pdf.set_text_color(0, 0, 0)

        for row in rows:
            pdf.set_font("Helvetica", "B" if row.bold else "", 9.5)
            border = "T" if row.top_line else 0
            for column, value in zip(columns, row.cells, strict=False):
                text = fmt_swiss(value) if column.money and value not in (None, "") else str(value or "")
                pdf.cell(column.width, 5.6, latin1(text), border=border, align=column.align)
            pdf.ln(5.6)

    def keyvalue(self, pairs: list[tuple[str, str]]) -> None:
        pdf = self.pdf
        for label, value in pairs:
            pdf.set_font("Helvetica", "", 9.5)
            pdf.cell(55, 5.2, latin1(label))
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.cell(0, 5.2, latin1(value), new_x="LMARGIN", new_y="NEXT")

    def page_break(self) -> None:
        self.pdf.add_page()

    def output(self) -> bytes:
        """Das fertige PDF. Fusszeile und 'Seite x / y' setzt fpdf2 auf jeder Seite selbst."""
        return bytes(self.pdf.output())


def money_columns(first_label: str, first_width: float = 0.0) -> list[Column]:
    """The layout every money table in this app uses: Konto · Bezeichnung · CHF."""
    width = first_width or 22.0
    return [
        Column("Konto", width, "L"),
        Column(first_label, CONTENT_WIDTH - width - 32.0, "L"),
        Column("CHF", 32.0, "R", money=True),
    ]

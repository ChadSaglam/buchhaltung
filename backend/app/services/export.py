"""Export helpers — Banana TSV, styled Excel, semicolon CSV.

Everything here leaves the building: the Treuhänder opens these files, usually
in Excel. So the writers are paranoid on purpose (B-53):

* a text cell that starts with ``=``, ``+``, ``-`` or ``@`` is a formula for
  Excel and LibreOffice, and a receipt description is attacker-controlled text
  — it gets neutralised, never evaluated;
* a tab or a newline inside a description would shift every following column of
  a TSV import, so those collapse to a space;
* dates are zero-padded (``2026-09-05``, not ``2026-9-5``) — Banana rejects the
  short form;
* an amount that is not a finite number is written as blank instead of ``nan``.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_CENT = Decimal("0.01")

# Excel and LibreOffice evaluate a cell that starts with one of these.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def round_chf(val) -> Decimal:
    """Round a money value to 2 decimals, half-up (kaufm\u00e4nnisch), on its decimal text.

    Going through the decimal representation (not the binary float) is what
    makes 2.675 -> 2.68 and 0.125 -> 0.13 instead of the half-even/binary
    artefacts of ``round()`` and ``f"{x:.2f}"``. Negative zero collapses to 0.
    """
    dec = val if isinstance(val, Decimal) else Decimal(repr(float(val)))
    if not dec.is_finite():
        raise ValueError(f"non-finite amount: {val!r}")
    dec = dec.quantize(_CENT, rounding=ROUND_HALF_UP)
    return dec if dec != 0 else _CENT * 0


#: U+0027, the plain apostrophe — what the docstring below always promised, what
#: the frontend's `formatAmount` prints, and what every PDF already shows
#: (fpdf2's core fonts are latin-1, so `pdf_render.latin1()` was silently
#: rewriting U+2019 to this on the way out). Until 2026-09-16 this function
#: emitted U+2019, so the same amount read `1'234.50` on a PDF and `1’234.50` in
#: the HTML preview, the e-mail and the CSV beside it.
THOUSANDS = "'"


def fmt_swiss(val) -> str:
    """Format a number in Swiss style: 1'234.56"""
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return ""
    num = round_chf(val)
    negative = num < 0
    if negative:
        num = abs(num)
    integer_part = int(num)
    decimal_part = str(num - integer_part)[1:]  # ".56"
    int_str = f"{integer_part:,}".replace(",", THOUSANDS)
    result = f"{int_str}{decimal_part}"
    if negative:
        result = f"-{result}"
    return result


def neutralise(value: Any) -> Any:
    """Text that Excel would run as a formula comes back quoted; everything else is untouched.

    Only strings are touched — numbers are written as numbers and cannot be a
    formula. The leading apostrophe is the mitigation every spreadsheet knows.
    """
    if not isinstance(value, str) or not value:
        return value
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


def safe_text(value: Any) -> str:
    """One line, no tabs, no formula — what a TSV/CSV field may contain."""
    text = "" if value is None else str(value)
    text = text.replace("\t", " ").replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return str(neutralise(text.strip()))


def iso_date(value: Any) -> str:
    """'5.9.2026' → '2026-09-05'. ISO input and anything unparseable pass through."""
    text = "" if value is None else str(value).strip()
    if "." not in text:
        return text
    parts = text.split(".")
    if len(parts) != 3 or not all(p.strip().isdigit() for p in parts):
        return text
    day, month, year = (p.strip() for p in parts)
    return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"


def safe_amount(value: Any) -> str:
    """Two decimals, no thousands separator — blank when it is not a finite number."""
    if value is None or value == "":
        return ""
    try:
        amount = round_chf(value)
    except (ValueError, TypeError, ArithmeticError):
        return ""
    return f"{amount:.2f}" if amount != 0 else ""


BANANA_DF_COLUMNS = [
    "Nr",
    "Datum",
    "Beleg",
    "Rechnung",
    "Beschreibung",
    "KtSoll",
    "KtHaben",
    "Betrag CHF",
    "MwStUSt-Code",
    "Art Betrag",
    "MwSt-%",
    "Gebuchte MwStUSt CHF",
    "KS3",
]


def bookings_to_df(bookings: Sequence[Any]) -> pd.DataFrame:
    """Booking rows → the export frame every writer below expects.

    Duck-typed on purpose: the router hands over ORM rows, the batch service the
    rows of one batch, and tests plain objects. One mapping, one column order —
    so the same bookings always render the same file (phase 4 checksum).
    """
    rows = [
        {
            "Nr": b.id,
            "Datum": b.datum,
            "Beleg": b.beleg or "",
            "Rechnung": b.rechnung or "",
            "Beschreibung": b.beschreibung or "",
            "KtSoll": b.kt_soll or "",
            "KtHaben": b.kt_haben or "",
            "Betrag CHF": b.betrag or 0,
            "MwStUSt-Code": b.mwst_code or "",
            "Art Betrag": "",
            "MwSt-%": b.mwst_pct or "",
            "Gebuchte MwStUSt CHF": b.mwst_amount or 0,
            "KS3": "",
        }
        for b in bookings
    ]
    return pd.DataFrame(rows, columns=BANANA_DF_COLUMNS)


def df_to_styled_excel(df: pd.DataFrame) -> bytes:
    """Export DataFrame to a formatted .xlsx with headers, borders, colors."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Buchhaltung"

    headers = list(df.columns)
    header_font = Font(bold=True, size=10)
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    col_widths = {
        "Nr": 6,
        "Datum": 12,
        "Beleg": 10,
        "Rechnung": 10,
        "Beschreibung": 48,
        "KtSoll": 8,
        "KtHaben": 8,
        "Betrag CHF": 14,
        "MwStUSt-Code": 16,
        "Art Betrag": 10,
        "MwSt-%": 9,
        "Gebuchte MwStUSt CHF": 20,
        "KS3": 6,
    }

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(header, 12)

    red_font = Font(color="FF0000", size=10)
    normal_font = Font(size=10)
    number_cols = {"Betrag CHF", "Gebuchte MwStUSt CHF", "MwSt-%"}

    for row_idx, (_, row) in enumerate(df.iterrows(), 2):
        for col_idx, header in enumerate(headers, 1):
            val = row[header]
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = thin_border

            if header in number_cols and val != "" and val is not None:
                try:
                    numval = float(val)
                    if numval != numval or numval in (float("inf"), float("-inf")):
                        raise ValueError(val)
                    cell.value = numval
                    cell.number_format = "#,##0.00" if header != "MwSt-%" else "0.00"
                    cell.alignment = Alignment(horizontal="right")
                    cell.font = red_font if numval < 0 else normal_font
                except (ValueError, TypeError):
                    cell.value = neutralise(val)
                    cell.font = normal_font
            elif header in ("KtSoll", "KtHaben", "Nr"):
                cell.value = neutralise(val)
                cell.alignment = Alignment(horizontal="center")
                cell.font = normal_font
            else:
                cell.value = neutralise(val) if val != "" else None
                cell.font = normal_font

    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def df_to_banana_tsv(df: pd.DataFrame) -> str:
    """Export DataFrame to Banana Accounting tab-separated import format."""
    banana_cols = [
        "Date",
        "Description",
        "AccountDebit",
        "AccountCredit",
        "Amount",
        "VatCode",
    ]
    lines = ["\t".join(banana_cols)]

    for _, row in df.iterrows():
        fields = [
            iso_date(row.get("Datum", "")),
            safe_text(row.get("Beschreibung", "")),
            safe_text(row.get("KtSoll", "")),
            safe_text(row.get("KtHaben", "")),
            safe_amount(row.get("Betrag CHF", 0)),
            safe_text(row.get("MwStUSt-Code", "")),
        ]
        lines.append("\t".join(fields))

    return "\n".join(lines)


def df_to_csv(df: pd.DataFrame) -> str:
    """Semicolon-separated CSV — text cells neutralised, so Excel never runs one."""
    buf = io.StringIO()
    df.map(neutralise).to_csv(buf, index=False, sep=";")
    return buf.getvalue()

"""Lohnabrechnung and Jahreszusammenzug as PDF (B-72).

Two documents:

* the **payslip** an employee gets every month. It shows each deduction with the
  rate that produced it, because "AHV 318.00" alone is not checkable and the
  first thing anyone does with a payslip is check it;
* the **Jahreszusammenzug**, twelve payslips added up.

The second is deliberately *not* called a Lohnausweis. The Lohnausweis is
Formular 11, a prescribed form with numbered boxes and a barcode, and issuing a
document that looks like one but is not would be worse than issuing none: the
employee files it with their tax return. What this produces is the figure sheet
a Treuhänder fills the real form from, and it says so on the page.
"""

from __future__ import annotations

from app.models.lohnabrechnung import Lohnabrechnung
from app.models.mitarbeiter import Mitarbeiter
from app.services.export import fmt_swiss
from app.services.pdf_render import CONTENT_WIDTH, Column, Meta, PdfDoc, Row

MONATE = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

HINWEIS_JAHR = (
    "Dies ist kein Lohnausweis. Der Lohnausweis ist das amtliche Formular 11; "
    "diese Zusammenstellung liefert die Zahlen dafür."
)

#: Rule 5 of docs/B-72-LOHN-SPEC.md. Stays on every page until a person has
#: checked one real month against the previous payroll and set the flag. The
#: arithmetic being right is not the same as the setup being right, and a
#: payslip is the wrong place to find that out.
WASSERZEICHEN = "Nicht für die Einreichung"


def wasserzeichen(freigegeben: bool) -> str:
    return "" if freigegeben else WASSERZEICHEN


def monatsname(monat: int) -> str:
    return MONATE[monat - 1] if 1 <= monat <= len(MONATE) else str(monat)


def _satz(value: float) -> str:
    """A rate as it belongs on a payslip: '5.30 %', or blank when there is none.

    BVG and other fixed amounts carry no rate; printing '0.00 %' next to them
    would read as "insured at zero percent" rather than "not a percentage".
    """
    return f"{value:.2f} %" if value else ""


def _abzugszeilen(row: Lohnabrechnung) -> list[Row]:
    lines = [
        # B-96: the Basis column shows the massgebender Lohn — the number the
        # rate was actually applied to — not the payout.
        ("AHV/IV/EO", row.ahv_satz, row.ahv_lohn, row.ahv_betrag),
        ("ALV", row.alv_satz, row.alv_basis, row.alv_betrag),
        ("NBU", row.nbu_satz, row.ahv_lohn, row.nbu_betrag),
        ("UVGZ", row.uvgz_satz, row.ahv_lohn, row.uvgz_betrag),
        ("KTG", row.ktg_satz, row.ahv_lohn, row.ktg_betrag),
        ("BVG", 0.0, row.ahv_lohn, row.bvg_betrag),
        ("Quellensteuer", row.quellensteuer_satz, row.brutto, row.quellensteuer_betrag),
    ]
    return [
        Row([label, _satz(satz), fmt_swiss(basis) if satz else "", fmt_swiss(-betrag)])
        for label, satz, basis, betrag in lines
        if betrag
    ]


def _ag_zeilen(row: Lohnabrechnung) -> list[Row]:
    lines = [
        ("AHV/IV/EO", row.ag_ahv),
        ("ALV", row.ag_alv),
        ("UVG BU", row.ag_bu),
        ("UVGZ", row.ag_uvgz),
        ("KTG", row.ag_ktg),
        ("FAK", row.ag_fak),
        ("Verwaltungskosten", row.ag_verwaltungskosten),
        ("BVG", row.ag_bvg),
    ]
    return [Row([label, "", "", fmt_swiss(betrag)]) for label, betrag in lines if betrag]


def _spalten() -> list[Column]:
    rest = CONTENT_WIDTH - 24.0 - 30.0 - 30.0
    return [
        Column("Position", rest, "L"),
        Column("Satz", 24.0, "R"),
        Column("Basis", 30.0, "R"),
        Column("CHF", 30.0, "R"),
    ]


def abrechnung_pdf(
    row: Lohnabrechnung,
    person: Mitarbeiter,
    *,
    firma: str = "",
    firma_adresse: str = "",
    freigegeben: bool = False,
) -> bytes:
    doc = PdfDoc(
        Meta(
            title="Lohnabrechnung",
            subtitle=person.anzeige_name,
            company=firma,
            company_address=firma_adresse,
            period=f"{monatsname(row.monat)} {row.jahr}",
            extra=[("AHV-Nr.", person.ahv_nummer)] if person.ahv_nummer else [],
            footer=firma,
            watermark=wasserzeichen(freigegeben),
        )
    )
    columns = _spalten()

    lohn: list[Row] = [Row(["Grundlohn", "", "", fmt_swiss(row.grundlohn)])]
    if row.dreizehnter:
        lohn.append(Row(["13. Monatslohn", "", "", fmt_swiss(row.dreizehnter)]))
    if row.zulagen:
        lohn.append(Row(["Zulagen", "", "", fmt_swiss(row.zulagen)]))
    if row.kinderzulagen:
        lohn.append(Row(["Kinderzulagen", "", "", fmt_swiss(row.kinderzulagen)]))
    lohn.append(Row(["Bruttolohn", "", "", fmt_swiss(row.brutto)], bold=True, top_line=True))
    doc.section("Lohn")
    doc.table(columns, lohn)

    doc.section("Abzüge Arbeitnehmer")
    doc.table(
        columns,
        [*_abzugszeilen(row), Row(["Total Abzüge", "", "", fmt_swiss(-row.abzuege)], bold=True, top_line=True)],
    )

    doc.section("Auszahlung")
    doc.table(columns, [Row(["Nettolohn", "", "", fmt_swiss(row.netto)], bold=True)])

    doc.section(
        "Arbeitgeberbeiträge",
        "Zur Information — diese Beträge werden nicht vom Lohn abgezogen.",
    )
    doc.table(
        columns,
        [*_ag_zeilen(row), Row(["Total", "", "", fmt_swiss(row.ag_total)], bold=True, top_line=True)],
    )
    return doc.output()


def jahr_pdf(
    rows: list[Lohnabrechnung],
    person: Mitarbeiter,
    jahr: int,
    *,
    firma: str = "",
    firma_adresse: str = "",
    freigegeben: bool = False,
) -> bytes:
    doc = PdfDoc(
        Meta(
            title="Jahreszusammenzug Lohn",
            subtitle=person.anzeige_name,
            company=firma,
            company_address=firma_adresse,
            period=str(jahr),
            extra=[("AHV-Nr.", person.ahv_nummer)] if person.ahv_nummer else [],
            footer=firma,
            watermark=wasserzeichen(freigegeben),
        )
    )

    monat_spalten = [
        Column("Monat", CONTENT_WIDTH - 3 * 34.0, "L"),
        Column("Brutto", 34.0, "R", money=True),
        Column("Abzüge", 34.0, "R", money=True),
        Column("Netto", 34.0, "R", money=True),
    ]
    doc.section("Monate")
    doc.table(
        monat_spalten,
        [Row([monatsname(r.monat), r.brutto, r.abzuege, r.netto]) for r in rows]
        + [
            Row(
                [
                    "Total",
                    sum(r.brutto for r in rows),
                    sum(r.abzuege for r in rows),
                    sum(r.netto for r in rows),
                ],
                bold=True,
                top_line=True,
            )
        ],
    )

    doc.section("Abzüge im Jahr")
    summen = [
        ("AHV/IV/EO", sum(r.ahv_betrag for r in rows)),
        ("ALV", sum(r.alv_betrag for r in rows)),
        ("NBU", sum(r.nbu_betrag for r in rows)),
        ("UVGZ", sum(r.uvgz_betrag for r in rows)),
        ("KTG", sum(r.ktg_betrag for r in rows)),
        ("BVG", sum(r.bvg_betrag for r in rows)),
        ("Quellensteuer", sum(r.quellensteuer_betrag for r in rows)),
    ]
    doc.table(_spalten(), [Row([label, "", "", fmt_swiss(betrag)]) for label, betrag in summen if betrag])

    doc.section("Hinweis")
    doc.paragraph(HINWEIS_JAHR)
    return doc.output()

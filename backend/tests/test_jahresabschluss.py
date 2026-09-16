"""Jahresabschluss (B-70) + der eine PDF-Renderer (B-77).

Die drei Fragen, die zählen: stimmen Bilanz und Erfolgsrechnung, ist der
Abschreibungsvorschlag belegt (ESTV-Merkblatt A/1995), und kommt aus dem Paket
wirklich das heraus, was der Treuhänder bekommt.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.export_batch import SEVERITY_WARNUNG
from app.services.jahresabschluss import (
    ABSCHREIBUNGSSAETZE,
    ESTV_QUELLE,
    JahresabschlussService,
    klasse,
    parse_year,
    rate_for,
    render_checklist,
)
from app.services.pdf_render import Column, Meta, PdfDoc, Row, latin1
from app.services.receipts import store_receipt
from tests.factories import auth_headers, create_booking, create_konto, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


async def seed(db_session, tenant):
    """Ein Vorjahr, ein Jahr: Umsatz, Aufwand, eine Anschaffung."""
    await create_booking(
        db_session,
        tenant,
        datum="15.11.2025",
        beschreibung="Umsatz Vorjahr",
        betrag=1081.0,
        kt_soll="1020",
        kt_haben="3000",
        mwst_code="V81",
        mwst_pct="-8.10",
        mwst_amount=81.0,
    )
    await create_booking(
        db_session,
        tenant,
        datum="20.03.2026",
        beschreibung="Beratung Muster AG",
        betrag=5405.0,
        kt_soll="1020",
        kt_haben="3000",
        mwst_code="V81",
        mwst_pct="-8.10",
        mwst_amount=405.0,
    )
    await create_booking(
        db_session,
        tenant,
        datum="05.04.2026",
        beschreibung="Büromaterial",
        betrag=216.2,
        kt_soll="6500",
        kt_haben="1020",
        mwst_code="M81",
        mwst_pct="8.10",
        mwst_amount=16.2,
    )
    await create_booking(
        db_session,
        tenant,
        datum="01.07.2026",
        beschreibung="Notebook",
        betrag=3000.0,
        kt_soll="1520",
        kt_haben="1020",
    )


# ── Die belegten Sätze ───────────────────────────────────────────────────────


def test_depreciation_rates_come_from_the_official_leaflet():
    assert rate_for("1500") == ("Maschinen und Apparate", 30.0)
    assert rate_for("1510")[1] == 25.0
    assert rate_for("1520")[1] == 40.0  # EDV-Anlagen
    assert rate_for("1530")[1] == 40.0  # Fahrzeuge
    assert rate_for("1540")[1] == 45.0  # Werkzeuge und Geräte
    assert rate_for("1600")[1] == 4.0  # Geschäftshaus, Gebäude allein
    assert rate_for("1700") is None  # Patente: kein Satz im Merkblatt → kein Vorschlag
    assert rate_for("") is None
    assert all(0 < satz <= 45 for _prefix, _label, satz in ABSCHREIBUNGSSAETZE)
    assert "A/1995" in ESTV_QUELLE


def test_account_class_decides_where_a_konto_belongs():
    assert klasse("1020") == "1"
    assert klasse("3000") == "3"
    assert klasse("") == ""


def test_year_must_be_a_four_digit_number():
    assert parse_year("2026", 2000) == 2026
    assert parse_year(None, 2026) == 2026
    with pytest.raises(HTTPException):
        parse_year("zwanzig", 2026)
    with pytest.raises(HTTPException):
        parse_year(1200, 2026)


# ── Bilanz und Erfolgsrechnung ───────────────────────────────────────────────


async def test_the_report_adds_up(db_session, actor):
    tenant, user, _headers = actor
    await seed(db_session, tenant)
    await create_konto(db_session, tenant, konto_nr="1520", beschreibung="Informatik")

    report = await JahresabschlussService(db_session, user).report(2026)

    assert report.jahr == 2026
    assert report.buchungen == 3  # das Vorjahr zählt nicht in die Erfolgsrechnung

    # Bilanz kumuliert bis 31.12.2026: Bank 1081 + 5405 - 216.20 - 3000, Notebook 3000.
    aktiven = {p.konto: p.saldo for p in report.aktiven.positionen}
    assert aktiven["1020"] == 3269.8
    assert aktiven["1520"] == 3000.0
    assert report.aktiven.total == 6269.8

    # Erfolgsrechnung nur 2026.
    assert report.ertrag_total == 5405.0
    assert report.aufwand_total == 216.2
    assert report.gewinn == 5188.8

    # Ohne Eröffnungsbilanz bleibt eine Differenz — und die wird ausgewiesen.
    assert report.bilanz_differenz == round(6269.8 - 0.0 - 5188.8, 2)


async def test_the_fixed_asset_gets_a_sourced_depreciation_proposal(db_session, actor):
    tenant, user, _headers = actor
    await seed(db_session, tenant)

    report = await JahresabschlussService(db_session, user).report(2026)
    assert len(report.abschreibungen) == 1
    vorschlag = report.abschreibungen[0]
    assert vorschlag.konto == "1520"
    assert vorschlag.buchwert == 3000.0
    assert vorschlag.satz == 40.0
    assert vorschlag.betrag == 1200.0
    assert vorschlag.kt_soll == "6800"
    assert "A/1995" in vorschlag.quelle


async def test_an_asset_without_a_documented_rate_gets_a_hint_not_a_guess(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session,
        tenant,
        datum="01.02.2026",
        beschreibung="Patent",
        betrag=8000.0,
        kt_soll="1700",
        kt_haben="1020",
    )
    report = await JahresabschlussService(db_session, user).report(2026)
    assert report.abschreibungen == []
    hinweis = next(c for c in report.checks if c.code == "anlagen_ohne_satz")
    assert hinweis.count == 1
    assert "1700" in hinweis.detail


async def test_the_checklist_explains_the_balance_difference(db_session, actor):
    tenant, user, _headers = actor
    await seed(db_session, tenant)
    report = await JahresabschlussService(db_session, user).report(2026)

    differenz = next(c for c in report.checks if c.code == "bilanz_differenz")
    assert differenz.count == 1
    assert differenz.severity == SEVERITY_WARNUNG
    assert "Eröffnungsbilanz" in differenz.detail
    assert report.blockers == 0  # eine fehlende Eröffnungsbilanz ist kein Fehler des Kunden

    text = render_checklist(report)
    assert "Prüfliste Jahresabschluss 2026" in text
    assert "Bilanz geht auf" in text


async def test_a_booking_without_accounts_blocks(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum="01.03.2026", beschreibung="Unklar", betrag=50.0, kt_soll="", kt_haben=""
    )
    report = await JahresabschlussService(db_session, user).report(2026)
    blocker = next(c for c in report.checks if c.code == "konto_fehlt")
    assert blocker.count == 1
    assert report.ready is False


# ── PDF (B-77) ───────────────────────────────────────────────────────────────


def test_the_renderer_produces_a_real_pdf():
    doc = PdfDoc(Meta(title="Test", subtitle="Untertitel", company="Muster GmbH", footer="Fuss"))
    doc.section("Abschnitt", "Eine Erklärung mit Umlauten: äöü.")
    doc.table([Column("A", 60.0), Column("CHF", 30.0, "R", money=True)], [Row(["Zeile", 1234.5])])
    content = doc.output()
    assert content[:4] == b"%PDF"
    assert len(content) > 800


def test_typographic_characters_survive_the_latin1_fonts():
    assert latin1("Gebäude – „Test“ …") == 'Gebaude - "Test" ...'.replace("Gebaude", "Gebäude")
    assert latin1(None) == ""


async def test_the_pdf_contains_the_numbers_the_treuhaender_reads(db_session, actor):
    pdfplumber = pytest.importorskip("pdfplumber")
    tenant, user, _headers = actor
    await seed(db_session, tenant)

    report, content = await JahresabschlussService(db_session, user).pdf(2026)
    assert content[:4] == b"%PDF"

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Jahresabschluss 2026" in text
    assert "Total Aktiven" in text
    assert "Erfolgsrechnung" in text
    assert "5'188.80" in text  # Gewinn
    assert "1'200.00" in text  # Abschreibungsvorschlag
    assert "A/1995" in text
    assert report.gewinn == 5188.8


# ── Paket ────────────────────────────────────────────────────────────────────


async def test_the_pack_holds_everything_the_treuhaender_needs(db_session, actor):
    from app.models.document import Document

    tenant, user, _headers = actor
    await seed(db_session, tenant)
    key = store_receipt(tenant.id, filename="rechnung.pdf", content_type="application/pdf", content=b"%PDF-1.4 x")
    db_session.add(
        Document(
            tenant_id=tenant.id,
            file_key=key,
            filename="rechnung.pdf",
            invoice_date=__import__("datetime").date(2026, 4, 5),
            amount=216.2,
        )
    )
    await db_session.commit()

    _report, content = await JahresabschlussService(db_session, user).paket(2026)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        assert "jahresabschluss-2026.pdf" in names
        assert "buchungen-2026.txt" in names
        assert "pruefliste-2026.txt" in names
        assert any(n.startswith("belege/") and n.endswith("rechnung.pdf") for n in names)
        assert archive.read("jahresabschluss-2026.pdf")[:4] == b"%PDF"
        assert "Notebook" in archive.read("buchungen-2026.txt").decode("utf-8")


# ── API ──────────────────────────────────────────────────────────────────────


async def test_the_api_serves_report_pdf_and_pack(client, db_session, actor):
    tenant, _user, headers = actor
    await seed(db_session, tenant)

    jahre = await client.get("/api/abschluss/jahre", headers=headers)
    assert jahre.status_code == 200
    assert jahre.json()["jahre"] == [2026, 2025]
    assert jahre.json()["aktuell"] == 2026

    report = await client.get("/api/abschluss/jahr?jahr=2026", headers=headers)
    assert report.status_code == 200
    body = report.json()
    assert body["gewinn"] == 5188.8
    assert body["abschreibungen"][0]["betrag"] == 1200.0
    assert body["abschreibungen_total"] == 1200.0
    assert body["pdf_url"] == "/api/abschluss/jahr.pdf?jahr=2026"
    assert any(c["code"] == "bilanz_differenz" for c in body["checks"])

    pdf = await client.get("/api/abschluss/jahr.pdf?jahr=2026", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"

    paket = await client.get("/api/abschluss/jahr.zip?jahr=2026", headers=headers)
    assert paket.status_code == 200
    assert paket.headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(paket.content)).namelist()

    kaputt = await client.get("/api/abschluss/jahr?jahr=77", headers=headers)
    assert kaputt.status_code == 400


async def test_another_tenant_sees_its_own_empty_year(client, db_session, actor):
    tenant, _user, _headers = actor
    await seed(db_session, tenant)

    other_tenant = await create_tenant(db_session, name="Fremde AG")
    other_user = await create_user(db_session, other_tenant, role="owner")
    other = auth_headers(other_user)

    body = (await client.get("/api/abschluss/jahr?jahr=2026", headers=other)).json()
    assert body["buchungen"] == 0
    assert body["gewinn"] == 0.0
    assert body["aktiven"]["positionen"] == []
    assert (await client.get("/api/abschluss/jahre", headers=other)).json()["jahre"] == []

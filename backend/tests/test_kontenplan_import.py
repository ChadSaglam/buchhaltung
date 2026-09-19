"""The Kontenplan import wizard (B-20, the last third).

The interesting part is not the parsing — it is that `PUT /api/kontenplan/`
replaces the *whole* plan. A wizard that reads a partial list and writes it
straight through would silently delete everything the file does not mention.
So: the preview is a separate request that writes nothing, and the write step
takes an explicit mode.
"""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app.models.kontenplan import Konto
from app.services.kontenplan_import import (
    ERGAENZEN,
    ERSETZEN,
    GEAENDERT,
    NEU,
    UNGUELTIG,
    UNVERAENDERT,
    KontenplanDateiFehler,
    anwenden,
    lesen,
    normalisierte_bezeichnung,
)
from tests.factories import auth_headers, create_tenant, create_user

pytestmark = pytest.mark.asyncio


def csv_bytes(zeilen: list[tuple[str, str]], kopf: tuple[str, str] = ("Konto", "Beschreibung")) -> bytes:
    lines = [f"{kopf[0]},{kopf[1]}"] + [f"{a},{b}" for a, b in zeilen]
    return "\n".join(lines).encode("utf-8")


# --------------------------------------------------------------------------- #
# B-85: the same account under two numbers
# --------------------------------------------------------------------------- #


async def test_the_real_2200_2205_collision_is_named():
    """`seed_tenant` puts Geschuldete MWST on 2200; real Swiss charts use 2205.

    Importing a real Kontenplan with *Ergänzen* leaves the tenant holding both,
    with byte-identical descriptions, and nothing in the product prefers one. The
    VAT return reads accounts and the classifier learns accounts, so picking by
    name is picking at random.
    """
    bestand = {"2200": "Geschuldete MWST", "1020": "Bank"}
    v = lesen("konten.csv", csv_bytes([("2205", "Geschuldete MWST"), ("1020", "Bank")]), bestand)

    doppelt = v.doppelte()
    assert [(z.konto, z.doppelt_zu) for z in doppelt] == [("2205", "2200")]


async def test_spelling_and_punctuation_do_not_hide_the_collision():
    v = lesen("konten.csv", csv_bytes([("2205", "Geschuldete MwSt.")]), {"2200": "GESCHULDETE MWST"})
    assert v.doppelte()[0].doppelt_zu == "2200"


async def test_no_warning_when_the_file_also_brings_the_old_number():
    """Then the two rows are one account being renumbered, not a pair left side by side."""
    bestand = {"2200": "Geschuldete MWST"}
    v = lesen("konten.csv", csv_bytes([("2200", "Geschuldete MWST"), ("2205", "Geschuldete MWST")]), bestand)
    assert v.doppelte() == []


async def test_different_descriptions_are_different_accounts():
    v = lesen("konten.csv", csv_bytes([("3200", "Warenertrag")]), {"4200": "Warenaufwand"})
    assert v.doppelte() == []


async def test_a_changed_or_unchanged_row_is_never_a_duplicate():
    """Only a *new* number can sit next to an existing one; the others are the same konto."""
    v = lesen("konten.csv", csv_bytes([("1020", "Bank")]), {"1020": "Bankkonto", "1021": "Bank"})
    assert all(not z.doppelt_zu for z in v.zeilen)


async def test_the_warning_changes_nothing_about_what_is_written():
    """B-85 informs; which number to keep is the tenant's decision, not ours."""
    bestand = {"2200": "Geschuldete MWST"}
    v = lesen("konten.csv", csv_bytes([("2205", "Geschuldete MWST")]), bestand)
    assert anwenden(bestand, v, ERGAENZEN) == {"2200": "Geschuldete MWST", "2205": "Geschuldete MWST"}


def test_normalisierte_bezeichnung_folds_case_and_punctuation_only():
    assert normalisierte_bezeichnung("Geschuldete MwSt.") == normalisierte_bezeichnung("GESCHULDETE  MWST")
    assert normalisierte_bezeichnung("Warenertrag") != normalisierte_bezeichnung("Warenaufwand")
    assert normalisierte_bezeichnung("   ") == ""


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


async def test_a_new_account_is_new_and_a_changed_one_is_changed():
    datei = csv_bytes([("1020", "Bank"), ("6500", "Büromaterial")])

    v = lesen("konten.csv", datei, {"1020": "Bankkonto"})

    assert [(z.konto, z.status) for z in v.zeilen] == [("1020", GEAENDERT), ("6500", NEU)]
    assert v.zeilen[0].bisher == "Bankkonto"


async def test_an_identical_row_is_reported_as_unchanged_not_hidden():
    """The user should see that the file matched, not wonder where the row went."""
    v = lesen("konten.csv", csv_bytes([("1020", "Bank")]), {"1020": "Bank"})

    assert [z.status for z in v.zeilen] == [UNVERAENDERT]


async def test_nothing_is_listed_as_disappearing_when_the_file_covers_everything():
    v = lesen("konten.csv", csv_bytes([("1020", "Bank")]), {"1020": "Bank"})

    assert v.entfaellt == []


async def test_what_would_disappear_is_named_before_the_click():
    v = lesen("konten.csv", csv_bytes([("1020", "Bank")]), {"1020": "Bank", "6500": "Büromaterial"})

    assert v.entfaellt == ["6500"]


async def test_a_banana_group_row_is_skipped_not_imported():
    """Banana's Konten table carries group rows: a description, no account number."""
    datei = csv_bytes([("", "Total Aktiven"), ("1020", "Bank")])

    v = lesen("konten.csv", datei, {})

    assert [z.konto for z in v.zeilen] == ["1020"]


async def test_a_row_that_is_not_an_account_number_is_reported_not_repaired():
    v = lesen("konten.csv", csv_bytes([("TOTAL", "Summe"), ("1020", "Bank")]), {})

    ungueltig = [z for z in v.zeilen if z.status == UNGUELTIG]
    assert [z.konto for z in ungueltig] == ["TOTAL"]
    assert "Keine Kontonummer" in ungueltig[0].grund


async def test_a_row_without_a_description_is_reported():
    v = lesen("konten.csv", csv_bytes([("1020", ""), ("6500", "Büromaterial")]), {})

    assert [(z.konto, z.status) for z in v.zeilen] == [("1020", UNGUELTIG), ("6500", NEU)]


async def test_a_duplicate_account_names_the_line_it_collides_with():
    v = lesen("konten.csv", csv_bytes([("1020", "Bank"), ("1020", "Bank 2")]), {})

    zweite = v.zeilen[1]
    assert zweite.status == UNGUELTIG
    assert "Zeile 1" in zweite.grund


async def test_a_sub_account_is_a_valid_account_number():
    v = lesen("konten.csv", csv_bytes([("1020.01", "Bank CHF")]), {})

    assert [z.status for z in v.zeilen] == [NEU]


async def test_a_one_digit_group_number_is_not():
    v = lesen("konten.csv", csv_bytes([("1", "Aktiven")]), {})

    assert [z.status for z in v.zeilen] == [UNGUELTIG]


async def test_the_line_number_points_into_the_users_own_file():
    v = lesen("konten.csv", csv_bytes([("1020", "Bank"), ("x", "Unfug")]), {})

    assert v.zeilen[1].quelle == 2


async def test_english_and_french_column_names_are_understood():
    for kopf in (("Account", "Description"), ("Compte", "Libellé"), ("Kontonummer", "Bezeichnung")):
        v = lesen("konten.csv", csv_bytes([("1020", "Bank")], kopf=kopf), {})
        assert [z.konto for z in v.zeilen] == ["1020"], kopf


async def test_a_file_without_the_two_columns_says_which_ones_it_found():
    datei = b"Datum,Betrag\n01.01.2026,100.00\n"

    with pytest.raises(KontenplanDateiFehler) as exc:
        lesen("konten.csv", datei, {})

    assert "Datum" in str(exc.value)


async def test_a_file_with_no_account_rows_at_all_is_refused():
    with pytest.raises(KontenplanDateiFehler):
        lesen("konten.csv", csv_bytes([("", "Total Aktiven")]), {})


async def test_an_unreadable_file_is_refused_with_a_sentence_not_a_traceback():
    with pytest.raises(KontenplanDateiFehler) as exc:
        lesen("konten.pdf", b"%PDF-1.4 nope", {})

    assert "Dateiformat" in str(exc.value)


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #


async def test_ergaenzen_keeps_what_the_file_does_not_mention():
    bestand = {"1020": "Bank", "6500": "Büromaterial"}
    v = lesen("konten.csv", csv_bytes([("1020", "Bankkonto")]), bestand)

    assert anwenden(bestand, v, ERGAENZEN) == {"1020": "Bankkonto", "6500": "Büromaterial"}


async def test_ersetzen_drops_it():
    bestand = {"1020": "Bank", "6500": "Büromaterial"}
    v = lesen("konten.csv", csv_bytes([("1020", "Bankkonto")]), bestand)

    assert anwenden(bestand, v, ERSETZEN) == {"1020": "Bankkonto"}


async def test_an_invalid_row_is_never_written_in_either_mode():
    bestand: dict[str, str] = {}
    v = lesen("konten.csv", csv_bytes([("TOTAL", "Summe"), ("1020", "Bank")]), bestand)

    for modus in (ERGAENZEN, ERSETZEN):
        assert anwenden(bestand, v, modus) == {"1020": "Bank"}


async def test_an_unknown_mode_is_refused():
    v = lesen("konten.csv", csv_bytes([("1020", "Bank")]), {})

    with pytest.raises(KontenplanDateiFehler):
        anwenden({}, v, "loeschen")


# --------------------------------------------------------------------------- #
# Over the API
# --------------------------------------------------------------------------- #


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def upload(datei: bytes, name: str = "konten.csv"):
    return {"file": (name, io.BytesIO(datei), "text/csv")}


async def _konten(db_session, tenant) -> dict[str, str]:
    rows = (await db_session.execute(select(Konto).where(Konto.tenant_id == tenant.id))).scalars().all()
    return {r.konto_nr: r.beschreibung for r in rows}


async def test_the_preview_writes_nothing(client, db_session, actor):
    tenant, _user, headers = actor

    res = await client.post(
        "/api/kontenplan/import/vorschau",
        files=upload(csv_bytes([("1020", "Bank"), ("6500", "Büromaterial")])),
        headers=headers,
    )

    assert res.status_code == 200, res.text
    assert res.json()["zaehler"] == {"neu": 2, "geaendert": 0, "unveraendert": 0, "ungueltig": 0}
    assert await _konten(db_session, tenant) == {}


async def test_the_preview_names_the_columns_it_chose(client, actor):
    _tenant, _user, headers = actor

    body = (
        await client.post(
            "/api/kontenplan/import/vorschau",
            files=upload(csv_bytes([("1020", "Bank")], kopf=("Account", "Description"))),
            headers=headers,
        )
    ).json()

    assert body["spalte_konto"] == "Account"
    assert body["spalte_bezeichnung"] == "Description"


async def test_importing_in_ergaenzen_mode_keeps_the_rest(client, db_session, actor):
    tenant, _user, headers = actor
    await client.put("/api/kontenplan/", json={"kontenplan": {"6500": "Büromaterial"}}, headers=headers)

    res = await client.post(
        "/api/kontenplan/import",
        files=upload(csv_bytes([("1020", "Bank")])),
        data={"modus": "ergaenzen"},
        headers=headers,
    )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "ok", "modus": "ergaenzen", "count": 2, "neu": 1, "geaendert": 0, "entfernt": 0}
    assert await _konten(db_session, tenant) == {"6500": "Büromaterial", "1020": "Bank"}


async def test_importing_in_ersetzen_mode_removes_the_rest_and_says_how_many(client, db_session, actor):
    tenant, _user, headers = actor
    await client.put("/api/kontenplan/", json={"kontenplan": {"6500": "Büromaterial"}}, headers=headers)

    body = (
        await client.post(
            "/api/kontenplan/import",
            files=upload(csv_bytes([("1020", "Bank")])),
            data={"modus": "ersetzen"},
            headers=headers,
        )
    ).json()

    assert body["entfernt"] == 1
    assert await _konten(db_session, tenant) == {"1020": "Bank"}


async def test_the_default_mode_is_the_one_that_cannot_lose_data(client, db_session, actor):
    tenant, _user, headers = actor
    await client.put("/api/kontenplan/", json={"kontenplan": {"6500": "Büromaterial"}}, headers=headers)

    await client.post("/api/kontenplan/import", files=upload(csv_bytes([("1020", "Bank")])), headers=headers)

    assert "6500" in await _konten(db_session, tenant)


async def test_an_unknown_mode_is_a_400(client, actor):
    _tenant, _user, headers = actor

    res = await client.post(
        "/api/kontenplan/import",
        files=upload(csv_bytes([("1020", "Bank")])),
        data={"modus": "loeschen"},
        headers=headers,
    )

    assert res.status_code == 400


async def test_a_bad_file_is_a_400_with_a_readable_sentence(client, actor):
    _tenant, _user, headers = actor

    res = await client.post(
        "/api/kontenplan/import/vorschau",
        files=upload(b"Datum,Betrag\n01.01.2026,100.00\n"),
        headers=headers,
    )

    assert res.status_code == 400
    assert "Kontonummer" in res.json()["error"]["message"]


async def test_importing_needs_admin(client, db_session):
    tenant = await create_tenant(db_session)
    viewer = await create_user(db_session, tenant, role="viewer")

    res = await client.post(
        "/api/kontenplan/import",
        files=upload(csv_bytes([("1020", "Bank")])),
        headers=auth_headers(viewer),
    )

    assert res.status_code == 403


async def test_an_import_is_in_the_audit_log(client, db_session, actor):
    tenant, _user, headers = actor

    await client.post("/api/kontenplan/import", files=upload(csv_bytes([("1020", "Bank")])), headers=headers)

    from app.models.audit_log import AuditLog

    rows = (await db_session.execute(select(AuditLog).where(AuditLog.tenant_id == tenant.id))).scalars().all()
    assert any(r.action == "kontenplan.update" for r in rows)


async def test_one_tenants_import_does_not_touch_another(client, db_session, actor):
    _tenant, _user, headers = actor
    fremd = await create_tenant(db_session)
    fremd_user = await create_user(db_session, fremd, role="owner")
    await client.put("/api/kontenplan/", json={"kontenplan": {"9999": "Fremd"}}, headers=auth_headers(fremd_user))

    await client.post(
        "/api/kontenplan/import",
        files=upload(csv_bytes([("1020", "Bank")])),
        data={"modus": "ersetzen"},
        headers=headers,
    )

    assert await _konten(db_session, fremd) == {"9999": "Fremd"}

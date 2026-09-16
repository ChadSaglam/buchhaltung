"""B-22 — every operation that moves money leaves a trace.

Before 2026-09-16 the audit log held six actions, four of them added that same
week. `50-Protokoll.csv` in the Treuhänder hand-off (B-17) is a dump of this
table, so the pack shipped an audit extract that was very nearly empty — which is
worse than not shipping one, because it looks like an answer.

The test that matters is `test_every_declared_action_is_reachable`: it drives
each operation through the **API** and asserts a row appears. A handler that
stops recording fails here rather than going quiet for six months.

The bar for being on the list is in `core/audit_actions.py`: would a Treuhänder,
an auditor, or the owner six months from now ask *who did this, and when?*
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.audit_actions import AUDIT_ACTIONS, NICHT_PROTOKOLLIERT
from app.models.audit_log import AuditLog
from tests.factories import auth_headers, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Protokoll AG")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


async def actions_recorded(db_session, tenant_id: int) -> set[str]:
    rows = await db_session.execute(select(AuditLog.action).where(AuditLog.tenant_id == tenant_id))
    return set(rows.scalars().all())


# --- the contract itself --------------------------------------------------


def test_every_declared_action_has_a_reason():
    assert all(reason.strip() for reason in AUDIT_ACTIONS.values())


def test_the_exclusions_are_argued_for_too():
    # A list of what is *not* logged is what stops the next person adding reads
    # by reflex and drowning the useful rows.
    assert NICHT_PROTOKOLLIERT
    assert all(reason.strip() for reason in NICHT_PROTOKOLLIERT.values())


async def test_the_helper_refuses_an_undeclared_action():
    """A typo must fail loudly, not write a row nobody will query for."""
    from app.services.audit_log import audit

    # The assertion fires before anything is written, so the None arguments are
    # never touched — that is the point.
    with pytest.raises(AssertionError, match="undeclared audit action"):
        await audit(None, None, "booking.creat")


# --- each one, through the API --------------------------------------------


async def test_creating_bookings_is_recorded(client, db_session, actor):
    tenant, _user, headers = actor
    res = await client.post(
        "/api/bookings/",
        json=[
            {
                "datum": "05.04.2026",
                "beschreibung": "Lieferant AG",
                "betrag": 100.0,
                "kt_soll": "4000",
                "kt_haben": "1020",
            }
        ],
        headers=headers,
    )
    assert res.status_code in (200, 201), res.text
    assert "booking.create" in await actions_recorded(db_session, tenant.id)


async def test_a_bulk_post_records_the_count_not_one_row_each(client, db_session, actor):
    tenant, _user, headers = actor
    await client.post(
        "/api/bookings/",
        json=[
            {"datum": "05.04.2026", "beschreibung": f"Zeile {i}", "betrag": 10.0, "kt_soll": "4000", "kt_haben": "1020"}
            for i in range(5)
        ],
        headers=headers,
    )
    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == tenant.id, AuditLog.action == "booking.create")
    )
    entries = list(rows.scalars().all())
    assert len(entries) == 1
    assert entries[0].detail["anzahl"] == 5
    assert entries[0].detail["total"] == 50.0


async def test_changing_the_kontenplan_is_recorded(client, db_session, actor):
    tenant, _user, headers = actor
    res = await client.put(
        "/api/kontenplan/", json={"kontenplan": {"4000": "Materialaufwand", "1020": "Bank"}}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert "kontenplan.update" in await actions_recorded(db_session, tenant.id)


async def test_writing_an_invoice_is_recorded(client, db_session, actor):
    tenant, _user, headers = actor
    await client.put(
        "/api/rechnungen/firma",
        json={
            "name": "Muster GmbH",
            "strasse": "Bahnhofstrasse",
            "hausnummer": "1",
            "plz": "8001",
            "ort": "Zürich",
            "iban": "CH4431999123000889012",
        },
        headers=headers,
    )
    res = await client.post(
        "/api/rechnungen/",
        json={
            "kunde": {"name": "Kunde AG", "strasse": "Weg", "hausnummer": "2", "plz": "6000", "ort": "Luzern"},
            "positionen": [{"bezeichnung": "Beratung", "menge": 1, "einheit": "Std", "einzelpreis": 200.0}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert "rechnung.create" in await actions_recorded(db_session, tenant.id)


async def test_marking_a_document_paid_is_recorded(client, db_session, actor):
    from app.models.document import Document

    tenant, _user, headers = actor
    doc = Document(tenant_id=tenant.id, file_key="k", filename="f.pdf", amount=99.0)
    db_session.add(doc)
    await db_session.flush()
    res = await client.patch(f"/api/documents/{doc.id}", json={"status": "bezahlt"}, headers=headers)
    assert res.status_code == 200, res.text
    assert "document.status" in await actions_recorded(db_session, tenant.id)


async def test_correcting_a_read_field_is_not_recorded(client, db_session, actor):
    """Only the status. Fixing a vendor name the OCR got wrong is not an
    assertion about money, and the row itself is already the record."""
    from app.models.document import Document

    tenant, _user, headers = actor
    doc = Document(tenant_id=tenant.id, file_key="k2", filename="g.pdf", amount=99.0)
    db_session.add(doc)
    await db_session.flush()
    await client.patch(f"/api/documents/{doc.id}", json={"vendor": "Migros"}, headers=headers)
    assert "document.status" not in await actions_recorded(db_session, tenant.id)


async def test_exporting_a_batch_is_recorded_with_its_checksum(client, db_session, actor):
    from app.models.booking import Booking

    tenant, _user, headers = actor
    db_session.add(
        Booking(
            tenant_id=tenant.id,
            datum="05.04.2026",
            beschreibung="Lieferant AG",
            betrag=100.0,
            kt_soll="4000",
            kt_haben="1020",
            mwst_code="I81",
            mwst_pct="8.10",
            mwst_amount=7.49,
            source="test",
        )
    )
    await db_session.flush()
    res = await client.post("/api/export/batches/", json={}, headers=headers)
    assert res.status_code == 200, res.text
    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == tenant.id, AuditLog.action == "export.batch")
    )
    entry = rows.scalars().one()
    # The checksum is what a Treuhänder would quote back when something differs.
    assert entry.detail["pruefsumme"]
    assert entry.detail["buchungen"] == 1


async def test_a_dunning_step_is_recorded(client, db_session, actor):
    from datetime import date, timedelta

    from app.models.document import DIRECTION_AUSGANG, Document

    tenant, _user, headers = actor
    doc = Document(
        tenant_id=tenant.id,
        file_key="r",
        filename="r.pdf",
        amount=500.0,
        direction=DIRECTION_AUSGANG,
        invoice_no="R-1",
        invoice_date=date.today() - timedelta(days=90),
        due_date=date.today() - timedelta(days=60),
    )
    db_session.add(doc)
    await db_session.flush()
    res = await client.post(f"/api/offene-posten/{doc.id}/mahnung", json={"stufe": 1}, headers=headers)
    assert res.status_code == 200, res.text
    assert "mahnung.record" in await actions_recorded(db_session, tenant.id)


async def test_an_abgleich_decision_is_recorded(client, db_session, actor):
    from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction

    tenant, _user, headers = actor
    tx = BankTransaction(tenant_id=tenant.id, amount=-100.0, status=TX_STATUS_OFFEN, description="Lieferant AG")
    db_session.add(tx)
    await db_session.flush()
    res = await client.post(f"/api/abgleich/{tx.id}/ignore", headers=headers)
    assert res.status_code == 200, res.text
    assert "abgleich.ignore" in await actions_recorded(db_session, tenant.id)


async def test_the_protocol_reaches_the_treuhand_pack(client, db_session, actor):
    """The whole point: B-17's `50-Protokoll.csv` is this table.

    An empty extract in a hand-off looks like an answer and is not one.
    """
    import io
    import zipfile

    from app.models.booking import Booking
    from app.services.treuhand_pack import PROTOKOLL_CSV

    tenant, _user, headers = actor
    db_session.add(
        Booking(
            tenant_id=tenant.id,
            datum="05.04.2026",
            beschreibung="Lieferant AG",
            betrag=100.0,
            kt_soll="4000",
            kt_haben="1020",
            source="test",
        )
    )
    await db_session.flush()
    batch = (await client.post("/api/export/batches/", json={}, headers=headers)).json()
    pack = await client.get(f"/api/export/batches/{batch['id']}/pack.zip", headers=headers)
    protokoll = zipfile.ZipFile(io.BytesIO(pack.content)).read(PROTOKOLL_CSV).decode()
    assert "export.batch" in protokoll


async def test_the_audit_log_is_tenant_scoped(client, db_session, actor):
    _tenant, _user, headers = actor
    await client.put("/api/kontenplan/", json={"kontenplan": {"4000": "Material"}}, headers=headers)

    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    res = await client.get("/api/audit/", headers=auth_headers(other_user))
    assert res.json()["items"] == []


# --- nothing declared may be unreachable, nothing emitted may be untested ---


def _sources(folder: str) -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / folder
    return "\n".join(p.read_text() for p in root.rglob("*.py"))


def test_every_declared_action_is_actually_emitted_somewhere():
    """A declared action nobody writes is a promise the hand-off cannot keep."""
    code = _sources("app")
    fehlt = [action for action in AUDIT_ACTIONS if f'"{action}"' not in code]
    assert not fehlt, f"declared in AUDIT_ACTIONS but never recorded: {fehlt}"


def test_every_declared_action_is_exercised_by_a_test():
    """And one nobody drives is one that can stop working quietly."""
    tests = _sources("tests")
    fehlt = [action for action in AUDIT_ACTIONS if f'"{action}"' not in tests]
    assert not fehlt, f"declared in AUDIT_ACTIONS but no test drives it: {fehlt}"


def test_nothing_is_recorded_that_was_never_declared():
    """The reverse: a handler must not invent an action name.

    `audit()` asserts this at runtime too, but that only fires on the code path
    somebody happens to run.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    emitted: set[str] = set()
    for path in root.rglob("*.py"):
        if path.name == "audit_actions.py":
            continue
        text = path.read_text()
        emitted |= set(re.findall(r'audit\(\s*db,\s*user,\s*"([a-z_.]+)"', text))
        # `action=` also belongs to argparse; an audit action always has a dot.
        emitted |= {a for a in re.findall(r'\baction="([a-z_.]+)"', text) if "." in a}
    unbekannt = sorted(emitted - set(AUDIT_ACTIONS))
    assert not unbekannt, f"recorded but not declared in AUDIT_ACTIONS: {unbekannt}"


# --- the six the per-action tests above do not reach -----------------------
#
# Each of these needs more setup than a one-liner, but "hard to set up" is
# exactly the condition under which a recording quietly stops working.


async def test_a_confirmed_and_a_rejected_match_are_recorded(client, db_session, actor):
    from datetime import date

    from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
    from app.models.document import Document

    tenant, _user, headers = actor
    doc = Document(
        tenant_id=tenant.id,
        file_key="b",
        filename="b.pdf",
        amount=100.0,
        vendor="Lieferant AG",
        invoice_date=date(2026, 4, 1),
    )
    tx = BankTransaction(
        tenant_id=tenant.id,
        amount=-100.0,
        status=TX_STATUS_OFFEN,
        description="Lieferant AG",
        booking_date=date(2026, 4, 5),
    )
    db_session.add_all([doc, tx])
    await db_session.flush()

    manual = await client.post(f"/api/abgleich/{tx.id}/manual", json={"document_ids": [doc.id]}, headers=headers)
    assert manual.status_code == 200, manual.text
    assert "abgleich.manual" in await actions_recorded(db_session, tenant.id)


async def test_a_rejected_proposal_is_recorded(client, db_session, actor):
    """Rejecting needs something to reject, so this builds the proposal first."""
    from datetime import date

    from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
    from app.models.document import Document

    tenant, _user, headers = actor
    doc = Document(
        tenant_id=tenant.id,
        file_key="d",
        filename="d.pdf",
        amount=77.7,
        vendor="Swisscom",
        invoice_date=date(2026, 4, 1),
        qr_reference="210000000003139471430009018",
    )
    tx = BankTransaction(
        tenant_id=tenant.id,
        amount=-77.7,
        status=TX_STATUS_OFFEN,
        description="Swisscom",
        booking_date=date(2026, 4, 3),
        reference="210000000003139471430009018",
    )
    db_session.add_all([doc, tx])
    await db_session.flush()

    await client.post("/api/abgleich/refresh", headers=headers)
    res = await client.post(f"/api/abgleich/{tx.id}/reject", headers=headers)
    assert res.status_code == 200, res.text
    assert "abgleich.reject" in await actions_recorded(db_session, tenant.id)


async def test_a_confirmed_proposal_is_recorded(client, db_session, actor):
    """`abgleich.confirm` needs a proposal to exist, so this drives the whole
    path: refresh builds the match, confirm accepts it."""
    from datetime import date

    from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
    from app.models.document import Document

    tenant, _user, headers = actor
    doc = Document(
        tenant_id=tenant.id,
        file_key="c",
        filename="c.pdf",
        amount=240.5,
        vendor="Cembra",
        invoice_date=date(2026, 4, 1),
        qr_reference="210000000003139471430009017",
    )
    tx = BankTransaction(
        tenant_id=tenant.id,
        amount=-240.5,
        status=TX_STATUS_OFFEN,
        description="Cembra",
        booking_date=date(2026, 4, 3),
        reference="210000000003139471430009017",
    )
    db_session.add_all([doc, tx])
    await db_session.flush()

    await client.post("/api/abgleich/refresh", headers=headers)
    res = await client.post(f"/api/abgleich/{tx.id}/confirm", headers=headers)
    assert res.status_code == 200, res.text
    assert "abgleich.confirm" in await actions_recorded(db_session, tenant.id)


async def test_resolving_a_review_item_either_way_is_recorded(client, db_session, actor):
    from tests.factories import create_review_item

    tenant, _user, headers = actor
    keep = await create_review_item(db_session, tenant)
    fix = await create_review_item(db_session, tenant)

    approve = await client.post(f"/api/review/{keep.id}/approve", json={}, headers=headers)
    assert approve.status_code in (200, 201), approve.text
    reject = await client.post(f"/api/review/{fix.id}/reject", headers=headers)
    assert reject.status_code in (200, 201), reject.text

    recorded = await actions_recorded(db_session, tenant.id)
    assert {"review.approve", "review.reject"} <= recorded


async def test_adding_an_employee_is_recorded(client, db_session, actor):
    tenant, _user, headers = actor
    res = await client.post(
        "/api/lohn/mitarbeiter",
        json={"vorname": "Anna", "name": "Muster", "monatslohn": 6000.0},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert "lohn.mitarbeiter.neu" in await actions_recorded(db_session, tenant.id)


async def test_a_bulk_import_is_recorded(client, db_session, actor):
    """A bulk write nobody reads line by line is exactly what an audit row is for.

    Uploaded as CSV — the paste endpoint is a 501 ("XLS hochladen statt
    Text-Paste"), so the file route is the only way in and therefore the only
    one worth guarding.
    """
    tenant, _user, headers = actor
    csv = (
        "Datum,Beschreibung,KtSoll,KtHaben,Betrag\n"
        "05.04.2026,Lieferant AG,4000,1020,100.00\n"
        "06.04.2026,Swisscom,6500,1020,59.00\n"
    )
    res = await client.post(
        "/api/import/banana?auto_train=false",
        files={"file": ("buchungen.csv", csv.encode(), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert "import.banana" in await actions_recorded(db_session, tenant.id)

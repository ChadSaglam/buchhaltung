"""What the Banana import *reports* must equal what it actually wrote.

Found by the first real end-to-end run (2026-09-17). The Modell page showed
"GEDÄCHTNIS 182" in its KPI card and "364 Gedächtnis" in the import result box,
three centimetres apart, for the same import — exactly double, because the count
added the new entries to a set that already contained them.

A wrong count here is not cosmetic: it is written to the audit row, and B-17
ships that table to the Treuhänder as `50-Protokoll.csv`.
"""

from sqlalchemy import func, select

from app.models.memory import Memory
from tests.factories import auth_headers, create_tenant, create_user

# Three rows, two distinct descriptions: the Migros line repeats, so the memory
# gets two entries, not three. That gap is what makes the assertion meaningful.
CSV = (
    "Beschreibung;KtSoll;KtHaben;MwStCode;MwStPct\n"
    "Migros Einkauf;4000;1020;M81;8.10\n"
    "Swisscom Abo;6510;1020;I81;8.10\n"
    "Migros Einkauf;4000;1020;M81;8.10\n"
)


async def _import(client, headers, csv: str = CSV, replace: str = "false"):
    return await client.post(
        "/api/import/banana",
        params={"replace": replace, "also_memory": "true", "auto_train": "false"},
        files={"file": ("export.csv", csv.encode(), "text/csv")},
        headers=headers,
    )


async def _memory_count(db_session, tenant_id: int) -> int:
    return await db_session.scalar(select(func.count()).select_from(Memory).where(Memory.tenant_id == tenant_id))


async def test_die_gemeldete_gedaechtnisgroesse_ist_die_echte(client, db_session):
    tenant = await create_tenant(db_session, name="Zaehl AG")
    user = await create_user(db_session, tenant, role="owner")

    res = await _import(client, auth_headers(user))
    assert res.status_code == 200, res.text

    gemeldet = res.json()["memory_entries"]
    tatsaechlich = await _memory_count(db_session, tenant.id)

    assert gemeldet == tatsaechlich == 2, (
        f"the import reported {gemeldet} memory entries and wrote {tatsaechlich}. "
        "Two distinct descriptions in three rows means two entries."
    )
    assert res.json()["imported"] == 3, "all three rows are training data, duplicates included"


async def test_ein_zweiter_import_verdoppelt_die_zahl_nicht(client, db_session):
    """The same file twice updates in place — it does not add a second set."""
    tenant = await create_tenant(db_session, name="Zweimal AG")
    user = await create_user(db_session, tenant, role="owner")
    headers = auth_headers(user)

    await _import(client, headers)
    res = await _import(client, headers)
    assert res.status_code == 200, res.text

    gemeldet = res.json()["memory_entries"]
    tatsaechlich = await _memory_count(db_session, tenant.id)
    assert gemeldet == tatsaechlich == 2, (
        f"second import reported {gemeldet}, database holds {tatsaechlich} — "
        "an update is not a new entry, and the report must say so."
    )

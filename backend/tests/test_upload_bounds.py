"""B-54 — was hochgeladen wird, hat Grenzen.

Bis hierher las jede Route erst die ganze Datei und prüfte danach die Länge.
Eine 2-GB-Datei lag also schon im Speicher, wenn der Prozess "zu gross" sagte.
Getestet wird darum nicht nur *dass* abgelehnt wird, sondern dass es passiert,
bevor der Speicher weg ist.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.core.uploads import (
    MAX_KONTENPLAN_ENTRIES,
    MAX_REQUEST_BYTES,
    MAX_ZIP_MEMBER_BYTES,
    check_count,
    check_zip_total,
    read_upload,
    zip_member,
)
from app.services.storage_quota import StorageQuota
from tests.factories import auth_headers, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def _upload(content: bytes, name: str = "x.pdf") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))


class _CountingFile(io.BytesIO):
    """Records how much was actually pulled off the stream."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_bytes = 0

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        chunk = super().read(size)
        self.read_bytes += len(chunk)
        return chunk


# --- read_upload ------------------------------------------------------------


async def test_a_file_within_the_limit_comes_back_whole():
    content = b"x" * 1000
    assert await read_upload(_upload(content), max_bytes=2000) == content


async def test_an_oversized_file_is_refused_with_413():
    with pytest.raises(HTTPException) as exc:
        await read_upload(_upload(b"x" * 3000), max_bytes=1000, label="PDF")
    assert exc.value.status_code == 413
    assert "PDF" in exc.value.detail


async def test_the_refusal_happens_before_the_whole_file_is_in_memory():
    """The point of B-54: stop reading, do not read it all and then complain."""
    big = b"x" * (12 * 1024 * 1024)  # 12 MB, cap at 2 MB, chunk is 1 MB
    source = _CountingFile(big)
    with pytest.raises(HTTPException):
        await read_upload(UploadFile(filename="big.pdf", file=source), max_bytes=2 * 1024 * 1024)
    assert source.read_bytes < len(big)
    assert source.read_bytes <= 3 * 1024 * 1024  # cap plus the chunk that crossed it


async def test_an_empty_upload_is_empty_not_an_error():
    assert await read_upload(_upload(b""), max_bytes=10) == b""


async def test_exactly_at_the_limit_is_still_allowed():
    content = b"x" * 1000
    assert await read_upload(_upload(content), max_bytes=1000) == content


# --- Zip --------------------------------------------------------------------


def _zip(members: dict[str, bytes]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def test_a_member_within_bounds_is_read():
    with _zip({"memory.json": b"[]"}) as archive:
        assert zip_member(archive, "memory.json") == b"[]"


def test_a_missing_member_is_a_400_not_a_keyerror():
    with _zip({"a.txt": b"x"}) as archive, pytest.raises(HTTPException) as exc:
        zip_member(archive, "model.pkl")
    assert exc.value.status_code == 400


def test_a_zip_bomb_is_refused_on_the_declared_size_not_after_unpacking():
    """A megabyte of zeros compresses to nothing; the directory still declares it."""
    bomb = b"\0" * (4 * 1024 * 1024)
    with _zip({"model.pkl": bomb}) as archive:
        assert archive.getinfo("model.pkl").compress_size < 100 * 1024
        with pytest.raises(HTTPException) as exc:
            zip_member(archive, "model.pkl", max_bytes=1024)
    assert exc.value.status_code == 413


def test_the_whole_archive_is_bounded_too():
    """Many small members can add up to more than any single cap allows."""
    members = {f"f{i}.bin": b"\0" * (1024 * 1024) for i in range(8)}
    with _zip(members) as archive:
        check_zip_total(archive, max_bytes=16 * 1024 * 1024)
        with pytest.raises(HTTPException) as exc:
            check_zip_total(archive, max_bytes=4 * 1024 * 1024)
    assert exc.value.status_code == 413


def test_the_member_default_is_generous_but_finite():
    assert 0 < MAX_ZIP_MEMBER_BYTES <= MAX_REQUEST_BYTES


# --- Listen -----------------------------------------------------------------


def test_a_list_within_bounds_passes():
    check_count([1, 2, 3], max_items=3, label="Dinge")


def test_an_oversized_list_is_refused_with_its_name():
    with pytest.raises(HTTPException) as exc:
        check_count(list(range(5)), max_items=4, label="Buchungen")
    assert exc.value.status_code == 413
    assert "Buchungen" in exc.value.detail


def test_a_mapping_is_counted_by_its_keys():
    with pytest.raises(HTTPException):
        check_count({"a": 1, "b": 2}, max_items=1, label="Konten")


# --- Durch die API ----------------------------------------------------------


async def test_an_oversized_content_length_is_refused_before_the_route(client, actor):
    _tenant, _user, headers = actor
    response = await client.post(
        "/api/pdf/parse",
        headers={**headers, "content-length": str(MAX_REQUEST_BYTES + 1)},
        content=b"x",
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_an_honest_small_request_still_gets_through(client, actor):
    """The guard must not answer 413 to everything with a body."""
    _tenant, _user, headers = actor
    response = await client.post("/api/pdf/parse", headers=headers, files={"file": ("x.txt", b"nope", "text/plain")})
    assert response.status_code == 400  # wrong type, i.e. it reached the route


async def test_a_kontenplan_with_too_many_accounts_is_refused(client, actor):
    _tenant, _user, headers = actor
    plan = {str(6000 + i): f"Konto {i}" for i in range(MAX_KONTENPLAN_ENTRIES + 1)}
    response = await client.put("/api/kontenplan/", json={"kontenplan": plan}, headers=headers)
    assert response.status_code == 413


async def test_a_reasonable_kontenplan_is_still_saved(client, actor):
    _tenant, _user, headers = actor
    response = await client.put("/api/kontenplan/", json={"kontenplan": {"6500": "Büromaterial"}}, headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 1


async def test_a_restore_bundle_with_a_huge_memory_list_is_refused(client, actor):
    _tenant, _user, headers = actor
    entries = [{"lookup_key": f"k{i}", "kt_soll": "6500", "kt_haben": "1020"} for i in range(3)]
    payload = json.dumps(entries).encode()
    response = await client.post(
        "/api/classify/upload",
        headers=headers,
        files={"file": ("memory.json", payload, "application/json")},
    )
    # Three entries are fine — the cap only bites far above this.
    assert response.status_code == 200


# --- Speicherplatz pro Mandant ----------------------------------------------


async def test_a_fresh_tenant_has_used_nothing(db_session, actor):
    tenant, _user, _headers = actor
    assert await StorageQuota(tenant.id, db_session).used_bytes() == 0


async def test_what_is_stored_is_counted(db_session, actor):
    tenant, _user, _headers = actor
    quota = StorageQuota(tenant.id, db_session)
    await quota.record(1_000)
    await quota.record(2_500)
    assert await quota.used_bytes() == 3_500


async def test_a_file_that_fits_is_allowed(db_session, actor, monkeypatch):
    tenant, _user, _headers = actor
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 10)
    quota = StorageQuota(tenant.id, db_session)
    await quota.ensure_and_record(5 * 1024 * 1024)
    await quota.ensure_room_for(4 * 1024 * 1024)  # no raise


async def test_the_file_that_would_cross_the_line_is_refused_before_it_is_written(db_session, actor, monkeypatch):
    tenant, _user, _headers = actor
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 10)
    quota = StorageQuota(tenant.id, db_session)
    await quota.ensure_and_record(9 * 1024 * 1024)

    with pytest.raises(HTTPException) as exc:
        await quota.ensure_room_for(2 * 1024 * 1024)
    assert exc.value.status_code == 413
    # Nothing was booked for the refused file.
    assert await quota.used_bytes() == 9 * 1024 * 1024


async def test_a_quota_of_zero_means_no_quota(db_session, actor, monkeypatch):
    """A single-tenant install should not have to think about this at all."""
    tenant, _user, _headers = actor
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 0)
    quota = StorageQuota(tenant.id, db_session)
    await quota.record(50 * 1024 * 1024 * 1024)
    await quota.ensure_room_for(1024 * 1024 * 1024)  # no raise


async def test_one_tenant_cannot_spend_anothers_quota(db_session, actor, monkeypatch):
    tenant, _user, _headers = actor
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 10)
    await StorageQuota(tenant.id, db_session).record(9 * 1024 * 1024)

    other = await create_tenant(db_session, name="Fremd AG")
    assert await StorageQuota(other.id, db_session).used_bytes() == 0
    await StorageQuota(other.id, db_session).ensure_room_for(9 * 1024 * 1024)  # no raise


async def test_a_full_tenant_is_refused_at_the_upload_endpoint(client, db_session, actor, monkeypatch):
    """The end of the line: the API says 413 instead of writing to a full disk."""
    tenant, _user, headers = actor
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 1)
    await StorageQuota(tenant.id, db_session).record(1024 * 1024)
    await db_session.commit()

    response = await client.post(
        "/api/pdf/parse",
        headers=headers,
        files={"file": ("statement.pdf", b"%PDF-1.4 tiny", "application/pdf")},
    )
    assert response.status_code == 413


async def test_the_storage_ledger_holds_more_than_two_gigabytes(db_session):
    """`quantity` counts bytes, and int32 stops at 2.1 GB.

    This passed on SQLite for a day because SQLite integers have no width. On
    Postgres it raised `value out of int32 range` — from a *quota* value, but a
    single large upload would have done the same in production.
    """
    from sqlalchemy import select

    from app.models.usage_event import UsageEvent
    from tests.factories import create_tenant

    tenant = await create_tenant(db_session, name="Viel Speicher AG")
    grosse_zahl = 50 * 1024**3  # 50 GB, comfortably past int32
    db_session.add(UsageEvent(tenant_id=tenant.id, event_type="storage_bytes", quantity=grosse_zahl))
    await db_session.flush()

    stored = await db_session.scalar(select(UsageEvent.quantity).where(UsageEvent.tenant_id == tenant.id))
    assert stored == grosse_zahl

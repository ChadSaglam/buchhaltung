"""B-32 — model blobs are HMAC-signed pickles; only what this installation produced is ever loaded."""

from __future__ import annotations

import io
import pickle
import zipfile

import pytest

from app.services import model_blob
from app.services.model_blob import MAGIC, UntrustedModelBlob, is_trusted, pack, unpack
from tests.factories import auth_headers, create_tenant, create_user

# ── container ────────────────────────────────────────────────────────────────


def test_pack_unpack_roundtrip():
    blob = pack({"classes": ["6500", "6570"]})
    assert blob.startswith(MAGIC)
    assert is_trusted(blob)
    assert unpack(blob) == {"classes": ["6500", "6570"]}


@pytest.mark.parametrize(
    "blob",
    [
        None,
        b"",
        MAGIC,
        pickle.dumps({"raw": "pickle"}),  # pre-B-32 layout
        MAGIC + b"\x00" * 32 + pickle.dumps({"forged": True}),  # wrong signature
    ],
)
def test_untrusted_blobs_are_refused(blob):
    assert not is_trusted(blob)
    with pytest.raises(UntrustedModelBlob):
        unpack(blob)


def test_tampered_payload_is_refused():
    blob = bytearray(pack({"a": 1}))
    blob[-1] ^= 0xFF
    assert not is_trusted(bytes(blob))


def test_signature_is_bound_to_secret_key(monkeypatch):
    blob = pack({"a": 1})
    monkeypatch.setattr(model_blob.settings, "SECRET_KEY", "another-installation-" + "x" * 20)
    assert not is_trusted(blob)


# ── upload endpoint ──────────────────────────────────────────────────────────


@pytest.fixture
async def headers(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    return auth_headers(user)


@pytest.mark.asyncio
async def test_upload_rejects_unsigned_pkl(client, headers):
    resp = await client.post(
        "/api/classify/upload",
        files={"file": ("model.pkl", pickle.dumps({"evil": True}), "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "nicht aus dieser Installation" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_rejects_unsigned_pkl_inside_zip(client, headers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("model.pkl", pickle.dumps({"evil": True}))
        zf.writestr("memory.json", "[]")
    resp = await client.post(
        "/api/classify/upload",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_signed_model_roundtrips_through_upload_and_download(client, headers):
    signed = pack({"classes": ["6500"]})
    resp = await client.post(
        "/api/classify/upload",
        files={"file": ("model.pkl", signed, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["restored"] == ["model"]

    resp = await client.get("/api/classify/download/model", headers=headers)
    assert resp.status_code == 200
    assert resp.content == signed

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


# ── B-34: derived key, insecure key refused, fingerprint column ──────────────


def test_signing_key_is_derived_not_the_raw_secret():
    import hashlib
    import hmac as _hmac

    blob = pack({"a": 1})
    payload = blob[len(MAGIC) + 32 :]
    raw_key_digest = _hmac.new(model_blob.settings.SECRET_KEY.encode(), payload, hashlib.sha256).digest()
    assert blob[len(MAGIC) : len(MAGIC) + 32] != raw_key_digest


@pytest.mark.parametrize("secret", ["change-me-in-production", "secret", "", "short-key"])
def test_insecure_secret_refuses_to_sign_and_trusts_nothing(monkeypatch, secret):
    good = pack({"a": 1})
    monkeypatch.setattr(model_blob.settings, "SECRET_KEY", secret)
    with pytest.raises(model_blob.InsecureSecretKey):
        pack({"a": 1})
    assert not is_trusted(good)
    with pytest.raises(UntrustedModelBlob):
        unpack(good)


@pytest.mark.asyncio
async def test_train_reports_insecure_secret_as_503(client, headers, db_session, monkeypatch):
    from app.models.tenant import Tenant
    from app.services import classifier as classifier_module
    from tests.factories import create_training_row

    me = (await client.get("/api/auth/me", headers=headers)).json()
    tenant = await db_session.get(Tenant, me["tenant_id"])
    for i in range(6):
        await create_training_row(db_session, tenant, f"Lieferant {i}", "4000" if i % 2 else "6500")

    # Swapping the secret itself would also invalidate the bearer token (401 first), so
    # simulate what pack() does with an insecure key at the point train_from_db reaches it.
    def refuse(_obj):
        raise model_blob.InsecureSecretKey(model_blob.INSECURE_SECRET_DETAIL)

    monkeypatch.setattr(classifier_module, "pack", refuse)
    resp = await client.post("/api/classify/train", headers=headers)
    assert resp.status_code == 503
    assert "SECRET_KEY" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_altered_blob_is_ignored_and_info_says_retrain(client, headers, db_session):
    from sqlalchemy import select

    from app.models.classifier_model import ClassifierModel
    from app.models.tenant import Tenant
    from app.services.classifier import TenantClassifier, model_row_is_trusted
    from app.services.model_blob import sha256_hex

    me = (await client.get("/api/auth/me", headers=headers)).json()
    tenant = await db_session.get(Tenant, me["tenant_id"])
    blob = pack({"a": 1})
    row = ClassifierModel(tenant_id=tenant.id, model_blob=blob, model_sha256=sha256_hex(blob))
    db_session.add(row)
    await db_session.commit()
    assert model_row_is_trusted(row)
    assert (await client.get("/api/classify/info", headers=headers)).json()["model_trusted"] is True

    # Someone swaps the blob in the DB for another signed one without updating the fingerprint.
    row.model_blob = pack({"b": 2})
    await db_session.commit()
    row = (await db_session.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tenant.id))).scalar_one()
    assert not model_row_is_trusted(row)
    assert await TenantClassifier(tenant.id, db_session)._load_model() is None
    info = (await client.get("/api/classify/info", headers=headers)).json()
    assert info["has_model"] is True and info["model_trusted"] is False

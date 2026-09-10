"""Storage backend — local round-trip, factory wiring, S3 with a fake client (no network, no moto)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services import model_storage, storage
from app.services.storage import (
    LocalStorage,
    S3Storage,
    StorageBackend,
    StorageError,
    build_storage,
    get_storage,
    normalize_key,
    reset_storage,
)


@pytest.fixture(autouse=True)
def _fresh_storage():
    reset_storage()
    yield
    reset_storage()


# ── keys ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("models/1/model.pkl", "models/1/model.pkl"),
        ("./models//1/./model.pkl", "models/1/model.pkl"),
        ("models\\1\\model.pkl", "models/1/model.pkl"),
    ],
)
def test_normalize_key_cleans_separators(raw, expected):
    assert normalize_key(raw) == expected


@pytest.mark.parametrize("raw", ["", "/etc/passwd", "../x", "models/../../x", ".", "a/../.."])
def test_normalize_key_rejects_escapes(raw):
    with pytest.raises(StorageError):
        normalize_key(raw)


# ── local ────────────────────────────────────────────────────────────────────


def test_local_round_trip(tmp_path: Path):
    store = LocalStorage(tmp_path)
    assert isinstance(store, StorageBackend)

    assert not store.exists("receipts/7/a.png")
    uri = store.save("receipts/7/a.png", b"\x89PNG...", "image/png")
    assert uri == str(tmp_path / "receipts" / "7" / "a.png")
    assert (tmp_path / "receipts" / "7" / "a.png").read_bytes() == b"\x89PNG..."
    assert store.exists("receipts/7/a.png")
    assert store.read("receipts/7/a.png") == b"\x89PNG..."

    store.save("receipts/7/a.png", b"v2")
    assert store.read("receipts/7/a.png") == b"v2"

    store.delete("receipts/7/a.png")
    assert not store.exists("receipts/7/a.png")
    store.delete("receipts/7/a.png")  # idempotent


def test_local_read_missing_raises_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        LocalStorage(tmp_path).read("nope.bin")


def test_local_key_cannot_escape_root(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    store = LocalStorage(root)
    for key in ("../outside.txt", "/abs.txt", "a/../../b"):
        with pytest.raises(StorageError):
            store.save(key, b"x")
    assert list(tmp_path.iterdir()) == [root]


# ── factory ──────────────────────────────────────────────────────────────────


def test_factory_default_is_local_under_configured_dir(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", "/srv/blobs")
    store = build_storage()
    assert isinstance(store, LocalStorage)
    assert store.root == Path("/srv/blobs")


def test_factory_defaults_match_previous_on_disk_layout():
    # Fresh Settings without env overrides: local backend under /app/data.
    assert settings.STORAGE_BACKEND == "local"
    assert settings.STORAGE_LOCAL_DIR == "/app/data"
    assert model_storage.model_artifact_key(42) == "models/42/model.pkl"


def test_get_storage_is_cached_until_reset(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    first = get_storage()
    assert get_storage() is first
    reset_storage()
    assert get_storage() is not first


def test_factory_builds_s3_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "S3")
    monkeypatch.setattr(settings, "S3_BUCKET", "bh-blobs")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr(settings, "S3_REGION", "eu-central-1")
    store = build_storage()
    assert isinstance(store, S3Storage)
    assert store.bucket == "bh-blobs"
    assert store._endpoint_url == "http://minio:9000"
    assert store._region == "eu-central-1"


def test_factory_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "gcs")
    with pytest.raises(StorageError):
        build_storage()


def test_factory_s3_requires_bucket(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "")
    with pytest.raises(StorageError):
        build_storage()


# ── S3 with a fake client ────────────────────────────────────────────────────


class FakeClientError(Exception):
    """Shaped like botocore.exceptions.ClientError: carries a .response dict."""

    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.calls: list[tuple[str, dict]] = []

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.calls.append(("put_object", {"Bucket": Bucket, "Key": Key, "ContentType": ContentType}))
        self.objects[(Bucket, Key)] = (Body, ContentType)
        return {"ETag": '"x"'}

    def get_object(self, *, Bucket, Key):
        self.calls.append(("get_object", {"Bucket": Bucket, "Key": Key}))
        if (Bucket, Key) not in self.objects:
            raise FakeClientError("NoSuchKey")
        return {"Body": FakeBody(self.objects[(Bucket, Key)][0])}

    def head_object(self, *, Bucket, Key):
        self.calls.append(("head_object", {"Bucket": Bucket, "Key": Key}))
        if (Bucket, Key) not in self.objects:
            raise FakeClientError("404")
        return {}

    def delete_object(self, *, Bucket, Key):
        self.calls.append(("delete_object", {"Bucket": Bucket, "Key": Key}))
        self.objects.pop((Bucket, Key), None)
        return {}


def test_s3_round_trip_with_fake_client():
    client = FakeS3Client()
    store = S3Storage("bh-blobs", client=client)
    assert isinstance(store, StorageBackend)

    assert not store.exists("receipts/7/a.pdf")
    uri = store.save("receipts/7/a.pdf", b"%PDF-1.4", "application/pdf")
    assert uri == "s3://bh-blobs/receipts/7/a.pdf"
    assert client.objects[("bh-blobs", "receipts/7/a.pdf")] == (b"%PDF-1.4", "application/pdf")
    assert store.exists("receipts/7/a.pdf")
    assert store.read("receipts/7/a.pdf") == b"%PDF-1.4"

    store.delete("receipts/7/a.pdf")
    assert not store.exists("receipts/7/a.pdf")
    with pytest.raises(FileNotFoundError):
        store.read("receipts/7/a.pdf")

    assert [c[0] for c in client.calls] == [
        "head_object",
        "put_object",
        "head_object",
        "get_object",
        "delete_object",
        "head_object",
        "get_object",
    ]


def test_s3_default_content_type_and_key_normalisation():
    client = FakeS3Client()
    store = S3Storage("b", client=client)
    store.save("./models//1/model.pkl", b"pkl")
    assert client.calls[-1][1] == {
        "Bucket": "b",
        "Key": "models/1/model.pkl",
        "ContentType": "application/octet-stream",
    }


def test_s3_non_missing_errors_propagate():
    class BrokenClient(FakeS3Client):
        def get_object(self, *, Bucket, Key):
            raise FakeClientError("AccessDenied")

        def head_object(self, *, Bucket, Key):
            raise FakeClientError("AccessDenied")

    store = S3Storage("b", client=BrokenClient())
    with pytest.raises(FakeClientError):
        store.read("x")
    with pytest.raises(FakeClientError):
        store.exists("x")


def test_s3_does_not_import_boto3_when_client_injected(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name.startswith("boto3") or name.startswith("botocore"):
            raise AssertionError("boto3 must not be imported when a client is injected")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    store = S3Storage("b", client=FakeS3Client())
    store.save("k", b"v")
    assert store.read("k") == b"v"


# ── model_storage goes through the backend ───────────────────────────────────


def test_model_storage_uses_configured_backend(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    assert model_storage.load_model_artifact(42) is None
    uri = model_storage.save_model_artifact(42, b"pickled")
    # Same layout as before the abstraction: <root>/models/<tenant>/model.pkl
    assert uri == str(tmp_path / "models" / "42" / "model.pkl")
    assert model_storage.load_model_artifact(42) == b"pickled"
    assert model_storage.load_model_artifact(43) is None


def test_model_storage_with_s3_backend(monkeypatch):
    client = FakeS3Client()
    monkeypatch.setattr(storage, "_storage", S3Storage("models-bucket", client=client))

    assert model_storage.save_model_artifact(7, b"blob") == "s3://models-bucket/models/7/model.pkl"
    assert model_storage.load_model_artifact(7) == b"blob"
    assert model_storage.load_model_artifact(8) is None

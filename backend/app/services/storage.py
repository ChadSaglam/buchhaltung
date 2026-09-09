"""Pluggable blob storage for uploads and artifacts.

Everything that needs to persist a file (receipt images, PDFs, trained model
blobs) goes through :func:`get_storage` instead of touching the filesystem.
The local backend is the default and preserves today's on-disk layout; S3 (or
any S3-compatible object store such as MinIO / Cloudflare R2) is what makes
multi-replica deployments work, because local disk is not shared between pods.

Keys are POSIX-style relative paths ("models/42/model.pkl"). They are never
allowed to escape the storage root.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONTENT_TYPE = "application/octet-stream"


class StorageError(RuntimeError):
    """Raised for invalid keys or backend failures that are not 'not found'."""


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, content_type: str = DEFAULT_CONTENT_TYPE) -> str:
        """Persist ``data`` under ``key``; returns a URI/path identifying the stored object."""
        ...

    def read(self, key: str) -> bytes:
        """Return the object's bytes. Raises ``FileNotFoundError`` when the key does not exist."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object. Deleting a missing key is a no-op."""
        ...

    def exists(self, key: str) -> bool: ...


def normalize_key(key: str) -> str:
    """Validate a storage key: relative, no '..' segments, no empty segments."""
    if not key or not isinstance(key, str):
        raise StorageError("Storage key must be a non-empty string.")
    path = PurePosixPath(key.replace("\\", "/"))
    if path.is_absolute():
        raise StorageError(f"Storage key must be relative: {key!r}")
    parts = [p for p in path.parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise StorageError(f"Storage key must not contain '..' or be empty: {key!r}")
    return "/".join(parts)


class LocalStorage:
    """Files under ``root`` — exactly what the app did before the abstraction existed."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        target = (self.root / normalize_key(key)).resolve()
        root = self.root.resolve()
        if target != root and root not in target.parents:
            raise StorageError(f"Storage key escapes the storage root: {key!r}")
        return target

    def save(self, key: str, data: bytes, content_type: str = DEFAULT_CONTENT_TYPE) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("[STORAGE] local saved key=%s bytes=%d", key, len(data))
        return str(dest)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def _client_error_code(exc: Exception) -> str:
    """Extract the error code from a botocore ClientError without importing botocore."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return ""


_MISSING_CODES = {"404", "NoSuchKey", "NotFound"}


class S3Storage:
    """Objects in an S3 bucket. boto3 is imported lazily so local deployments never need it.

    ``client`` may be injected (tests, custom sessions); otherwise one is created
    on first use from the constructor arguments.
    """

    def __init__(
        self,
        bucket: str,
        *,
        client: Any | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ) -> None:
        if not bucket:
            raise StorageError("S3 storage requires a bucket name (S3_BUCKET).")
        self.bucket = bucket
        self._client = client
        self._endpoint_url = endpoint_url or None
        self._access_key = access_key or None
        self._secret_key = secret_key or None
        self._region = region or None

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise StorageError("STORAGE_BACKEND=s3 requires boto3 (pip install boto3).") from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._client

    def save(self, key: str, data: bytes, content_type: str = DEFAULT_CONTENT_TYPE) -> str:
        key = normalize_key(key)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type or DEFAULT_CONTENT_TYPE)
        logger.info("[STORAGE] s3 saved bucket=%s key=%s bytes=%d", self.bucket, key, len(data))
        return f"s3://{self.bucket}/{key}"

    def read(self, key: str) -> bytes:
        key = normalize_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if _client_error_code(exc) in _MISSING_CODES:
                raise FileNotFoundError(key) from exc
            raise
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=normalize_key(key))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=normalize_key(key))
        except Exception as exc:
            if _client_error_code(exc) in _MISSING_CODES:
                return False
            raise
        return True


_storage: StorageBackend | None = None


def build_storage(backend: str | None = None) -> StorageBackend:
    """Construct a backend from settings (``backend`` overrides STORAGE_BACKEND)."""
    name = (backend or settings.STORAGE_BACKEND or "local").strip().lower()
    if name == "local":
        return LocalStorage(settings.STORAGE_LOCAL_DIR)
    if name == "s3":
        return S3Storage(
            settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
        )
    raise StorageError(f"Unknown STORAGE_BACKEND={name!r} (expected 'local' or 's3').")


def get_storage() -> StorageBackend:
    """Process-wide storage backend, built lazily from settings."""
    global _storage
    if _storage is None:
        _storage = build_storage()
    return _storage


def reset_storage() -> None:
    """Drop the cached backend (tests / settings reloads)."""
    global _storage
    _storage = None

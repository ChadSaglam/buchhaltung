"""Persisted source documents (receipt images, bank-statement PDFs) — B-09.

Every upload is written through the storage backend *before* extraction, so
a failed or later-improved extraction can be re-run and every booking keeps
an audit copy of the document it came from.

Keys are ``receipts/<tenant_id>/<uuid>.<ext>``. The tenant id inside the key
is what ties a document to its tenant: :func:`key_belongs_to_tenant` is
checked wherever a client hands a key back (booking create, source download),
so a key can never address another tenant's file.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import PurePosixPath

from app.services.storage import DEFAULT_CONTENT_TYPE, get_storage

logger = logging.getLogger(__name__)

RECEIPTS_PREFIX = "receipts"

_EXT_BY_CONTENT_TYPE = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/tiff": "tif",
    "image/heic": "heic",
}
_CONTENT_TYPE_BY_EXT = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "heic": "image/heic",
}
_SAFE_EXT = re.compile(r"^[a-z0-9]{1,8}$")
_KEY_PATTERN = re.compile(rf"^{RECEIPTS_PREFIX}/(?P<tenant_id>\d+)/[0-9a-f]{{32}}\.[a-z0-9]{{1,8}}$")


def _extension(filename: str, content_type: str) -> str:
    ext = PurePosixPath(filename or "").suffix.lstrip(".").lower()
    if _SAFE_EXT.match(ext):
        return ext
    return _EXT_BY_CONTENT_TYPE.get((content_type or "").split(";")[0].strip().lower(), "bin")


def receipt_key(tenant_id: int, filename: str, content_type: str) -> str:
    return f"{RECEIPTS_PREFIX}/{tenant_id}/{uuid.uuid4().hex}.{_extension(filename, content_type)}"


def key_belongs_to_tenant(key: str | None, tenant_id: int) -> bool:
    """True only for a well-formed receipt key of exactly this tenant."""
    if not key:
        return False
    match = _KEY_PATTERN.match(key)
    return match is not None and int(match.group("tenant_id")) == tenant_id


def content_type_for_key(key: str) -> str:
    ext = PurePosixPath(key).suffix.lstrip(".").lower()
    return _CONTENT_TYPE_BY_EXT.get(ext, DEFAULT_CONTENT_TYPE)


def store_receipt(tenant_id: int, *, filename: str, content_type: str, content: bytes) -> str:
    """Persist an uploaded document for ``tenant_id``; returns its storage key."""
    key = receipt_key(tenant_id, filename, content_type)
    get_storage().save(key, content, content_type or content_type_for_key(key))
    logger.info("[RECEIPTS] stored tenant=%s key=%s bytes=%d", tenant_id, key, len(content))
    return key


def read_receipt(key: str, tenant_id: int) -> bytes | None:
    """Bytes of a stored document, or None when the key is not this tenant's or the file is gone."""
    if not key_belongs_to_tenant(key, tenant_id):
        return None
    try:
        return get_storage().read(key)
    except FileNotFoundError:
        return None

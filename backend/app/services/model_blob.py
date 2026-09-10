"""Signed pickle container for the per-tenant classifier model (B-32).

``pickle.loads`` executes whatever the bytes say, and a model blob can enter
the database from ``POST /api/classify/upload`` (backup restore), not only
from ``train_from_db``. So every blob carries an HMAC-SHA256 over the pickle,
keyed with ``settings.SECRET_KEY``; ``unpack`` refuses anything that was not
produced by this installation. Layout::

    b"BHM1" + 32-byte HMAC + pickle

The download endpoint returns the container unchanged, so a backup taken here
restores here. A model file from another installation (different key) or a
pre-B-32 raw pickle is rejected — retraining recreates the model in seconds.
"""

from __future__ import annotations

import hashlib
import hmac
import pickle
from typing import Any

from app.core.config import settings

MAGIC = b"BHM1"
_DIGEST_LEN = hashlib.sha256().digest_size


class UntrustedModelBlob(ValueError):
    """The blob is not signed by this installation and must not be unpickled."""


def _sign(payload: bytes) -> bytes:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).digest()


def is_trusted(blob: bytes | None) -> bool:
    """True if ``blob`` is a container whose signature matches our SECRET_KEY."""
    if not blob or len(blob) <= len(MAGIC) + _DIGEST_LEN or not blob.startswith(MAGIC):
        return False
    digest = blob[len(MAGIC) : len(MAGIC) + _DIGEST_LEN]
    payload = blob[len(MAGIC) + _DIGEST_LEN :]
    return hmac.compare_digest(digest, _sign(payload))


def pack(obj: Any) -> bytes:
    payload = pickle.dumps(obj)
    return MAGIC + _sign(payload) + payload


def unpack(blob: bytes | None) -> Any:
    """Verify the signature, then unpickle. Raises ``UntrustedModelBlob`` otherwise."""
    if not is_trusted(blob):
        raise UntrustedModelBlob("model blob is not signed by this installation")
    assert blob is not None  # narrowed by is_trusted
    # Safe by construction: the payload was produced by pack() on this
    # installation and its HMAC was just verified with our SECRET_KEY.
    return pickle.loads(blob[len(MAGIC) + _DIGEST_LEN :])  # nosec B301

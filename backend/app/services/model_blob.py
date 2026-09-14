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

from app.core.config import INSECURE_SECRETS, settings

MAGIC = b"BHM1"
_DIGEST_LEN = hashlib.sha256().digest_size
# B-34: the signing key is derived, not the raw SECRET_KEY — a leaked model
# signature can never be turned into a JWT-signing oracle, and vice versa.
_KEY_CONTEXT = b"model-blob-v1"
INSECURE_SECRET_DETAIL = (
    "SECRET_KEY ist unsicher (Standardwert oder zu kurz). Setze einen zufälligen Wert in backend/.env, "
    'z. B. python -c "import secrets; print(secrets.token_urlsafe(48))", und starte neu.'
)


class UntrustedModelBlob(ValueError):
    """The blob is not signed by this installation and must not be unpickled."""


class InsecureSecretKey(UntrustedModelBlob):
    """Signing with a default/short SECRET_KEY would let anyone forge a blob — refused everywhere."""


def _key() -> bytes:
    secret = settings.SECRET_KEY
    if secret.strip().lower() in INSECURE_SECRETS or len(secret) < 32:
        raise InsecureSecretKey(INSECURE_SECRET_DETAIL)
    return hmac.new(secret.encode("utf-8"), _KEY_CONTEXT, hashlib.sha256).digest()


def _sign(payload: bytes) -> bytes:
    return hmac.new(_key(), payload, hashlib.sha256).digest()


def is_trusted(blob: bytes | None) -> bool:
    """True if ``blob`` is a container whose signature matches our derived key.

    False (never an exception) for a foreign, tampered or raw blob — and for an
    insecure SECRET_KEY, since nothing can be verified with it.
    """
    if not blob or len(blob) <= len(MAGIC) + _DIGEST_LEN or not blob.startswith(MAGIC):
        return False
    digest = blob[len(MAGIC) : len(MAGIC) + _DIGEST_LEN]
    payload = blob[len(MAGIC) + _DIGEST_LEN :]
    try:
        return hmac.compare_digest(digest, _sign(payload))
    except InsecureSecretKey:
        return False


def sha256_hex(blob: bytes) -> str:
    """Fingerprint stored next to the blob (``classifier_models.model_sha256``, B-34)."""
    return hashlib.sha256(blob).hexdigest()


def pack(obj: Any) -> bytes:
    """Serialise and sign. Raises ``InsecureSecretKey`` rather than signing with a guessable key."""
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

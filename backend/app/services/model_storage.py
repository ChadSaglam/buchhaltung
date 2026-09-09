"""Model artifact persistence — thin wrapper over the storage backend.

Keys are ``models/<tenant_id>/<filename>``. With the default local backend
this is the same on-disk layout as before (``/app/data/models/<tenant_id>/``).
"""

from __future__ import annotations

import logging

from app.services.storage import get_storage

logger = logging.getLogger(__name__)


def model_artifact_key(tenant_id: int, filename: str = "model.pkl") -> str:
    return f"models/{tenant_id}/{filename}"


def save_model_artifact(tenant_id: int, data: bytes, filename: str = "model.pkl") -> str:
    """Persist a model artifact. Returns a URI/path for the stored object."""
    uri = get_storage().save(model_artifact_key(tenant_id, filename), data)
    logger.info("[MODEL_STORAGE] saved tenant=%s uri=%s", tenant_id, uri)
    return uri


def load_model_artifact(tenant_id: int, filename: str = "model.pkl") -> bytes | None:
    """Load a model artifact. Returns None if not found."""
    try:
        return get_storage().read(model_artifact_key(tenant_id, filename))
    except FileNotFoundError:
        return None

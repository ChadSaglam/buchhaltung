from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_STORAGE_BACKEND = os.getenv("MODEL_STORAGE_BACKEND", "local")
_LOCAL_DIR = Path(os.getenv("MODEL_DATA_DIR", "/app/data/models"))


def _get_s3_client():
    import boto3  # type: ignore[import]
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


def save_model_artifact(tenant_id: int, data: bytes, filename: str = "model.pkl") -> str:
    """Persist a model artifact. Returns a URI for the stored object."""
    if _STORAGE_BACKEND == "s3":
        bucket = os.getenv("S3_BUCKET", "buchhaltung-models")
        key = f"tenants/{tenant_id}/{filename}"
        _get_s3_client().put_object(Bucket=bucket, Key=key, Body=data)
        logger.info("[MODEL_STORAGE] s3 saved tenant=%s key=%s", tenant_id, key)
        return f"s3://{bucket}/{key}"

    path = _LOCAL_DIR / str(tenant_id)
    path.mkdir(parents=True, exist_ok=True)
    dest = path / filename
    dest.write_bytes(data)
    logger.info("[MODEL_STORAGE] local saved tenant=%s path=%s", tenant_id, dest)
    return str(dest)


def load_model_artifact(tenant_id: int, filename: str = "model.pkl") -> bytes | None:
    """Load a model artifact. Returns None if not found."""
    if _STORAGE_BACKEND == "s3":
        import botocore.exceptions  # type: ignore[import]
        bucket = os.getenv("S3_BUCKET", "buchhaltung-models")
        key = f"tenants/{tenant_id}/{filename}"
        try:
            resp = _get_s3_client().get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except botocore.exceptions.ClientError:
            return None

    path = _LOCAL_DIR / str(tenant_id) / filename
    return path.read_bytes() if path.exists() else None
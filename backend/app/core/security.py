from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.user import User


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# alias used by auth router
hash_password = get_password_hash


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Platform auth contract (chadev-platform/contracts/auth.md) ──────
# Shared claim set for every ChaDev product so one token can be verified by
# both apps: {sub, tid, role, type, exp, jti}. `tid` replaces the old
# `tenant_id` claim; decode side keeps accepting the legacy name for one
# release (see core/deps.py).
ROLES = ("owner", "admin", "editor", "viewer")


def issue_access_token(user: User, expires_delta: timedelta | None = None) -> str:
    """Access token in the platform claim shape."""
    return create_access_token(
        {
            "sub": str(user.id),
            "tid": user.tenant_id,
            "role": user.role,
            "type": "access",
            "jti": uuid4().hex,
        },
        expires_delta,
    )

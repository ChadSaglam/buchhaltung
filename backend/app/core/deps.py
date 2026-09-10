from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.tenant import Tenant
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # Platform contract: only access tokens may call the API. Tokens minted
    # before the contract carry no `type`; treat them as access tokens.
    if payload.get("type", "access") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # `tid` is the contract claim; `tenant_id` is the pre-contract name and is
    # accepted for one release so already-issued tokens keep working.
    claimed_tenant = payload.get("tid", payload.get("tenant_id"))
    if claimed_tenant is not None and int(claimed_tenant) != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # Tenant-level gate (platform contract, mirrors billing): a deactivated
    # tenant locks every user under it.
    active = await db.scalar(select(Tenant.is_active).where(Tenant.id == user.tenant_id))
    if not active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant deaktiviert")
    request.state.tenant_id = user.tenant_id
    return user


# ── Role-based access control (platform contract) ───────────────────
# viewer  read only
# editor  read + write business data
# admin   everything, including user management
# owner   admin + billing/plan/tenant deletion
ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}


def require_role(minimum: str):
    """Dependency factory: reject users below `minimum`.

    Mirrors billing's `require_role` so both products enforce the same ladder.
    Read endpoints stay open to every authenticated role.
    """
    required = ROLE_RANK[minimum]

    def _check(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, -1) < required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum} role or higher",
            )
        return user

    return _check


require_editor = require_role("editor")
require_admin = require_role("admin")
require_owner = require_role("owner")

"""Auth endpoints — register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import ApiError
from app.core.security import hash_password, issue_access_token, verify_password
from app.models.tenant import Tenant
from app.models.user import AUTH_SOURCE_LOCAL, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.tenant_setup import seed_tenant, unique_tenant_slug

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Platform contract (tenant.md): slug derived from the name; buchhaltung
    # keeps its free plan on sign-up (billing starts on "trial").
    # Two sign-ups with the same company name in the same instant both see the
    # base slug as free; the UNIQUE index decides, so retry the loser with a
    # fresh suffix inside a savepoint instead of surfacing a 500.
    for _attempt in range(3):
        tenant = Tenant(
            name=body.tenant_name,
            slug=await unique_tenant_slug(db, body.tenant_name),
            subscription_plan="free",
            is_active=True,
        )
        try:
            async with db.begin_nested():
                db.add(tenant)
                await db.flush()
            break
        except IntegrityError:
            continue
    else:
        raise HTTPException(status_code=409, detail="Tenant name is taken, please retry")

    user = User(
        tenant_id=tenant.id,
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
    )
    db.add(user)
    await db.flush()

    await seed_tenant(db, tenant.id)

    await db.commit()

    token = issue_access_token(user)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Shadow users provisioned by platform SSO have no usable password
    # (contracts/sso.md): say so before touching the hash at all.
    if user is not None and user.auth_source != AUTH_SOURCE_LOCAL:
        raise ApiError(403, "platform_user", "Dieses Konto meldet sich über die Plattform (Billing) an")
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = issue_access_token(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        subscription_plan=tenant.subscription_plan,
        trial_ends_at=tenant.trial_ends_at,
    )

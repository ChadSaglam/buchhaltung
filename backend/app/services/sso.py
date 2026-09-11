"""SSO hand-off, verifier side (B-36, chadev-platform/contracts/sso.md).

billing is the platform identity issuer (ADR-001). It mints a short-lived,
single-use HS256 token signed with `PLATFORM_SHARED_SECRET`; this module
verifies it and mirrors the caller into local rows:

* tenant by `tenants.platform_tenant_id == tid` — created from the `tenant`
  snapshot on first use (slug via `unique_tenant_slug`, Kontenplan via
  `seed_tenant`), `name` / `subscription_plan` / `trial_ends_at` refreshed on
  every later hop;
* shadow user by (`tenant_id`, `users.platform_user_id == sub`) — created
  with `auth_source='platform'` and an unusable password sentinel,
  `email` / `display_name` / `role` refreshed on every hop.

Email is globally unique in `users`. When the claim's email already belongs
to a *local* user of the same tenant that account is linked (gets the
`platform_user_id`, stays `auth_source='local'`, keeps its own role and
password); when it belongs to a user of a different tenant the hop is
refused with 409 `email_taken_locally` — silently attaching an SSO identity
to somebody else's account would be an account takeover.

Role mapping (contracts/auth.md): the ladder is identical in both products
(`owner › admin › editor › viewer`), so roles pass through unchanged and an
unknown role degrades to `viewer`. billing issues `admin` at most; buchhaltung
does not promote it to `owner`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ROLES
from app.models.sso_nonce import SsoNonce
from app.models.tenant import Tenant
from app.models.user import AUTH_SOURCE_PLATFORM, PLATFORM_PASSWORD_SENTINEL, User
from app.services.tenant_setup import seed_tenant, unique_tenant_slug

SSO_ISSUER = "billing"
SSO_AUDIENCE = "buchhaltung"
SSO_TYPE = "sso"
SSO_ALGORITHM = "HS256"
# Contract: `exp` at most 120 s after `iat`.
SSO_MAX_TTL_SECONDS = 120
JTI_MAX_LEN = 64
# Kept slightly beyond the token's own lifetime so a clock-skewed worker
# cannot purge a nonce that another worker still considers valid.
NONCE_GRACE = timedelta(minutes=5)


@dataclass(frozen=True)
class SsoError(Exception):
    """Verification failure with the envelope code the router answers with."""

    status_code: int
    code: str
    message: str


@dataclass(frozen=True)
class SsoClaims:
    sub: str
    email: str
    name: str
    tid: int
    role: str
    tenant: dict
    jti: str
    exp: datetime


def platform_role(role: object) -> str:
    """Claim role → local role: pass-through on the shared ladder, else least privilege."""
    return role if isinstance(role, str) and role in ROLES else "viewer"


def _invalid(message: str = "Ungültiges SSO-Token") -> SsoError:
    return SsoError(401, "sso_invalid", message)


def decode_sso_token(token: str, secret: str) -> SsoClaims:
    """Verify signature + every claim rule of contracts/sso.md; raise `SsoError` otherwise."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[SSO_ALGORITHM],
            audience=SSO_AUDIENCE,
            issuer=SSO_ISSUER,
            options={"require_exp": True, "require_iat": True, "require_sub": True},
        )
    except ExpiredSignatureError as exc:
        raise SsoError(401, "sso_expired", "Das SSO-Token ist abgelaufen") from exc
    except JWTError as exc:
        raise _invalid() from exc

    if payload.get("type") != SSO_TYPE:
        raise _invalid()
    iat, exp = payload.get("iat"), payload.get("exp")
    if not isinstance(iat, int | float) or not isinstance(exp, int | float) or exp - iat > SSO_MAX_TTL_SECONDS:
        raise _invalid()
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti or len(jti) > JTI_MAX_LEN:
        raise _invalid()
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > 64:
        raise _invalid()
    tid = payload.get("tid")
    if not isinstance(tid, int) or isinstance(tid, bool):
        raise _invalid()
    email = payload.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise _invalid()
    tenant = payload.get("tenant")
    if not isinstance(tenant, dict):
        raise _invalid()
    name = payload.get("name")
    return SsoClaims(
        sub=sub,
        email=email,
        name=name if isinstance(name, str) else "",
        tid=tid,
        role=platform_role(payload.get("role")),
        tenant=tenant,
        jti=jti,
        exp=datetime.fromtimestamp(exp, tz=UTC),
    )


async def consume_nonce(db: AsyncSession, claims: SsoClaims) -> None:
    """Remember `jti`; a second use raises `sso_replayed`. Purges expired rows on the way."""
    now = datetime.now(UTC)
    await db.execute(delete(SsoNonce).where(SsoNonce.expires_at < now - NONCE_GRACE))
    try:
        async with db.begin_nested():
            db.add(SsoNonce(jti=claims.jti, expires_at=claims.exp))
            await db.flush()
    except IntegrityError as exc:
        raise SsoError(401, "sso_replayed", "Das SSO-Token wurde bereits verwendet") from exc


def _parse_trial_ends_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _apply_tenant_snapshot(tenant: Tenant, snapshot: dict) -> None:
    name = snapshot.get("name")
    if isinstance(name, str) and name.strip():
        tenant.name = name.strip()[:255]
    plan = snapshot.get("subscription_plan")
    if isinstance(plan, str) and plan:
        tenant.subscription_plan = plan[:50]
    tenant.trial_ends_at = _parse_trial_ends_at(snapshot.get("trial_ends_at"))


async def _tenant_by_platform_id(db: AsyncSession, tid: int) -> Tenant | None:
    return await db.scalar(select(Tenant).where(Tenant.platform_tenant_id == tid))


async def mirror_tenant(db: AsyncSession, claims: SsoClaims) -> Tenant:
    """Tenant for `tid`: created from the snapshot on first use, refreshed afterwards."""
    tenant = await _tenant_by_platform_id(db, claims.tid)
    if tenant is not None:
        _apply_tenant_snapshot(tenant, claims.tenant)
        return tenant

    snapshot = claims.tenant
    name = snapshot.get("name") if isinstance(snapshot.get("name"), str) else ""
    name = name.strip() or f"Tenant {claims.tid}"
    slug_source = snapshot.get("slug") if isinstance(snapshot.get("slug"), str) and snapshot.get("slug") else name
    # Two first hops for the same tid in the same instant both see "no tenant";
    # the UNIQUE on platform_tenant_id decides and the loser re-reads the winner.
    tenant = Tenant(
        name=name[:255],
        slug=await unique_tenant_slug(db, slug_source),
        subscription_plan="free",
        is_active=True,
        platform_tenant_id=claims.tid,
    )
    _apply_tenant_snapshot(tenant, snapshot)
    try:
        async with db.begin_nested():
            db.add(tenant)
            await db.flush()
            await seed_tenant(db, tenant.id)
            await db.flush()
    except IntegrityError:
        db.expunge(tenant)
        existing = await _tenant_by_platform_id(db, claims.tid)
        if existing is None:
            raise
        _apply_tenant_snapshot(existing, snapshot)
        return existing
    return tenant


async def mirror_user(db: AsyncSession, tenant: Tenant, claims: SsoClaims) -> User:
    """Shadow user for (`tenant`, `sub`): created on first use, refreshed afterwards."""
    user = await db.scalar(
        select(User).where(User.tenant_id == tenant.id, User.platform_user_id == claims.sub).limit(1)
    )
    by_email = await db.scalar(select(User).where(User.email == claims.email).limit(1))

    if user is not None:
        if user.auth_source != AUTH_SOURCE_PLATFORM:
            # A linked local account keeps its own profile, role and password.
            return user
        if by_email is not None and by_email.id != user.id:
            raise SsoError(409, "email_taken_locally", "Diese E-Mail-Adresse gehört bereits einem anderen Konto")
        user.email = claims.email
        user.display_name = claims.name or user.display_name
        user.role = claims.role
        return user

    if by_email is not None:
        if by_email.tenant_id != tenant.id or by_email.platform_user_id:
            raise SsoError(409, "email_taken_locally", "Diese E-Mail-Adresse gehört bereits einem anderen Konto")
        by_email.platform_user_id = claims.sub
        return by_email

    user = User(
        tenant_id=tenant.id,
        email=claims.email,
        password_hash=PLATFORM_PASSWORD_SENTINEL,
        display_name=claims.name or claims.email.split("@")[0],
        role=claims.role,
        platform_user_id=claims.sub,
        auth_source=AUTH_SOURCE_PLATFORM,
    )
    db.add(user)
    await db.flush()
    return user

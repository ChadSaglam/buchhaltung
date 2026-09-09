from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.correction import Correction
from app.models.kontenplan import Konto, KontoDefault
from app.models.memory import Memory
from app.models.review_queue import ReviewQueueItem
from app.models.scanner_config import ScannerConfig
from app.models.tenant import Tenant
from app.models.training_data import TrainingRow
from app.models.user import User
from app.services.classifier import make_memory_key


async def create_tenant(db: AsyncSession, name: str | None = None) -> Tenant:
    tenant = Tenant(name=name or f"tenant-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def create_user(
    db: AsyncSession,
    tenant: Tenant,
    email: str | None = None,
    password: str = "Test1234!",
) -> User:
    user = User(
        email=email or f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash(password),
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    """Bearer header for API tests — same claims the auth router mints."""
    token = create_access_token({"sub": str(user.id), "tenant_id": user.tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _persist(db: AsyncSession, obj):
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def create_booking(
    db: AsyncSession,
    tenant: Tenant,
    *,
    datum: str = "15.03.2025",
    beschreibung: str = "Testbuchung",
    betrag: float = 100.0,
    kt_soll: str = "6500",
    kt_haben: str = "1020",
    mwst_code: str = "",
    mwst_pct: str = "",
    mwst_amount: float = 0.0,
    beleg: str = "",
    rechnung: str = "",
    source: str = "test",
) -> Booking:
    return await _persist(
        db,
        Booking(
            tenant_id=tenant.id,
            datum=datum,
            beschreibung=beschreibung,
            betrag=betrag,
            kt_soll=kt_soll,
            kt_haben=kt_haben,
            mwst_code=mwst_code,
            mwst_pct=mwst_pct,
            mwst_amount=mwst_amount,
            beleg=beleg,
            rechnung=rechnung,
            source=source,
        ),
    )


async def create_konto(
    db: AsyncSession,
    tenant: Tenant,
    konto_nr: str = "6500",
    beschreibung: str = "Büromaterial",
) -> Konto:
    return await _persist(db, Konto(tenant_id=tenant.id, konto_nr=konto_nr, beschreibung=beschreibung))


async def create_konto_default(
    db: AsyncSession,
    tenant: Tenant,
    konto_soll: str = "6500",
    konto_haben: str = "1020",
    mwst_code: str = "",
    mwst_pct: str = "",
) -> KontoDefault:
    return await _persist(
        db,
        KontoDefault(
            tenant_id=tenant.id,
            konto_soll=konto_soll,
            konto_haben=konto_haben,
            mwst_code=mwst_code,
            mwst_pct=mwst_pct,
        ),
    )


async def create_review_item(
    db: AsyncSession,
    tenant: Tenant,
    *,
    beschreibung: str = "Unklare Buchung",
    betrag: float = 42.0,
    predicted_soll: str = "6500",
    predicted_haben: str = "1020",
    predicted_mwst_code: str = "",
    predicted_mwst_pct: str = "",
    confidence: float = 0.35,
    source: str = "Regeln",
    status: str = "pending",
) -> ReviewQueueItem:
    return await _persist(
        db,
        ReviewQueueItem(
            tenant_id=tenant.id,
            beschreibung=beschreibung,
            betrag=betrag,
            predicted_soll=predicted_soll,
            predicted_haben=predicted_haben,
            predicted_mwst_code=predicted_mwst_code,
            predicted_mwst_pct=predicted_mwst_pct,
            confidence=confidence,
            source=source,
            status=status,
        ),
    )


async def create_scanner_config(
    db: AsyncSession,
    tenant: Tenant,
    **overrides,
) -> ScannerConfig:
    return await _persist(db, ScannerConfig(tenant_id=tenant.id, **overrides))


async def create_memory(
    db: AsyncSession,
    tenant: Tenant,
    beschreibung: str,
    kt_soll: str = "6500",
    kt_haben: str = "1020",
    mwst_code: str = "",
    mwst_pct: str = "",
) -> Memory:
    """Seed a memory row keyed the way the classifier looks it up."""
    return await _persist(
        db,
        Memory(
            tenant_id=tenant.id,
            lookup_key=make_memory_key(beschreibung),
            kt_soll=kt_soll,
            kt_haben=kt_haben,
            mwst_code=mwst_code,
            mwst_pct=mwst_pct,
        ),
    )


async def create_correction(
    db: AsyncSession,
    tenant: Tenant,
    *,
    beschreibung: str = "Korrigierte Buchung",
    original_soll: str = "6500",
    original_haben: str = "1020",
    corrected_soll: str = "6570",
    corrected_haben: str = "1020",
    corrected_mwst_code: str = "",
    corrected_mwst_pct: str = "",
) -> Correction:
    return await _persist(
        db,
        Correction(
            tenant_id=tenant.id,
            beschreibung=beschreibung,
            original_soll=original_soll,
            original_haben=original_haben,
            corrected_soll=corrected_soll,
            corrected_haben=corrected_haben,
            corrected_mwst_code=corrected_mwst_code,
            corrected_mwst_pct=corrected_mwst_pct,
        ),
    )


async def create_training_row(
    db: AsyncSession,
    tenant: Tenant,
    beschreibung: str,
    kt_soll: str,
    kt_haben: str = "1020",
    mwst_code: str = "",
    mwst_pct: str = "",
) -> TrainingRow:
    return await _persist(
        db,
        TrainingRow(
            tenant_id=tenant.id,
            beschreibung=beschreibung,
            kt_soll=kt_soll,
            kt_haben=kt_haben,
            mwst_code=mwst_code,
            mwst_pct=mwst_pct,
        ),
    )


async def create_audit_entry(
    db: AsyncSession,
    tenant: Tenant,
    *,
    action: str = "test.action",
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
) -> AuditLog:
    return await _persist(
        db,
        AuditLog(
            tenant_id=tenant.id,
            action=action,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        ),
    )

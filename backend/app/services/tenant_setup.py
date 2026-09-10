"""Tenant onboarding — slug derivation, seed default Kontenplan and konto_defaults."""

import re
import unicodedata
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kontenplan import Konto, KontoDefault
from app.models.tenant import Tenant

SLUG_MAX_LEN = 100
_SLUG_SUFFIX_LEN = 6


def slugify(name: str) -> str:
    """ASCII slug for a tenant name: `"Müller & Söhne AG"` → `"muller-sohne-ag"`.

    Empty input (or a name with no ASCII letters/digits) yields `"tenant"` so
    the caller always gets a valid slug.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:SLUG_MAX_LEN].strip("-") or "tenant"


async def unique_tenant_slug(db: AsyncSession, name: str) -> str:
    """Slug derived from `name`; on collision a short random suffix is appended."""
    base = slugify(name)
    slug = base
    while True:
        taken = await db.scalar(select(Tenant.id).where(Tenant.slug == slug).limit(1))
        if taken is None:
            return slug
        suffix = uuid4().hex[:_SLUG_SUFFIX_LEN]
        slug = f"{base[: SLUG_MAX_LEN - _SLUG_SUFFIX_LEN - 1]}-{suffix}"


FALLBACK_KONTENPLAN: dict[str, str] = {
    "1000": "Kasse",
    "1020": "Bankguthaben",
    "1100": "Forderungen aus Leistungen (Debitoren)",
    "2000": "Kreditoren (Verbindlichkeiten aus L+L)",
    "2200": "Geschuldete MWST (Umsatzsteuer)",
    "3000": "Bruttoertrag Arbeit",
    "4000": "Materialaufwand Produktion",
    "5000": "Lohnaufwand",
    "5700": "AHV, IV, EO",
    "6000": "Raumaufwand",
    "6200": "Fahrzeugaufwand",
    "6210": "Betriebsstoffe",
    "6500": "Verwaltungsaufwand",
    "6570": "EDV Updates, Lizenzen, Wartung",
    "6900": "Finanzaufwand",
    "8900": "Direkte Steuern",
}

DEFAULT_KONTO_DEFAULTS: dict[str, dict] = {
    "1020": {"konto_haben": "3000", "mwst_code": "V81", "mwst_pct": "-8.10"},
    "4000": {"konto_haben": "1020", "mwst_code": "M81", "mwst_pct": "8.10"},
    "5000": {"konto_haben": "1020", "mwst_code": "", "mwst_pct": ""},
    "5700": {"konto_haben": "1020", "mwst_code": "", "mwst_pct": ""},
    "6000": {"konto_haben": "1020", "mwst_code": "", "mwst_pct": ""},
    "6200": {"konto_haben": "1020", "mwst_code": "I81", "mwst_pct": "8.10"},
    "6210": {"konto_haben": "1020", "mwst_code": "I81", "mwst_pct": "8.10"},
    "6500": {"konto_haben": "1020", "mwst_code": "I81", "mwst_pct": "8.10"},
    "6570": {"konto_haben": "1020", "mwst_code": "I81", "mwst_pct": "8.10"},
    "6600": {"konto_haben": "1020", "mwst_code": "I81", "mwst_pct": "8.10"},
    "6900": {"konto_haben": "1020", "mwst_code": "", "mwst_pct": ""},
    "8900": {"konto_haben": "1020", "mwst_code": "", "mwst_pct": ""},
}


async def seed_tenant(db: AsyncSession, tenant_id: int):
    for konto_nr, beschreibung in FALLBACK_KONTENPLAN.items():
        db.add(Konto(tenant_id=tenant_id, konto_nr=konto_nr, beschreibung=beschreibung))
    for konto_soll, defaults in DEFAULT_KONTO_DEFAULTS.items():
        db.add(
            KontoDefault(
                tenant_id=tenant_id,
                konto_soll=konto_soll,
                konto_haben=defaults["konto_haben"],
                mwst_code=defaults["mwst_code"],
                mwst_pct=defaults["mwst_pct"],
            )
        )

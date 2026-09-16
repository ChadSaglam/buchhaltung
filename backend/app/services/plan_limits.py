"""Plan-Grenzen durchsetzen (B-23).

B-54 hat angefangen zu *zählen*; hier wird gezählt **und** abgelehnt. Alles
kommt aus derselben Tabelle (``usage_events``), damit die Zahl, die dem Kunden
angezeigt wird, dieselbe ist, die ihn aussperrt — zwei Quellen für dieselbe
Zahl driften auseinander, und zwar immer an dem Tag, an dem sich jemand
beschwert.

Zwei Entscheidungen, die man beim Lesen sofort sehen soll:

* **Geprüft wird vor dem Schreiben**, nicht danach. Ein Beleg, der gespeichert
  und dann abgelehnt wird, liegt trotzdem auf der Platte.
* **Sitzplätze werden nicht begrenzt.** Es gibt heute genau zwei Wege, wie ein
  Benutzer entsteht: die Selbstregistrierung (die immer einen *neuen* Mandanten
  anlegt, also nie einen bestehenden vergrössert) und die Spiegelung aus der
  Abrechnung über SSO — und was von dort kommt, hat die Abrechnung bereits
  entschieden. Eine Sitzplatzgrenze hier wäre eine Regel ohne Regelverstoss.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.core.plans import (
    BESTAND,
    EVENT_TYPE,
    LIMIT_KEYS,
    LIMIT_LABEL,
    MONATLICH,
    WARNSCHWELLE,
    ZEITZONE,
    limits_for,
)
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent

logger = logging.getLogger(__name__)

MB = 1024 * 1024
LIMIT_CODE = "plan_limit_erreicht"


def monatsbeginn(now: datetime | None = None) -> datetime:
    """Der erste Moment des laufenden Schweizer Kalendermonats, als UTC-Zeitpunkt."""
    tz = ZoneInfo(ZEITZONE)
    lokal = (now or datetime.now(tz)).astimezone(tz)
    return lokal.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _grenze_fuer(db: AsyncSession, moment: datetime) -> datetime:
    """Derselbe Zeitpunkt, in der Form, die dieser Dialekt vergleichen kann.

    Postgres speichert ``timestamptz`` und vergleicht Zeitpunkte. SQLite hat
    keinen Zeitzonentyp: ``server_default=func.now()`` schreibt dort *naives
    UTC*, und ein Vergleich mit einem zonenbehafteten Wert wäre ein
    Textvergleich mit angehängtem Offset — der am Monatsersten um 00:30 Uhr
    Zürcher Zeit das falsche Ergebnis liefert, also genau dann, wenn es
    jemandem auffällt.
    """
    return moment if db.get_bind().dialect.name == "postgresql" else moment.replace(tzinfo=None)


class PlanLimits:
    def __init__(self, tenant_id: int, db: AsyncSession) -> None:
        self.tenant_id = tenant_id
        self.db = db
        self._plan: str | None = None

    async def plan(self) -> str:
        if self._plan is None:
            row = await self.db.execute(select(Tenant.subscription_plan).where(Tenant.id == self.tenant_id))
            self._plan = (row.scalar_one_or_none() or "").strip().lower()
        return self._plan

    async def limits(self) -> dict[str, int | None]:
        return limits_for(await self.plan())

    async def verbrauch(self) -> dict[str, int]:
        """Ein Statement für alle Zähler.

        Die monatlichen und die Bestandsgrössen haben verschiedene Fenster, also
        bekommt jede Summe ihre eigene ``CASE``-Bedingung statt einer eigenen
        Abfrage (B-27: eine Grenze darf keine fünf Round-Trips kosten).
        """
        seit = _grenze_fuer(self.db, monatsbeginn())
        spalten = []
        for key in LIMIT_KEYS:
            bedingung = UsageEvent.event_type == EVENT_TYPE[key]
            if key in MONATLICH:
                bedingung = bedingung & (UsageEvent.created_at >= seit)
            # `CASE`, nicht `FILTER`: SQLite kennt `FILTER` erst ab 3.30 und die
            # Testmatrix läuft auf beidem.
            spalten.append(func.coalesce(func.sum(case((bedingung, UsageEvent.quantity), else_=0)), 0))

        row = (await self.db.execute(select(*spalten).where(UsageEvent.tenant_id == self.tenant_id))).one()

        roh = dict(zip(LIMIT_KEYS, (int(v or 0) for v in row), strict=True))
        # `storage_bytes` zählt Bytes, die Grenze steht in MB. Aufgerundet, damit
        # 1 Byte über der Grenze auch als "über der Grenze" gelesen wird.
        roh["speicher_mb"] = -(-roh["speicher_mb"] // MB)
        return roh

    async def snapshot(self) -> dict[str, object]:
        """Was die Oberfläche zeigt: Plan, Verbrauch, Grenze, Warnung — pro Zähler."""
        limits = await self.limits()
        verbrauch = await self.verbrauch()
        zaehler = []
        for key in LIMIT_KEYS:
            limit = limits[key]
            benutzt = verbrauch[key]
            anteil = None if limit in (None, 0) else min(1.0, benutzt / limit)
            zaehler.append(
                {
                    "key": key,
                    "label": LIMIT_LABEL[key],
                    "benutzt": benutzt,
                    "limit": limit,
                    "anteil": anteil,
                    "warnung": anteil is not None and anteil >= WARNSCHWELLE,
                    "erreicht": limit is not None and benutzt >= limit,
                    "periode": "monat" if key in MONATLICH else "bestand",
                }
            )
        return {
            "plan": await self.plan() or "free",
            "durchgesetzt": settings.ENFORCE_PLAN_LIMITS,
            "monat_seit": monatsbeginn().isoformat(),
            "zaehler": zaehler,
        }

    async def ensure(self, key: str, menge: int = 1) -> None:
        """Ablehnen, *bevor* geschrieben wird. Kein Limit → kein Statement."""
        assert key in LIMIT_KEYS, f"unbekannte Grenze: {key}"
        limit = (await self.limits())[key]
        if limit is None:
            return
        benutzt = (await self.verbrauch())[key]
        if benutzt + menge <= limit:
            return

        einheit = "MB" if key in BESTAND else ""
        meldung = (
            f"{LIMIT_LABEL[key]}: {benutzt}{einheit} von {limit}{einheit} verbraucht. "
            f"Mit dem Abo «{await self.plan() or 'free'}» ist hier Schluss."
        )
        if not settings.ENFORCE_PLAN_LIMITS:
            # Der Schalter existiert für den Tag, an dem eine Zahl falsch gesetzt
            # wurde und niemand aussperrt werden soll, bis sie korrigiert ist.
            logger.warning("[PLAN] tenant=%s würde abgelehnt: %s", self.tenant_id, meldung)
            return
        logger.info("[PLAN] tenant=%s abgelehnt: %s", self.tenant_id, meldung)
        raise ApiError(402, LIMIT_CODE, meldung)

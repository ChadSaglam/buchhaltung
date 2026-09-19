"""Wie viel Platz ein Mandant belegen darf (B-54).

Jede hochgeladene Datei wird aufbewahrt — das ist Absicht (B-09: der Beleg
überlebt auch, wenn das Parsen scheitert). Ohne Obergrenze heisst das aber,
dass ein einziger Mandant die Platte des Servers füllen kann, und zwar mit
Dateien, die das Produkt nie lesen konnte.

Gezählt wird über ``usage_events``: ein Ereignis pro gespeicherter Datei, die
Bytezahl als ``quantity``. Das ist genau, solange nichts gelöscht wird — und
heute löscht dieses Produkt keine Belege. **Wenn ein Löschpfad dazukommt, muss
er ein negatives Ereignis schreiben**, sonst wandert das Konto nur nach oben.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.usage_event import UsageEvent
from app.services.plan_limits import MB, PlanLimits

logger = logging.getLogger(__name__)

STORAGE_EVENT = "storage_bytes"


class StorageQuota:
    def __init__(self, tenant_id: int, db: AsyncSession) -> None:
        self.tenant_id = tenant_id
        self.db = db

    async def limit_bytes(self) -> int:
        """Die engere der beiden Grenzen, in Bytes. 0 = keine.

        Zwei Grenzen, zwei Gründe: ``MAX_TENANT_STORAGE_MB`` schützt die Platte
        dieser Installation (B-54), der Plan verkauft Platz (B-23). Wer beides
        setzt, meint beides — also gilt die kleinere.
        """
        install = max(0, settings.MAX_TENANT_STORAGE_MB)
        if install == 0:
            # Der dokumentierte Notausgang aus B-54: keine Quote, Punkt. Hier
            # über die Plan-Tabelle wieder eine einzuführen, würde genau die
            # Installation treffen, die sie bewusst abgeschaltet hat.
            return 0
        plan = None
        if settings.ENFORCE_PLAN_LIMITS:
            plan = (await PlanLimits(self.tenant_id, self.db).limits())["speicher_mb"]
        return min(install, plan) * MB if plan else install * MB

    async def used_bytes(self) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.tenant_id == self.tenant_id,
                UsageEvent.event_type == STORAGE_EVENT,
            )
        )
        return int(result.scalar() or 0)

    async def ensure_room_for(self, nbytes: int) -> None:
        """Refuse *before* the bytes are written, not after the disk is full."""
        limit = await self.limit_bytes()
        if limit <= 0:  # 0 = no quota, for a single-tenant install
            return
        used = await self.used_bytes()
        if used + nbytes > limit:
            logger.info("[QUOTA] tenant=%s refused %d bytes (used %d of %d)", self.tenant_id, nbytes, used, limit)
            raise HTTPException(
                413,
                f"Speicherplatz aufgebraucht: {used // MB} von {limit // MB} MB belegt. "
                "Bitte wenden Sie sich an den Support.",
            )

    async def record(self, nbytes: int) -> None:
        """Book what was just stored. Negative when something is removed again."""
        self.db.add(UsageEvent(tenant_id=self.tenant_id, event_type=STORAGE_EVENT, quantity=int(nbytes)))
        await self.db.flush()

    async def ensure_and_record(self, nbytes: int) -> None:
        await self.ensure_room_for(nbytes)
        await self.record(nbytes)

"""Confidence-threshold review queue service — tenant-scoped."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_queue import ReviewQueueItem
from app.models.scanner_config import ScannerConfig
from app.services.classifier import ClassificationResult, TenantClassifier

DEFAULT_THRESHOLD = 0.80


class ReviewQueueService:
    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db

    async def get_threshold(self) -> float:
        result = await self.db.execute(
            select(ScannerConfig.review_confidence_threshold).where(ScannerConfig.tenant_id == self.tenant_id)
        )
        value = result.scalar_one_or_none()
        return float(value) if value is not None else DEFAULT_THRESHOLD

    async def enqueue_if_low_confidence(
        self, beschreibung: str, betrag: float, result: ClassificationResult
    ) -> ReviewQueueItem | None:
        threshold = await self.get_threshold()
        if result.confidence >= threshold:
            return None
        item = ReviewQueueItem(
            tenant_id=self.tenant_id,
            beschreibung=beschreibung,
            betrag=betrag,
            predicted_soll=result.kt_soll,
            predicted_haben=result.kt_haben,
            predicted_mwst_code=result.mwst_code,
            predicted_mwst_pct=result.mwst_pct,
            confidence=result.confidence,
            source=result.source,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_pending(self) -> list[ReviewQueueItem]:
        result = await self.db.execute(
            select(ReviewQueueItem)
            .where(
                ReviewQueueItem.tenant_id == self.tenant_id,
                ReviewQueueItem.status == "pending",
            )
            .order_by(ReviewQueueItem.confidence.asc(), ReviewQueueItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def pending_count(self) -> int:
        result = await self.db.execute(
            select(func.count(ReviewQueueItem.id)).where(
                ReviewQueueItem.tenant_id == self.tenant_id,
                ReviewQueueItem.status == "pending",
            )
        )
        return result.scalar() or 0

    async def _get_item(self, item_id: int) -> ReviewQueueItem | None:
        result = await self.db.execute(
            select(ReviewQueueItem)
            .where(
                ReviewQueueItem.id == item_id,
                ReviewQueueItem.tenant_id == self.tenant_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _claim(self, item_id: int, status: str) -> bool:
        """Take the item out of *pending* in one statement (B-52).

        Reading the status and then writing it leaves a gap; two clicks on the
        same row used to log the correction twice and train the model twice.
        The ``WHERE status = 'pending'`` makes the database pick a winner, and
        ``rowcount`` says whether we are it.
        """
        result = await self.db.execute(
            update(ReviewQueueItem)
            .where(
                ReviewQueueItem.id == item_id,
                ReviewQueueItem.tenant_id == self.tenant_id,
                ReviewQueueItem.status == "pending",
            )
            .values(status=status, resolved_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        return (result.rowcount or 0) == 1

    async def approve(
        self,
        item_id: int,
        corrected_soll: str | None = None,
        corrected_haben: str | None = None,
        corrected_mwst_code: str | None = None,
        corrected_mwst_pct: str | None = None,
    ) -> ReviewQueueItem | None:
        if not await self._claim(item_id, "approved"):
            return None
        item = await self._get_item(item_id)
        if item is None:  # pragma: no cover - claimed rows exist by definition
            return None

        final_soll = corrected_soll or item.predicted_soll
        final_haben = corrected_haben or item.predicted_haben
        final_mwst_code = corrected_mwst_code if corrected_mwst_code is not None else item.predicted_mwst_code
        final_mwst_pct = corrected_mwst_pct if corrected_mwst_pct is not None else item.predicted_mwst_pct

        clf = TenantClassifier(self.tenant_id, self.db)
        original = ClassificationResult(
            kt_soll=item.predicted_soll,
            kt_haben=item.predicted_haben,
            mwst_code=item.predicted_mwst_code,
            mwst_pct=item.predicted_mwst_pct,
            mwst_amount="",
        )
        await clf.log_correction(
            beschreibung=item.beschreibung,
            original=original,
            corrected_soll=final_soll,
            corrected_haben=final_haben,
            corrected_mwst_code=final_mwst_code,
            corrected_mwst_pct=final_mwst_pct,
        )

        item.resolved_soll = final_soll
        item.resolved_haben = final_haben
        item.resolved_mwst_code = final_mwst_code
        item.resolved_mwst_pct = final_mwst_pct
        return item

    async def reject(self, item_id: int) -> ReviewQueueItem | None:
        if not await self._claim(item_id, "rejected"):
            return None
        return await self._get_item(item_id)

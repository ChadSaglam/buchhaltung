"""Per-tenant background training, queued through the ``training_jobs`` table.

The API side only inserts a row (:func:`enqueue_training`); the worker side
(:class:`TrainingWorker`) claims pending rows and retrains one tenant per
job. Because the queue lives in the database the two halves can run in the
same process (``RUN_WORKER_IN_API=true``, the dev default) or in separate
containers (``python -m app.worker``) without changing callers.

Jobs are deduplicated per tenant: while a pending job exists for a tenant a
second enqueue is a no-op, so a burst of corrections triggers one retrain.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.training_job import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TrainingJob,
)
from app.services.classifier import TenantClassifier

logger = logging.getLogger(__name__)


async def enqueue_training(session: AsyncSession, tenant_id: int) -> bool:
    """Queue a retrain for ``tenant_id`` in the caller's session (committed with it).

    Returns False when a pending job for the tenant already exists.
    """
    stmt = select(TrainingJob.id).where(TrainingJob.tenant_id == tenant_id, TrainingJob.status == STATUS_PENDING)
    if (await session.execute(stmt.limit(1))).scalar_one_or_none() is not None:
        logger.info("[TRAIN] tenant=%s already queued, skipped", tenant_id)
        return False
    session.add(TrainingJob(tenant_id=tenant_id, status=STATUS_PENDING))
    await session.flush()
    return True


class TrainingWorker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_once(self) -> int:
        """Claim and run every pending job. Returns the number of jobs processed."""
        processed = 0
        while True:
            job_id = await self._claim_next()
            if job_id is None:
                return processed
            await self._run(job_id)
            processed += 1

    async def _claim_next(self) -> int | None:
        async with self._session_factory() as session:
            stmt = (
                select(TrainingJob.id)
                .where(TrainingJob.status == STATUS_PENDING)
                .order_by(TrainingJob.requested_at, TrainingJob.id)
                .limit(1)
            )
            job_id = (await session.execute(stmt)).scalar_one_or_none()
            if job_id is None:
                return None
            # Conditional update = the claim; a concurrent worker that lost the
            # race sees rowcount 0 and moves on to the next job.
            result = await session.execute(
                update(TrainingJob)
                .where(TrainingJob.id == job_id, TrainingJob.status == STATUS_PENDING)
                .values(status=STATUS_RUNNING, started_at=datetime.now(UTC))
            )
            await session.commit()
            return job_id if result.rowcount == 1 else await self._claim_next()

    async def _run(self, job_id: int) -> None:
        async with self._session_factory() as session:
            job = await session.get(TrainingJob, job_id)
            if job is None:
                return
            try:
                result = await TenantClassifier(job.tenant_id, session).train_from_db()
                job.status = STATUS_FAILED if "error" in result else STATUS_DONE
                job.error = result.get("error")
                logger.info("[TRAIN] tenant=%s job=%s %s: %s", job.tenant_id, job_id, job.status, result)
            except asyncio.CancelledError:
                # Shutdown mid-training: hand the job back so the next pass retries it.
                await session.rollback()
                await self._release(job_id)
                raise
            except Exception as exc:
                await session.rollback()
                job = await session.get(TrainingJob, job_id)
                if job is None:
                    return
                job.status = STATUS_FAILED
                job.error = f"{type(exc).__name__}: {exc}"[:2000]
                logger.exception("[TRAIN] tenant=%s job=%s failed", job.tenant_id, job_id)
            job.finished_at = datetime.now(UTC)
            await session.commit()

    async def _release(self, job_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(TrainingJob)
                .where(TrainingJob.id == job_id, TrainingJob.status == STATUS_RUNNING)
                .values(status=STATUS_PENDING, started_at=None)
            )
            await session.commit()

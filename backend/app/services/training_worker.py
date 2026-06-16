"""Per-tenant background training worker.

In-process async implementation with a stable interface that can later be
backed by Redis/Celery (V9) without changing callers. Jobs are deduplicated
per tenant so concurrent correction bursts trigger at most one retrain.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.classifier import TenantClassifier

logger = logging.getLogger(__name__)

class TrainingWorker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def enqueue_training(self, tenant_id: int) -> bool:
        """Schedule a retrain for a tenant. Returns False if one is already running."""
        async with self._lock:
            existing = self._tasks.get(tenant_id)
            if existing and not existing.done():
                logger.info("[TRAIN] tenant=%s already training, skipped", tenant_id)
                return False
            task = asyncio.create_task(self._run(tenant_id))
            self._tasks[tenant_id] = task
            return True

    async def _run(self, tenant_id: int) -> None:
        try:
            async with self._session_factory() as session:
                clf = TenantClassifier(tenant_id, session)
                result = await clf.train_from_db()
                await session.commit()
                logger.info("[TRAIN] tenant=%s done: %s", tenant_id, result)
        except Exception:
            logger.exception("[TRAIN] tenant=%s failed", tenant_id)
        finally:
            async with self._lock:
                self._tasks.pop(tenant_id, None)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = [t for t in self._tasks.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

_worker: TrainingWorker | None = None

def init_training_worker(session_factory: async_sessionmaker[AsyncSession]) -> TrainingWorker:
    global _worker
    _worker = TrainingWorker(session_factory)
    return _worker

def get_training_worker() -> TrainingWorker:
    if _worker is None:
        raise RuntimeError("Training worker not initialized. Call init_training_worker() at startup.")
    return _worker
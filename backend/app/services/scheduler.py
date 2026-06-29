from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


class ScheduledTask:
    def __init__(self, name: str, interval: timedelta, coro_factory) -> None:
        self.name = name
        self.interval = interval
        self.coro_factory = coro_factory
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("[SCHEDULER] started %s every %s", self.name, self.interval)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval.total_seconds())
            try:
                await self.coro_factory()
                logger.info("[SCHEDULER] %s ran at %s", self.name, datetime.now(UTC))
            except Exception:
                logger.exception("[SCHEDULER] %s failed", self.name)

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()


class CronScheduler:
    """Lightweight in-process cron scheduler. Replace with Celery Beat for V9+ scale."""

    def __init__(self) -> None:
        self._tasks: list[ScheduledTask] = []

    def register(self, name: str, interval: timedelta, coro_factory) -> None:
        self._tasks.append(ScheduledTask(name, interval, coro_factory))

    def start_all(self) -> None:
        for t in self._tasks:
            t.start()

    def stop_all(self) -> None:
        for t in self._tasks:
            t.cancel()


_scheduler = CronScheduler()


def get_scheduler() -> CronScheduler:
    return _scheduler
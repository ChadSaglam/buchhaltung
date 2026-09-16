from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

#: How long a shutdown waits for running jobs to unwind, in total. Compose gives
#: the worker 120 s (``stop_grace_period``), so this stays well inside it —
#: a SIGKILL half-way through the unwinding is the thing it exists to avoid.
STOP_TIMEOUT_SECONDS = 30.0


class ScheduledTask:
    def __init__(self, name: str, interval: timedelta, coro_factory) -> None:
        self.name = name
        self.interval = interval
        self.coro_factory = coro_factory
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("[SCHEDULER] started %s every %s", self.name, self.interval)

    async def run_once(self) -> None:
        try:
            await self.coro_factory()
            logger.info("[SCHEDULER] %s ran at %s", self.name, datetime.now(UTC))
        except Exception:
            logger.exception("[SCHEDULER] %s failed", self.name)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval.total_seconds())
            await self.run_once()

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def wait(self, frist: float) -> bool:
        """Wait for the cancelled task to actually finish. True if it did.

        Cancelling is a request, not an event (B-57). Until the task is awaited
        its ``except asyncio.CancelledError`` never runs — and the training
        worker's handler is the thing that hands a half-finished job back to the
        queue. Exiting without awaiting leaves the row `running` forever, and
        because jobs are deduplicated per tenant, that tenant never trains again.
        """
        if self._task is None or self._task.done():
            return True
        # `asyncio.wait`, not `await self._task`: waiting on a cancelled task
        # re-raises its CancelledError in *this* coroutine, and a shutdown path
        # that swallows CancelledError swallows its own cancellation with it.
        # `wait` reports the outcome instead of propagating it.
        _done, offen = await asyncio.wait({self._task}, timeout=max(0.0, frist))
        return not offen


class CronScheduler:
    """Lightweight in-process interval scheduler.

    Runs inside the API (``RUN_WORKER_IN_API=true``) or in the dedicated worker
    process (``python -m app.worker``) — see ``app/worker.py``.
    """

    def __init__(self) -> None:
        self._tasks: list[ScheduledTask] = []

    def register(self, name: str, interval: timedelta, coro_factory) -> None:
        self._tasks.append(ScheduledTask(name, interval, coro_factory))

    @property
    def names(self) -> list[str]:
        return [t.name for t in self._tasks]

    def start_all(self) -> None:
        for t in self._tasks:
            t.start()

    async def run_all_once(self) -> None:
        """One pass over every registered task, in registration order (``--once``)."""
        for t in self._tasks:
            await t.run_once()

    async def stop_all(self, frist: float = STOP_TIMEOUT_SECONDS) -> None:
        """Cancel every task and wait for it to unwind.

        The budget is per shutdown, not per task, so a container that is being
        killed cannot be held open task-by-task past its grace period.
        """
        for t in self._tasks:
            t.cancel()
        if not self._tasks:
            return
        deadline = asyncio.get_running_loop().time() + frist
        for t in self._tasks:
            rest = max(0.0, deadline - asyncio.get_running_loop().time())
            if not await t.wait(rest):
                logger.warning("[SCHEDULER] %s did not stop within the grace period", t.name)


_scheduler = CronScheduler()


def get_scheduler() -> CronScheduler:
    return _scheduler

"""Background jobs: interval scheduler + classifier training worker.

Two ways to run the same thing:

* inside the API process — ``RUN_WORKER_IN_API=true`` (default; dev, single
  container): the lifespan in ``app/main.py`` calls :func:`start` / :func:`stop`;
* as its own process — ``python -m app.worker`` (compose ``worker`` service,
  API started with ``RUN_WORKER_IN_API=false``). ``--once`` runs a single pass
  over every job and exits, which is what the tests and ops smoke checks use.

Work reaches the worker through the database (``training_jobs``), never
through process memory, so both modes behave the same.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
from datetime import timedelta

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.services.scheduler import CronScheduler
from app.services.training_worker import TrainingWorker

logger = logging.getLogger(__name__)

TRAINING_TASK = "training-jobs"


class BackgroundJobs:
    """Everything that runs on a timer, bundled so both entry points start the same set."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        poll_interval: float | None = None,
    ) -> None:
        interval = timedelta(seconds=poll_interval if poll_interval is not None else settings.WORKER_POLL_INTERVAL)
        self.training = TrainingWorker(session_factory)
        self.scheduler = CronScheduler()
        self.scheduler.register(TRAINING_TASK, interval, self.training.run_once)

    @property
    def task_names(self) -> list[str]:
        return self.scheduler.names

    def start(self) -> None:
        self.scheduler.start_all()

    async def run_once(self) -> None:
        await self.scheduler.run_all_once()

    async def stop(self) -> None:
        self.scheduler.stop_all()


async def run(*, once: bool, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
    if session_factory is None:
        from app.core.database import async_session

        session_factory = async_session

    jobs = BackgroundJobs(session_factory)
    if once:
        await jobs.run_once()
        return

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):  # non-POSIX loops
            loop.add_signal_handler(sig, stop.set)

    jobs.start()
    logger.info("[WORKER] running tasks=%s poll=%ss", jobs.task_names, settings.WORKER_POLL_INTERVAL)
    await stop.wait()
    await jobs.stop()
    logger.info("[WORKER] stopped")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description=__doc__.split("\n\n")[0])
    parser.add_argument("--once", action="store_true", help="run a single pass over every job and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, session_factory: async_sessionmaker[AsyncSession] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv()
    configure_logging(settings.LOG_LEVEL)
    asyncio.run(run(once=args.once, session_factory=session_factory))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess / compose
    raise SystemExit(main())

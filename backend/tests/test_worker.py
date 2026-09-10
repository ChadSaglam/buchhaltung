"""B-08 — scheduler + training worker outside the API process.

The queue is the `training_jobs` table: the API enqueues, a worker pass
(`python -m app.worker --once`) claims and trains. The lifespan only starts
the in-process worker when RUN_WORKER_IN_API is true.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import worker as worker_module
from app.core.config import settings
from app.main import app
from app.models.classifier_model import ClassifierModel
from app.models.training_job import STATUS_DONE, STATUS_FAILED, STATUS_PENDING, TrainingJob
from app.services.classifier import AUTO_RETRAIN_THRESHOLD
from app.services.training_worker import TrainingWorker, enqueue_training
from app.worker import TRAINING_TASK, BackgroundJobs
from tests.conftest import _IS_SQLITE, TEST_DATABASE_URL
from tests.factories import auth_headers, create_tenant, create_training_row, create_user

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _seed_training_rows(db_session, tenant, n: int = 6) -> None:
    for i in range(n):
        await create_training_row(db_session, tenant, f"Lieferant {i} Rechnung", "6500" if i % 2 else "6570")


async def _jobs(db_session, tenant_id: int) -> list[TrainingJob]:
    # Fresh rows: the worker commits through its own sessions.
    db_session.expire_all()
    result = await db_session.execute(
        select(TrainingJob).where(TrainingJob.tenant_id == tenant_id).order_by(TrainingJob.id)
    )
    return list(result.scalars().all())


# ── queue semantics ──────────────────────────────────────────────────────────


async def test_enqueue_is_deduplicated_per_tenant(db_session):
    tenant = await create_tenant(db_session)
    tenant_id = tenant.id
    other = await create_tenant(db_session)
    other_id = other.id

    assert await enqueue_training(db_session, tenant.id) is True
    assert await enqueue_training(db_session, tenant.id) is False
    assert await enqueue_training(db_session, other.id) is True
    await db_session.commit()

    assert [j.status for j in await _jobs(db_session, tenant_id)] == [STATUS_PENDING]
    assert len(await _jobs(db_session, other_id)) == 1


async def test_worker_pass_trains_pending_job(db_session, engine):
    tenant = await create_tenant(db_session)
    tenant_id = tenant.id
    await _seed_training_rows(db_session, tenant)
    await enqueue_training(db_session, tenant.id)
    await db_session.commit()

    worker = TrainingWorker(async_sessionmaker(engine, expire_on_commit=False))
    assert await worker.run_once() == 1
    assert await worker.run_once() == 0  # nothing left to claim

    (job,) = await _jobs(db_session, tenant_id)
    assert job.status == STATUS_DONE
    assert job.error is None
    assert job.started_at is not None and job.finished_at is not None

    model = (
        await db_session.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tenant_id))
    ).scalar_one()
    assert model.total_samples == 6

    # A retrain can be queued again once the previous job is no longer pending.
    assert await enqueue_training(db_session, tenant_id) is True


async def test_worker_marks_job_failed_when_training_cannot_run(db_session, engine):
    tenant = await create_tenant(db_session)  # no training data at all
    tenant_id = tenant.id
    await enqueue_training(db_session, tenant.id)
    await db_session.commit()

    worker = TrainingWorker(async_sessionmaker(engine, expire_on_commit=False))
    assert await worker.run_once() == 1

    (job,) = await _jobs(db_session, tenant_id)
    assert job.status == STATUS_FAILED
    assert "Zu wenige Daten" in (job.error or "")


# ── API → queue → worker ─────────────────────────────────────────────────────


async def test_corrections_via_api_are_picked_up_by_one_worker_pass(client, db_session, engine):
    tenant = await create_tenant(db_session)
    tenant_id = tenant.id
    user = await create_user(db_session, tenant)
    headers = auth_headers(user)

    for i in range(AUTO_RETRAIN_THRESHOLD):
        resp = await client.post(
            "/api/classify/correct",
            json={
                "beschreibung": f"Lieferant {i} Rechnung",
                "original_soll": "4000",
                "original_haben": "1020",
                "corrected_soll": "6500" if i % 2 else "6570",
                "corrected_haben": "1020",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    assert [j.status for j in await _jobs(db_session, tenant_id)] == [STATUS_PENDING]

    jobs = BackgroundJobs(async_sessionmaker(engine, expire_on_commit=False), poll_interval=60)
    assert jobs.task_names == [TRAINING_TASK]
    await jobs.run_once()

    (job,) = await _jobs(db_session, tenant_id)
    assert job.status == STATUS_DONE
    assert (
        await db_session.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tenant_id))
    ).scalar_one().total_samples == AUTO_RETRAIN_THRESHOLD


# ── entrypoint ───────────────────────────────────────────────────────────────


def test_cli_parses_once_flag():
    assert worker_module.parse_args(["--once"]).once is True
    assert worker_module.parse_args([]).once is False


async def test_run_once_entrypoint_processes_the_queue(db_session, engine):
    tenant = await create_tenant(db_session)
    tenant_id = tenant.id
    await _seed_training_rows(db_session, tenant)
    await enqueue_training(db_session, tenant.id)
    await db_session.commit()

    await worker_module.run(once=True, session_factory=async_sessionmaker(engine, expire_on_commit=False))

    (job,) = await _jobs(db_session, tenant_id)
    assert job.status == STATUS_DONE


@pytest.mark.skipif(_IS_SQLITE, reason="A separate process cannot see an in-memory SQLite database.")
async def test_python_m_app_worker_once_runs_in_a_separate_process(db_session, engine):
    tenant = await create_tenant(db_session)
    tenant_id = tenant.id
    await _seed_training_rows(db_session, tenant)
    await enqueue_training(db_session, tenant.id)
    await db_session.commit()

    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    proc = subprocess.run(  # noqa: ASYNC221 - a blocking child process is the point of this test
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr

    (job,) = await _jobs(db_session, tenant_id)
    assert job.status == STATUS_DONE


# ── lifespan ─────────────────────────────────────────────────────────────────


async def test_lifespan_starts_in_process_worker_by_default(monkeypatch):
    monkeypatch.setattr(settings, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(settings, "RUN_WORKER_IN_API", True)
    async with app.router.lifespan_context(app):
        jobs = app.state.background_jobs
        assert isinstance(jobs, BackgroundJobs)
        assert jobs.task_names == [TRAINING_TASK]
    assert app.state.background_jobs is jobs


async def test_lifespan_skips_worker_when_flag_is_false(monkeypatch):
    monkeypatch.setattr(settings, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(settings, "RUN_WORKER_IN_API", False)
    async with app.router.lifespan_context(app):
        assert app.state.background_jobs is None

"""B-57 — the worker runs where nobody is watching.

Since B-08 the jobs live in their own container. Everything here is about what
happens when that container dies badly, because that is the case with no human
in the room.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.training_job import (
    STATUS_DONE,
    STATUS_PENDING,
    STATUS_RUNNING,
    TrainingJob,
)
from app.services.classifier import EIN_EINZIGES_KONTO, ZU_WENIG_DATEN, TrainingDatenFehlen, fit_pipeline
from app.services.scheduler import CronScheduler
from app.services.training_worker import STALE_AFTER, TrainingWorker, enqueue_training
from tests.factories import auth_headers, create_tenant, create_user

pytestmark = pytest.mark.asyncio


@pytest.fixture
def maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


# --------------------------------------------------------------------------- #
# The reaper
# --------------------------------------------------------------------------- #


async def _job(db, tenant, status: str, started_at: datetime | None) -> TrainingJob:
    job = TrainingJob(tenant_id=tenant.id, status=status, started_at=started_at)
    db.add(job)
    await db.commit()
    return job


async def test_a_job_a_dead_worker_left_running_is_handed_back(db_session, maker):
    """A SIGKILLed worker never runs its CancelledError handler, so the row stays
    `running` — and dedup then queues that tenant's retrains behind a job nobody
    will ever finish."""
    tenant = await create_tenant(db_session)
    job = await _job(db_session, tenant, STATUS_RUNNING, datetime.now(UTC) - STALE_AFTER - timedelta(minutes=1))

    reaped = await TrainingWorker(maker).reap_stale()

    await db_session.refresh(job)
    assert reaped == 1
    assert job.status == STATUS_PENDING
    assert job.started_at is None


async def test_a_job_that_is_merely_slow_is_left_alone(db_session, maker):
    tenant = await create_tenant(db_session)
    job = await _job(db_session, tenant, STATUS_RUNNING, datetime.now(UTC) - timedelta(seconds=30))

    assert await TrainingWorker(maker).reap_stale() == 0

    await db_session.refresh(job)
    assert job.status == STATUS_RUNNING


async def test_a_running_job_with_no_start_time_is_treated_as_stale(db_session, maker):
    """A row from before `started_at` existed must not be immortal."""
    tenant = await create_tenant(db_session)
    job = await _job(db_session, tenant, STATUS_RUNNING, None)

    assert await TrainingWorker(maker).reap_stale() == 1

    await db_session.refresh(job)
    assert job.status == STATUS_PENDING


async def test_the_reaper_never_touches_a_finished_job(db_session, maker):
    tenant = await create_tenant(db_session)
    job = await _job(db_session, tenant, STATUS_DONE, datetime.now(UTC) - timedelta(days=9))

    assert await TrainingWorker(maker).reap_stale() == 0

    await db_session.refresh(job)
    assert job.status == STATUS_DONE


async def test_a_reaped_job_gets_picked_up_again(db_session, maker):
    tenant = await create_tenant(db_session)
    await _job(db_session, tenant, STATUS_RUNNING, datetime.now(UTC) - STALE_AFTER - timedelta(minutes=1))

    processed = await TrainingWorker(maker).run_once()

    assert processed == 1, "run_once reaps before it claims, so the dead job runs"


async def test_a_stuck_job_no_longer_blocks_the_tenants_next_retrain(db_session, maker):
    """The whole point: dedup is on a *pending* row, so a stuck `running` row plus
    a fresh enqueue used to leave the tenant with a queue that never drains."""
    tenant = await create_tenant(db_session)
    await _job(db_session, tenant, STATUS_RUNNING, datetime.now(UTC) - STALE_AFTER - timedelta(minutes=1))
    await enqueue_training(db_session, tenant.id)
    await db_session.commit()

    await TrainingWorker(maker).reap_stale()

    offen = (
        (
            await db_session.execute(
                select(TrainingJob).where(TrainingJob.tenant_id == tenant.id, TrainingJob.status == STATUS_PENDING)
            )
        )
        .scalars()
        .all()
    )
    assert len(offen) == 2


# --------------------------------------------------------------------------- #
# Shutting down
# --------------------------------------------------------------------------- #


async def test_stopping_waits_for_the_task_to_unwind():
    """Cancelling is a request, not an event: until the task is awaited its
    `except CancelledError` never runs, and that handler is what returns the job."""
    aufgeraeumt = asyncio.Event()

    async def job():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            aufgeraeumt.set()
            raise

    scheduler = CronScheduler()
    scheduler.register("test", timedelta(seconds=0.01), job)
    scheduler.start_all()
    await asyncio.sleep(0.05)

    await scheduler.stop_all(frist=2.0)

    assert aufgeraeumt.is_set()


async def _langsam_beim_aufraeumen(dauer: float):
    """Unwinds, but slowly — like a training run finishing its write."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await asyncio.shield(asyncio.sleep(dauer))
        raise


async def test_stopping_gives_up_rather_than_hanging_forever():
    """A task that unwinds slower than the grace period must not hold the
    container open — the alternative is a SIGKILL half-way through."""
    scheduler = CronScheduler()
    scheduler.register("slow", timedelta(seconds=0.01), lambda: _langsam_beim_aufraeumen(0.4))
    scheduler.start_all()
    await asyncio.sleep(0.05)

    start = asyncio.get_running_loop().time()
    await scheduler.stop_all(frist=0.05)
    dauer = asyncio.get_running_loop().time() - start

    assert dauer < 0.3, "stop_all waited past its own budget"
    await asyncio.sleep(0.5)  # let the task finish so the loop closes clean


async def test_stopping_an_empty_scheduler_is_fine():
    await CronScheduler().stop_all(frist=0.1)


async def test_the_budget_is_per_shutdown_not_per_task():
    """Three slow tasks must not cost three timeouts."""
    scheduler = CronScheduler()
    for i in range(3):
        scheduler.register(f"t{i}", timedelta(seconds=0.01), lambda: _langsam_beim_aufraeumen(0.4))
    scheduler.start_all()
    await asyncio.sleep(0.05)

    start = asyncio.get_running_loop().time()
    await scheduler.stop_all(frist=0.15)
    dauer = asyncio.get_running_loop().time() - start

    assert dauer < 0.35, "the budget is per shutdown, not per task"
    await asyncio.sleep(0.5)


# --------------------------------------------------------------------------- #
# A single account is the user's problem, not the server's
# --------------------------------------------------------------------------- #


def _rows(konten: list[str]) -> list[dict[str, str]]:
    return [{"Beschreibung": f"Lieferant {chr(97 + i)} AG", "KontoSoll": k} for i, k in enumerate(konten)]


async def test_one_account_raises_a_typed_error_instead_of_a_sklearn_crash():
    with pytest.raises(TrainingDatenFehlen) as exc:
        fit_pipeline(_rows(["6500"] * 8))

    assert "6500" in str(exc.value)
    assert str(exc.value) == EIN_EINZIGES_KONTO.format(konto="6500")


async def test_two_accounts_still_train():
    pipeline, n_rows, n_classes, _cv, _acc = fit_pipeline(_rows(["6500", "6570"] * 4))

    assert n_classes == 2
    assert n_rows == 8
    assert pipeline is not None


async def test_too_few_rows_is_the_same_kind_of_error():
    with pytest.raises(TrainingDatenFehlen) as exc:
        fit_pipeline(_rows(["6500", "6570"]))

    assert str(exc.value) == ZU_WENIG_DATEN


async def test_no_rows_at_all_is_the_same_kind_of_error():
    with pytest.raises(TrainingDatenFehlen):
        fit_pipeline([])


async def test_training_one_account_over_the_api_is_400_not_500(client, db_session):
    """The most ordinary state a new tenant can be in: every receipt so far went
    to the same account."""
    from tests.factories import create_training_row

    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    for i in range(8):
        await create_training_row(db_session, tenant, beschreibung=f"Lieferant {chr(97 + i)} AG", kt_soll="6500")

    res = await client.post("/api/classify/train", headers=auth_headers(user))

    assert res.status_code == 400
    assert "6500" in res.json()["error"]["message"]


# --------------------------------------------------------------------------- #
# The import survives a training failure
# --------------------------------------------------------------------------- #


def _banana_csv(n: int) -> bytes:
    letters = "abcdefghijklmnopqrstuvwxyz"
    lines = ["Datum,Beschreibung,KtSoll,KtHaben,Betrag"]
    for i in range(n):
        konto = "6500" if i % 2 else "6570"
        lines.append(f"15.03.2025,Lieferant {letters[i]} AG,{konto},1020,{100 + i}.00")
    return "\n".join(lines).encode()


async def test_the_import_survives_a_training_failure(client, db_session, monkeypatch):
    """Training is the long, failing part. Rolling the import back because of it
    made the user re-upload a 2'000-line file to fix a different feature."""
    from app.models.training_data import TrainingRow
    from app.services import classifier as classifier_module

    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    async def boom(self):
        raise RuntimeError("the model exploded")

    monkeypatch.setattr(classifier_module.TenantClassifier, "train_from_db", boom)

    res = await client.post(
        "/api/import/banana",
        headers=auth_headers(user),
        files={"file": ("b.csv", _banana_csv(8), "text/csv")},
    )

    assert res.status_code == 200, res.text
    assert "error" in res.json()["training"]
    rows = (await db_session.execute(select(TrainingRow).where(TrainingRow.tenant_id == tenant.id))).scalars().all()
    assert len(rows) == 8, "the imported rows must still be there"


async def test_a_successful_import_still_trains(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    body = (
        await client.post(
            "/api/import/banana",
            headers=auth_headers(user),
            files={"file": ("b.csv", _banana_csv(10), "text/csv")},
        )
    ).json()

    assert body["imported"] == 10
    assert "error" not in body.get("training", {})


async def test_an_import_of_one_account_reports_it_without_losing_the_rows(client, db_session):
    from app.models.training_data import TrainingRow

    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    letters = "abcdefghij"
    csv = "\n".join(
        ["Datum,Beschreibung,KtSoll,KtHaben,Betrag"]
        + [f"15.03.2025,Lieferant {letters[i]} AG,6500,1020,{100 + i}.00" for i in range(8)]
    ).encode()

    body = (
        await client.post("/api/import/banana", headers=auth_headers(user), files={"file": ("b.csv", csv, "text/csv")})
    ).json()

    assert body["imported"] == 8
    assert "6500" in body["training"]["error"]
    rows = (await db_session.execute(select(TrainingRow).where(TrainingRow.tenant_id == tenant.id))).scalars().all()
    assert len(rows) == 8


# --------------------------------------------------------------------------- #
# Sentry
# --------------------------------------------------------------------------- #


async def test_the_worker_configures_sentry():
    """Until B-57 the API had error tracking and the worker did not — so a crash
    in the one process nobody watches was invisible; the queue just stopped."""
    from pathlib import Path

    quelle = Path(__file__).resolve().parents[1] / "app" / "worker.py"
    text = quelle.read_text(encoding="utf-8")

    assert "configure_sentry" in text
    assert text.index("configure_sentry(settings.SENTRY_DSN") > text.index("def main(")

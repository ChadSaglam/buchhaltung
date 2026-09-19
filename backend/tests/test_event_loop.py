"""B-49 — CPU/blocking work runs in worker threads; the event loop keeps serving."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.services.classifier import TenantClassifier, TrainingDatenFehlen, fit_pipeline
from app.services.scanner import vision_ollama
from app.services.scanner.scanner_service import ScannerService
from tests.factories import create_tenant, create_training_row, create_user


def test_fit_pipeline_is_pure_and_needs_five_rows():
    # B-57: it now says *why* it cannot train, because "too few rows" and "one
    # single account" are different problems with different answers.
    with pytest.raises(TrainingDatenFehlen):
        fit_pipeline([])
    with pytest.raises(TrainingDatenFehlen):
        fit_pipeline([{"Beschreibung": "a", "KontoSoll": "4000"}] * 4)
    rows = [{"Beschreibung": f"Lieferant {i}", "KontoSoll": "4000" if i % 2 else "6500"} for i in range(10)]
    pipeline, n_rows, n_classes, _cv, train_acc = fit_pipeline(rows)
    assert (n_rows, n_classes) == (10, 2)
    assert 0 <= train_acc <= 1
    assert pipeline.predict(["lieferant 1"])[0] in {"4000", "6500"}


@pytest.mark.asyncio
async def test_training_does_not_block_the_loop(db_session):
    tenant = await create_tenant(db_session)
    for i in range(300):
        await create_training_row(db_session, tenant, f"Lieferant {i} Rechnung {i % 7}", str(4000 + (i % 5) * 100))
    clf = TenantClassifier(tenant.id, db_session)

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.005)

    t = asyncio.create_task(ticker())
    result = await clf.train_from_db()
    t.cancel()
    assert "error" not in result
    # A blocked loop would leave the ticker at ~1; a free one ticks many times during fit + CV.
    assert ticks > 5


@pytest.mark.asyncio
async def test_scanner_status_never_uses_the_sync_shim(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)

    def boom(_coro):
        raise AssertionError("sync shim used on the request path")

    with (
        patch.object(vision_ollama, "_run_sync", boom),
        patch.object(
            vision_ollama, "check_ollama_status_async", return_value={"ok": True, "models": [], "vision_models": []}
        ),
    ):
        status = await service.get_status()
    assert status.ok is True

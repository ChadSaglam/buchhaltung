from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.scanner import ScannerStatusResponse
from app.services.scanner.base import ProviderExtractionResult
from app.services.scanner.scanner_service import ScannerService
from tests.factories import auth_headers, create_tenant, create_user

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"


def _ok_status() -> ScannerStatusResponse:
    return ScannerStatusResponse(
        ok=True,
        error=None,
        models=[],
        vision_models=["gemma3:12b"],
        best_vision="gemma3:12b",
        scanner_mode="custom-first",
        pipeline=[],
        custom_ocr_available=True,
    )


@pytest.mark.asyncio
async def test_validate_upload_rejects_non_image(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)

    with pytest.raises(HTTPException):
        service._validate_upload(content_type="text/plain", content=b"hello")


@pytest.mark.asyncio
async def test_ocr_first_path_classifies_invoice(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)

    ocr_result = ProviderExtractionResult(
        data={"ocr_text": "Acme AG Rechnung CHF 100.00"},
        steps=[],
        attempts=[],
        providers=[],
        ocr_provider="custom-ocr",
        ocr_worked=True,
    )

    with (
        patch.object(service.registry, "get_ocr_provider") as mock_ocr,
        patch.object(service.registry, "get_vision_provider") as mock_vision,
        patch(
            "app.services.scanner.scanner_service.parse_invoice_text",
            return_value={"vendor": "Acme AG", "total_amount": 100.0, "vat_rate": 8.1},
        ),
        patch.object(ScannerService, "get_status", new=AsyncMock(return_value=_ok_status())),
    ):
        mock_ocr.return_value.is_available.return_value = True
        mock_ocr.return_value.extract_async = AsyncMock(return_value=ocr_result)
        mock_vision.return_value.is_available.return_value = False

        response = await service.extract(
            file_name="invoice.png",
            content_type="image/png",
            content=PNG_BYTES,
            model="",
        )

    assert response.data.vendor == "Acme AG"
    assert response.data.ocr_worked is True


@pytest.mark.asyncio
async def test_vision_fallback_when_ocr_empty(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)

    empty_ocr = ProviderExtractionResult(
        data=None,
        steps=[],
        attempts=[],
        providers=[],
        ocr_provider="custom-ocr",
        ocr_worked=False,
        error="Kein OCR-Text erkannt.",
    )
    vision_result = ProviderExtractionResult(
        data={"vendor": "Vision GmbH", "total_amount": 50.0, "vat_rate": 0},
        steps=[],
        attempts=[],
        providers=[],
        selected_model="gemma3:12b",
        ocr_provider="ollama",
        ocr_worked=False,
    )

    with (
        patch.object(service.registry, "get_ocr_provider") as mock_ocr,
        patch.object(service.registry, "get_vision_provider") as mock_vision,
        patch.object(ScannerService, "get_status", new=AsyncMock(return_value=_ok_status())),
    ):
        mock_ocr.return_value.is_available.return_value = True
        mock_ocr.return_value.extract_async = AsyncMock(return_value=empty_ocr)
        mock_vision.return_value.is_available.return_value = True
        mock_vision.return_value.extract.return_value = vision_result

        response = await service.extract(
            file_name="invoice.png",
            content_type="image/png",
            content=PNG_BYTES,
            model="gemma3:12b",
        )

    assert response.data.vendor == "Vision GmbH"
    assert response.data.vision_model == "gemma3:12b"


@pytest.mark.asyncio
async def test_get_or_create_config_survives_a_concurrent_insert(db_session):
    """Two first calls for the same tenant race; the loser must reuse the winner's row."""
    from app.models.scanner_config import ScannerConfig
    from tests.factories import create_tenant, create_user

    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)

    # The "winner" already inserted its row …
    winner = ScannerConfig(
        tenant_id=tenant.id,
        ocr_provider="custom-ocr",
        vision_provider="ollama",
        fallback_provider="ollama",
        ollama_base_url="http://localhost:11434",
        pdf_ocr_enabled=True,
        invoice_matching_enabled=True,
        auto_classification_enabled=True,
    )
    db_session.add(winner)
    await db_session.commit()
    db_session.expunge(winner)

    # … but the "loser" selected before that and saw nothing.
    original_execute = db_session.execute
    calls = {"n": 0}

    class _Empty:
        def scalar_one_or_none(self):
            return None

    async def stale_first_select(stmt, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Empty()
        return await original_execute(stmt, *args, **kwargs)

    db_session.execute = stale_first_select  # type: ignore[method-assign]
    config = await service.get_or_create_config_model()
    assert config.id == winner.id


@pytest.mark.asyncio
async def test_scanner_config_service_survives_a_concurrent_insert(db_session):
    from app.models.scanner_config import ScannerConfig
    from app.services.scanner_config import ScannerConfigService
    from tests.factories import create_tenant

    tenant = await create_tenant(db_session)
    winner = ScannerConfig(tenant_id=tenant.id)
    db_session.add(winner)
    await db_session.commit()
    db_session.expunge(winner)

    original_execute = db_session.execute
    calls = {"n": 0}

    class _Empty:
        def scalar_one_or_none(self):
            return None

    async def stale_first_select(stmt, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Empty()
        return await original_execute(stmt, *args, **kwargs)

    db_session.execute = stale_first_select  # type: ignore[method-assign]
    config = await ScannerConfigService(tenant.id, db_session).get_or_create()
    assert config.id == winner.id
    # The session is still usable afterwards (no PendingRollbackError).
    await db_session.commit()


# --- B-48: extraction never zeroes a real amount; it flags it -------------------------------
def test_validate_and_fix_flags_large_amounts_instead_of_zeroing():
    from app.services.ollama_vision import _validate_and_fix

    data = _validate_and_fix({"vendor": "Bauunternehmung AG", "total_amount": 82_500.0, "vat_rate": 8.1})
    assert data["total_amount"] == 82_500.0
    assert data["needs_review"] is True
    assert "50'000" in data["review_reason"]

    small = _validate_and_fix({"vendor": "Migros", "total_amount": 42.0, "vat_rate": 7.9})
    assert "needs_review" not in small
    assert small["vat_rate"] == 8.1  # snapped to the nearest real Swiss rate


# --- B-42: tenant config cannot point the server at another host --------------------------
@pytest.mark.asyncio
async def test_config_update_ignores_ollama_url_and_ocr_command(client, db_session):
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.scanner_config import ScannerConfig

    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    headers = auth_headers(user)
    body = {
        "ocr_provider": "custom-ocr",
        "vision_provider": "ollama",
        "ollama_base_url": "http://169.254.169.254",
        "ocr_command": "rm -rf /",
    }
    for method in (client.put, client.patch):
        resp = await method("/api/scanner/config", json=body, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ollama_base_url"] == settings.OLLAMA_BASE_URL
    row = (await db_session.execute(select(ScannerConfig).where(ScannerConfig.tenant_id == tenant.id))).scalar_one()
    assert row.ollama_base_url != "http://169.254.169.254"
    assert row.ocr_command is None


@pytest.mark.asyncio
async def test_resolve_ollama_uses_deployment_url_not_tenant_row(db_session):
    from app.core.config import settings
    from app.services import ai_assistant
    from tests.factories import create_scanner_config

    tenant = await create_tenant(db_session)
    await create_scanner_config(db_session, tenant, ollama_base_url="http://evil:11434", default_ollama_model="")
    with patch.object(ai_assistant.settings, "OLLAMA_CHAT_MODEL", "llama3"):
        base_url, _model = await ai_assistant.resolve_ollama(tenant.id, db_session)
    assert base_url == settings.OLLAMA_BASE_URL.rstrip("/")

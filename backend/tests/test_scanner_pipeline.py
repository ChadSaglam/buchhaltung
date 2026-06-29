from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.scanner import ScannerStatusResponse
from app.services.scanner.base import ProviderExtractionResult
from app.services.scanner.scanner_service import ScannerService
from tests.factories import create_tenant, create_user

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


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

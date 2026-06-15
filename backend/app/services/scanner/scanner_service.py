from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scanner_config import ScannerConfig
from app.models.user import User
from app.schemas.scanner import (
    ExtractedInvoice,
    ScannerConfigResponse,
    ScannerConfigUpdate,
    ScannerExtractResponse,
    ScannerStatusResponse,
)
from app.services.classifier import TenantClassifier, calc_mwst
from app.services.ollama_vision import parse_invoice_text
from app.services.scanner.base import ScannerFile
from app.services.scanner.registry import ScannerProviderRegistry


MAX_FILE_SIZE = 20 * 1024 * 1024
CUSTOM_MODEL_NAME = "custom-ocr"


class ScannerService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.registry = ScannerProviderRegistry()

    async def get_status(self) -> ScannerStatusResponse:
        vision = self.registry.get_vision_provider("ollama")
        custom_available = self.registry.custom_ocr_available()
        config = await self.get_or_create_config_model()

        best_vision = config.default_ollama_model or vision.get_best_model()
        if custom_available and not config.default_ollama_model:
            best_vision = CUSTOM_MODEL_NAME

        return ScannerStatusResponse(
            ok=vision.is_available() or custom_available,
            error=None
            if (vision.is_available() or custom_available)
            else "Scanner nicht verfügbar (kein Vision-Modell und keine OCR).",
            models=self.registry.list_status_models(),
            vision_models=vision.get_vision_model_names(),
            best_vision=best_vision,
            scanner_mode="custom-first" if custom_available else "vision-only",
            pipeline=vision.get_pipeline(),
            custom_ocr_available=custom_available,
        )

    async def get_or_create_config_model(self) -> ScannerConfig:
        stmt = select(ScannerConfig).where(ScannerConfig.tenant_id == self.user.tenant_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if config is not None:
            return config

        config = ScannerConfig(
            tenant_id=self.user.tenant_id,
            ocr_provider="custom-ocr",
            vision_provider="ollama",
            fallback_provider="ollama",
            ollama_base_url="http://localhost:11434",
            default_ollama_model=None,
            ocr_command=None,
            pdf_ocr_enabled=True,
            invoice_matching_enabled=True,
            auto_classification_enabled=True,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_config(self) -> ScannerConfigResponse:
        config = await self.get_or_create_config_model()
        return ScannerConfigResponse.model_validate(config)

    async def update_config(self, payload: ScannerConfigUpdate) -> ScannerConfigResponse:
        config = await self.get_or_create_config_model()

        config.ocr_provider = payload.ocr_provider
        config.vision_provider = payload.vision_provider
        config.fallback_provider = payload.fallback_provider
        config.ollama_base_url = payload.ollama_base_url
        config.default_ollama_model = payload.default_ollama_model
        config.ocr_command = payload.ocr_command
        config.pdf_ocr_enabled = payload.pdf_ocr_enabled
        config.invoice_matching_enabled = payload.invoice_matching_enabled
        config.auto_classification_enabled = payload.auto_classification_enabled

        await self.db.commit()
        await self.db.refresh(config)
        return ScannerConfigResponse.model_validate(config)

    async def extract(
        self,
        *,
        file_name: str,
        content_type: str,
        content: bytes,
        model: str = "",
    ) -> ScannerExtractResponse:
        self._validate_upload(content_type=content_type, content=content)
        scanner_file = ScannerFile(
            filename=file_name,
            content_type=content_type,
            content=content,
        )

        config = await self.get_or_create_config_model()
        ocr = self.registry.get_ocr_provider(config.ocr_provider)
        vision = self.registry.get_vision_provider(config.vision_provider)

        status = await self.get_status()
        if not status.ok:
            raise HTTPException(503, status.error or "Scanner nicht verfügbar.")

        steps: list[dict[str, Any]] = [
            {"icon": "📤", "label": "Datei wird verarbeitet", "status": "done"}
        ]
        attempts: list[dict[str, Any]] = []
        providers: list[dict[str, str]] = []

        data: dict[str, Any] | None = None
        ocr_provider: str | None = None
        ocr_worked = False
        vision_model: str | None = None
        custom_available = ocr.is_available()

        effective_model = (model or config.default_ollama_model or "").strip()

        if self._use_custom_first(effective_model):
            ocr_result = ocr.extract(scanner_file)
            steps.extend(item.model_dump() for item in ocr_result.steps)
            attempts.extend(item.model_dump() for item in ocr_result.attempts)
            providers.extend(ocr_result.providers)
            if ocr_result.data and ocr_result.data.get("ocr_text"):
                parsed = parse_invoice_text(ocr_result.data["ocr_text"])
                if parsed:
                    data = parsed
                    ocr_provider = ocr_result.ocr_provider
                    ocr_worked = True
                    steps.append(
                        {
                            "icon": "📝",
                            "label": "Rechnungsdetails aus OCR-Text extrahiert",
                            "status": "done",
                            "provider": "ocr",
                            "model": ocr_result.ocr_provider,
                        }
                    )

        if not data and vision.is_available():
            vision_result = vision.extract(
                scanner_file=scanner_file,
                selected_model=effective_model,
                preferred_models=["gemma3:12b", "gemma3:4b", "kimi-k2.5:cloud"],
            )
            steps.extend(item.model_dump() for item in vision_result.steps)
            attempts.extend(item.model_dump() for item in vision_result.attempts)
            providers.extend(vision_result.providers)

            if vision_result.data:
                data = vision_result.data
                vision_model = vision_result.selected_model
                if not ocr_provider:
                    ocr_provider = vision_result.ocr_provider
            elif not data:
                raise HTTPException(422, vision_result.error or "Keine Rechnung erkannt.")

        if not data:
            raise HTTPException(422, "Keine Rechnung erkannt.")

        if config.auto_classification_enabled:
            steps.append(
                {
                    "icon": "🧠",
                    "label": "Kontierung wird berechnet",
                    "status": "active",
                    "provider": "classification",
                }
            )
            data = await self._classify_invoice(data)

            best_conf = data.get("classification_confidence") or 0
            best_source = data.get("classification_source") or ""
            steps.append(
                {
                    "icon": "🎯",
                    "label": f"Kontierung: {data.get('kt_soll', '')}/{data.get('kt_haben', '')} ({best_source}, {best_conf:.0%})",
                    "status": "done",
                    "provider": "classification",
                    "source": best_source,
                    "confidence": best_conf,
                }
            )

        data["vision_model"] = vision_model or ""
        data["ocr_provider"] = ocr_provider or ""
        data["ocr_worked"] = ocr_worked
        data["custom_ocr_available"] = custom_available
        data["scanner_steps"] = steps
        data["scanner_attempts"] = attempts
        data["scanner_providers"] = providers

        return ScannerExtractResponse(data=ExtractedInvoice(**data))

    def _validate_upload(self, *, content_type: str, content: bytes) -> None:
        if not content_type or not (
            content_type.startswith("image") or content_type == "application/pdf"
        ):
            raise HTTPException(400, "Nur Bilder (JPG, PNG, WebP) oder PDF erlaubt.")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"Datei zu gross (max {MAX_FILE_SIZE // 1024 // 1024} MB).")

    def _use_custom_first(self, selected_model: str) -> bool:
        selected = (selected_model or "").strip()
        return not selected or selected == CUSTOM_MODEL_NAME

    async def _classify_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        vendor = str(data.get("vendor", "") or "")
        description = str(data.get("description", "") or "")
        total_amount = float(data.get("total_amount", 0) or 0)
        vat_rate = self._normalize_vat_rate(data.get("vat_rate", 0))

        is_credit = any(
            kw in f"{vendor} {description}".lower()
            for kw in ["gutschrift", "zahlung erhalten", "einzahlung"]
        )

        clf = TenantClassifier(self.user.tenant_id, self.db)
        candidates = [
            vendor.strip(),
            f"{vendor} {description.split('(')[0].split(',')[0]}".strip(),
            f"{vendor} {description}".strip(),
            description.strip(),
        ]
        candidates = [candidate for candidate in candidates if candidate]

        best_result = None
        best_input = ""
        for text in candidates:
            result = await clf.classify(text, is_credit, total_amount)
            if best_result is None or result.confidence > best_result.confidence:
                best_result = result
                best_input = text
            if result.confidence >= 0.7:
                break

        if best_result is None:
            raise HTTPException(422, "Klassifizierung fehlgeschlagen.")

        if vat_rate > 0:
            if vat_rate >= 7.0:
                best_result.mwst_pct = "8.10"
                best_result.mwst_code = best_result.mwst_code or "I81"
            elif vat_rate >= 2.0:
                best_result.mwst_pct = "2.60"
                best_result.mwst_code = best_result.mwst_code or "I25"
            best_result.mwst_amount = calc_mwst(total_amount, best_result.mwst_pct)

        result_data = dict(data)
        result_data["kt_soll"] = best_result.kt_soll
        result_data["kt_haben"] = best_result.kt_haben
        result_data["mwst_code"] = best_result.mwst_code
        result_data["mwst_pct"] = best_result.mwst_pct
        result_data["mwst_amount"] = best_result.mwst_amount
        result_data["classification_confidence"] = best_result.confidence
        result_data["classification_source"] = best_result.source
        result_data["classification_input"] = best_input
        return result_data

    def _normalize_vat_rate(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.schemas.scanner import ScannerAttempt, ScannerEventStep
from app.services.scanner.base import BaseOcrProvider, ProviderExtractionResult, ScannerFile


class TesseractOcrProvider(BaseOcrProvider):
    name = "custom-ocr"
    kind = "local"

    def __init__(self, command: str | None = None, language: str = "deu+eng") -> None:
        self.command = command or os.getenv("SCANNER_OCR_COMMAND", "tesseract")
        self.language = language

    def is_available(self) -> bool:
        binary = self.command.split(" ", 1)[0]   # "tesseract"
        return shutil.which(binary) is not None

    def extract(self, scanner_file: ScannerFile) -> ProviderExtractionResult:
        attempts = [
            ScannerAttempt(
                provider="ocr",
                name=self.name,
                kind=self.kind,
                status="active",
                available=self.is_available(),
            )
        ]
        providers = [{"type": "ocr", "name": self.name, "kind": self.kind}]
        steps = [
            ScannerEventStep(
                icon="🧾",
                label="Eigene OCR wird getestet",
                status="active",
                provider="ocr",
                model=self.name,
            )
        ]

        if not self.is_available():
            attempts[0].status = "failed"
            steps.append(
                ScannerEventStep(
                    icon="⚠️",
                    label="Eigene OCR nicht verfügbar, Vision-Fallback startet",
                    status="failed",
                    provider="ocr",
                    model=self.name,
                )
            )
            return ProviderExtractionResult(
                data=None,
                steps=steps,
                attempts=attempts,
                providers=providers,
                ocr_provider=self.name,
                ocr_worked=False,
                error="Tesseract nicht verfügbar.",
            )

        suffix = Path(scanner_file.filename or "upload").suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(scanner_file.content)
            tmp_path = tmp.name

        try:
            command = self.command.split() + [tmp_path, "stdout", "-l", self.language]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )

            if completed.returncode != 0:
                attempts[0].status = "failed"
                steps.append(
                    ScannerEventStep(
                        icon="ℹ️",
                        label="Eigene OCR fehlgeschlagen, Vision-Fallback startet",
                        status="failed",
                        provider="ocr",
                        model=self.name,
                    )
                )
                return ProviderExtractionResult(
                    data=None,
                    steps=steps,
                    attempts=attempts,
                    providers=providers,
                    ocr_provider=self.name,
                    ocr_worked=False,
                    error=(completed.stderr or "OCR Fehler").strip(),
                )

            text = (completed.stdout or "").strip()
            if not text:
                attempts[0].status = "failed"
                steps.append(
                    ScannerEventStep(
                        icon="ℹ️",
                        label="Eigene OCR lieferte keinen Text, Vision-Fallback startet",
                        status="failed",
                        provider="ocr",
                        model=self.name,
                    )
                )
                return ProviderExtractionResult(
                    data=None,
                    steps=steps,
                    attempts=attempts,
                    providers=providers,
                    ocr_provider=self.name,
                    ocr_worked=False,
                    error="Kein OCR-Text erkannt.",
                )

            attempts[0].status = "done"
            steps.append(
                ScannerEventStep(
                    icon="✅",
                    label="Eigene OCR erfolgreich",
                    status="done",
                    provider="ocr",
                    model=self.name,
                )
            )
            return ProviderExtractionResult(
                data={"ocr_text": text},
                steps=steps,
                attempts=attempts,
                providers=providers,
                selected_model=self.name,
                ocr_provider=self.name,
                ocr_worked=True,
            )
        except subprocess.TimeoutExpired:
            attempts[0].status = "failed"
            steps.append(
                ScannerEventStep(
                    icon="⏱️",
                    label="Eigene OCR Timeout, Vision-Fallback startet",
                    status="failed",
                    provider="ocr",
                    model=self.name,
                )
            )
            return ProviderExtractionResult(
                data=None,
                steps=steps,
                attempts=attempts,
                providers=providers,
                ocr_provider=self.name,
                ocr_worked=False,
                error="OCR Timeout.",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
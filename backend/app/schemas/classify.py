"""Classification schemas."""
from pydantic import BaseModel


class ClassifyRequest(BaseModel):
    beschreibung: str
    betrag: float = 0.0
    is_credit: bool = False


class ClassificationResponse(BaseModel):
    kt_soll: str
    kt_haben: str
    mwst_code: str
    mwst_pct: str
    mwst_amount: float | str
    confidence: float
    source: str


class CorrectionRequest(BaseModel):
    beschreibung: str
    original_soll: str
    original_haben: str
    corrected_soll: str
    corrected_haben: str
    corrected_mwst_code: str = ""
    corrected_mwst_pct: str = ""


class TrainResponse(BaseModel):
    total_samples: int = 0
    classes: int = 0
    cv_accuracy: float | None = None
    train_accuracy: float | None = None
    error: str | None = None

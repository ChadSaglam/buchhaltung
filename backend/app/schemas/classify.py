"""Classification schemas."""

from pydantic import BaseModel

from app.schemas.common import Money


class ClassifyRequest(BaseModel):
    beschreibung: str
    betrag: Money = 0.0
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


class ClassifierInfoResponse(BaseModel):
    """What `/api/classify/info` actually returns (B-59).

    The hand-written frontend interface claimed `sklearn_version`,
    `model_size_kb` and `memory_size_kb`; the endpoint has never sent them.
    """

    has_model: bool
    #: False when a stored model is unsigned, foreign or altered — the classifier ignores it (B-34).
    model_trusted: bool
    model_accuracy: float
    train_accuracy: float
    total_samples: int
    classes: int
    memory_count: int
    correction_count: int
    trained_at: str | None = None

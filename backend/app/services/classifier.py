from __future__ import annotations

import pickle
import re
from dataclasses import dataclass

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline, FeatureUnion
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.models.correction import Correction
from app.models.training_data import TrainingRow
from app.models.classifier_model import ClassifierModel
from app.models.kontenplan import KontoDefault

CONFIDENCE_THRESHOLD = 0.45
AUTO_RETRAIN_THRESHOLD = 20

# ── Text preprocessing (unchanged from original) ──────────────

def preprocess(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(
        r"(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)", "", text
    )
    text = re.sub(r"(jan|feb|mr|apr|jun|jul|aug|sep|okt|nov|dez)", "", text)
    text = re.sub(r"[\d]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_memory_key(text: str) -> str:
    return preprocess(text).strip()


def calc_mwst(betrag: float, mwst_pct: str) -> float | str:
    if not mwst_pct or not betrag:
        return ""
    try:
        pct_val = abs(float(mwst_pct))
        mwst_val = round(float(betrag) * pct_val / (100 + pct_val), 2)
        if float(mwst_pct) < 0:
            mwst_val = -mwst_val
        return mwst_val
    except (ValueError, TypeError):
        return ""


# ── Classification rules (unchanged from original) ────────────
CLASSIFICATION_RULES: list[tuple[list[str], str, str, str, str]] = [
    (["iso-trade", "iso-center", "isolier", "material", "baumate", "spenglerei", "werkzeug", "schrauben", "befestigung"], "4000", "1020", "M81", "8.10"),
    (["handelsware", "einkauf waren", "grosshandel"], "4200", "1020", "M81", "8.10"),
    (["tankstelle", "benzin", "fuel", "agrola", "landi", "socar energy", "diesel", "avia ", "shell ", "bp ", "eni "], "6210", "1020", "I81", "8.10"),
    (["strassenverkehr", "verkehrsamt", "mfk ", "motorfahrzeug"], "6230", "1020", "", ""),
    (["garage", "auto ", "autoreparatur", "reifenwechsel", "pneu ", "dorfgarage", "feldmann"], "6200", "1020", "I81", "8.10"),
    (["autoversicherung", "fahrzeugversicherung"], "6230", "1020", "", ""),
    (["leasing fahrzeug", "autoleasing"], "6260", "1020", "", ""),
    (["lohn", "gehalt", "salary", "aksoy", "nettolohn"], "5000", "1020", "", ""),
    (["ahv", "iv ", "eo ", "alv", "fak ", "sozialversicherung"], "5700", "1020", "", ""),
    (["pension", "bvg", "vorsorge", "2. säule"], "5700", "1020", "", ""),
    (["spesen mitarbeiter", "spesenabrechnung", "spesen"], "5800", "1020", "", ""),
    (["miete", "mietverwaltung", "immobilien", "nebenkosten gebäude"], "6000", "1020", "", ""),
    (["reparatur", "unterhalt", "wartung", "service "], "6100", "1020", "I81", "8.10"),
    (["chadev", "software", "it-", "hosting", "domain", "server", "microsoft", "google workspace", "adobe", "informatik"], "6570", "1020", "I81", "8.10"),
    (["versicherung", "insurance", "vaudoise", "mobiliar", "helvetia", "axa ", "zurich ", "generali"], "6300", "1020", "", ""),
    (["werbung", "marketing", "inserat", "google ads", "facebook ads", "flyer", "druckerei", "visitenkarte"], "6600", "1020", "I81", "8.10"),
    (["coop", "migros", "subway", "gastro", "brot", "zopf", "tchibo", "restaurant", "mcdonald", "pizza", "kebab", "essen", "lunch"], "6500", "1020", "", ""),
    (["büromaterial", "schreibwaren", "post ", "porto", "briefmarke"], "6500", "1020", "I81", "8.10"),
    (["telefon", "swisscom", "sunrise", "salt ", "handy"], "6500", "1020", "I81", "8.10"),
    (["obi ", "interdiscount", "baumarkt", "jumbo ", "hornbach"], "6500", "1020", "I81", "8.10"),
    (["dienstleistungspreis", "bankgebühr", "kontoführung", "saldo dienst", "kontospesen", "kartengebühr"], "6900", "1020", "", ""),
    (["strom", "elektrizität", "gas ", "heizung", "ewz", "energie"], "6400", "1020", "I81", "8.10"),
    (["steuer", "direkte steuer", "gemeinde", "kanton"], "8900", "1020", "", ""),
    (["rechtsanwalt", "anwalt", "beratung", "consulting", "treuhänder", "notar", "revision"], "4400", "1020", "I81", "8.10"),
    (["zahlung qr-rechnung", "zahlung qr"], "6500", "1020", "", ""),
    (["lastschrift"], "6500", "1020", "", ""),
    (["clearing", "gutschrift"], "1020", "3000", "V81", "-8.10"),
    (["zahlung erhalten", "einzahlung kunde"], "1020", "1100", "", ""),
]


@dataclass
class ClassificationResult:
    kt_soll: str
    kt_haben: str
    mwst_code: str
    mwst_pct: str
    mwst_amount: float | str
    confidence: float = 0.0
    source: str = "Regeln"


class TenantClassifier:
    """Async, tenant-scoped classifier backed by PostgreSQL."""

    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db
        self._model: Pipeline | None = None
        self._konto_defaults: dict[str, dict] | None = None

    async def _load_model(self) -> Pipeline | None:
        if self._model is not None:
            return self._model
        result = await self.db.execute(
            select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id)
        )
        row = result.scalar_one_or_none()
        if row:
            self._model = pickle.loads(row.model_blob)
        return self._model

    async def _load_konto_defaults(self) -> dict[str, dict]:
        if self._konto_defaults is not None:
            return self._konto_defaults
        result = await self.db.execute(
            select(KontoDefault).where(KontoDefault.tenant_id == self.tenant_id)
        )
        self._konto_defaults = {
            r.konto_soll: {"KontoHaben": r.konto_haben, "MwStCode": r.mwst_code, "MwStUStProz": r.mwst_pct}
            for r in result.scalars().all()
        }
        return self._konto_defaults

    async def classify(self, beschreibung: str, is_credit: bool, betrag: float) -> ClassificationResult:
        if is_credit:
            pct = 8.10
            return ClassificationResult(
                kt_soll="1020", kt_haben="3000", mwst_code="V81", mwst_pct="-8.10",
                mwst_amount=round(-betrag * pct / (100 + pct), 2), confidence=1.0, source="Regeln",
            )

        # Layer 1: Memory
        key = make_memory_key(beschreibung)
        result = await self.db.execute(
            select(Memory).where(Memory.tenant_id == self.tenant_id, Memory.lookup_key == key)
        )
        mem = result.scalar_one_or_none()
        if mem:
            return ClassificationResult(
                kt_soll=mem.kt_soll, kt_haben=mem.kt_haben, mwst_code=mem.mwst_code, mwst_pct=mem.mwst_pct,
                mwst_amount=calc_mwst(betrag, mem.mwst_pct), confidence=1.0, source="Gedächtnis",
            )

        # Layer 2: ML
        model = await self._load_model()
        if model is not None:
            clean = preprocess(beschreibung)
            proba = model.predict_proba([clean])[0]
            confidence = float(proba.max())
            predicted_soll = model.classes_[proba.argmax()]
            if confidence >= CONFIDENCE_THRESHOLD:
                defaults = (await self._load_konto_defaults()).get(predicted_soll, {})
                kt_haben = defaults.get("KontoHaben", "1020")
                mwst_code = defaults.get("MwStCode", "")
                mwst_pct = defaults.get("MwStUStProz", "")
                return ClassificationResult(
                    kt_soll=predicted_soll, kt_haben=kt_haben, mwst_code=mwst_code, mwst_pct=mwst_pct,
                    mwst_amount=calc_mwst(betrag, mwst_pct), confidence=confidence, source="ML",
                )

        # Layer 3: Rules
        return self._classify_rules(beschreibung, betrag)

    def _classify_rules(self, beschreibung: str, betrag: float) -> ClassificationResult:
        desc_lower = beschreibung.lower()
        for keywords, account, gegen, code, pct in CLASSIFICATION_RULES:
            if any(kw in desc_lower for kw in keywords):
                return ClassificationResult(
                    kt_soll=account, kt_haben=gegen, mwst_code=code, mwst_pct=pct,
                    mwst_amount=calc_mwst(betrag, pct), confidence=0.0, source="Regeln",
                )
        return ClassificationResult(
            kt_soll="6500", kt_haben="1020", mwst_code="", mwst_pct="",
            mwst_amount="", confidence=0.0, source="Regeln",
        )

    async def save_to_memory(self, beschreibung: str, kt_soll: str, kt_haben: str, mwst_code: str = "", mwst_pct: str = ""):
        if not beschreibung.strip():
            return
        key = make_memory_key(beschreibung)
        result = await self.db.execute(
            select(Memory).where(Memory.tenant_id == self.tenant_id, Memory.lookup_key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.kt_soll = kt_soll
            existing.kt_haben = kt_haben
            existing.mwst_code = mwst_code
            existing.mwst_pct = mwst_pct
        else:
            self.db.add(Memory(
                tenant_id=self.tenant_id, lookup_key=key,
                kt_soll=kt_soll, kt_haben=kt_haben, mwst_code=mwst_code, mwst_pct=mwst_pct,
            ))

    async def log_correction(self, beschreibung: str, original: ClassificationResult,
                            corrected_soll: str, corrected_haben: str,
                            corrected_mwst_code: str = "", corrected_mwst_pct: str = ""):
        await self.save_to_memory(beschreibung, corrected_soll, corrected_haben, corrected_mwst_code, corrected_mwst_pct)
        if (original.kt_soll == corrected_soll and original.kt_haben == corrected_haben
                and original.mwst_code == corrected_mwst_code and original.mwst_pct == corrected_mwst_pct):
            return
        self.db.add(Correction(
            tenant_id=self.tenant_id, beschreibung=beschreibung,
            original_soll=original.kt_soll, original_haben=original.kt_haben,
            corrected_soll=corrected_soll, corrected_haben=corrected_haben,
            corrected_mwst_code=corrected_mwst_code, corrected_mwst_pct=corrected_mwst_pct,
        ))
        # ── NEW: Auto-retrain every N corrections ──
        count = await self.correction_count()
        if count > 0 and count % AUTO_RETRAIN_THRESHOLD == 0:
            await self.train_from_db()

    async def correction_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Correction.id)).where(Correction.tenant_id == self.tenant_id)
        )
        return result.scalar() or 0

    async def memory_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Memory.id)).where(Memory.tenant_id == self.tenant_id)
        )
        return result.scalar() or 0

    async def model_info(self) -> dict | None:
        result = await self.db.execute(
            select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "total_samples": row.total_samples, "classes": row.num_classes,
            "cv_accuracy": row.cv_accuracy, "train_accuracy": row.train_accuracy,
            "sklearn_version": row.sklearn_version, "updated_at": str(row.updated_at),
        }

    async def train_from_db(self) -> dict:
        """Train model from all training data + corrections for this tenant."""
        # Gather training rows
        result = await self.db.execute(
            select(TrainingRow).where(TrainingRow.tenant_id == self.tenant_id)
        )
        training_rows = result.scalars().all()

        # Gather corrections
        result = await self.db.execute(
            select(Correction).where(Correction.tenant_id == self.tenant_id)
        )
        corrections = result.scalars().all()

        rows = []
        for r in training_rows:
            rows.append({"Beschreibung": r.beschreibung, "KontoSoll": r.kt_soll})
        for c in corrections:
            rows.append({"Beschreibung": c.beschreibung, "KontoSoll": c.corrected_soll})

        if len(rows) < 5:
            return {"error": "Zu wenige Daten zum Trainieren (min. 5 Buchungen)"}

        df = pd.DataFrame(rows)
        df = df[df["Beschreibung"].notna() & (df["Beschreibung"] != "")]
        df = df[df["KontoSoll"].notna() & (df["KontoSoll"] != "")]

        if len(df) < 5:
            return {"error": "Zu wenige Daten zum Trainieren (min. 5 Buchungen)"}

        df["text_clean"] = df["Beschreibung"].apply(preprocess)

        X = df["text_clean"]
        y = df["KontoSoll"]


        pipeline = Pipeline([
            ("features", FeatureUnion([
                ("tfidf_char", TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(2, 5),
                    max_features=6000, sublinear_tf=True,
                )),
                ("tfidf_word", TfidfVectorizer(
                    analyzer="word", ngram_range=(1, 2),
                    max_features=4000, sublinear_tf=True,
                )),
            ])),
            ("clf", LogisticRegression(
                max_iter=1000, C=5.0,
                class_weight="balanced", solver="lbfgs",
            )),
        ])
       
        min_count = y.value_counts().min()
        n_folds = min(5, max(2, min_count))
        cv_acc = None
        if n_folds >= 2:
            try:
                cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
                scores = cross_val_score(pipeline, X, y, cv=cv, scoring="accuracy")
                cv_acc = float(scores.mean())
            except Exception:
                pass

        pipeline.fit(X, y)
        train_acc = float((pipeline.predict(X) == y).mean())
        self._model = pipeline

        import sklearn
        model_blob = pickle.dumps(pipeline)

        result = await self.db.execute(
            select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.model_blob = model_blob
            existing.total_samples = len(df)
            existing.num_classes = int(y.nunique())
            existing.cv_accuracy = cv_acc
            existing.train_accuracy = train_acc
            existing.sklearn_version = sklearn.__version__
        else:
            self.db.add(ClassifierModel(
                tenant_id=self.tenant_id, model_blob=model_blob,
                total_samples=len(df), num_classes=int(y.nunique()),
                cv_accuracy=cv_acc, train_accuracy=train_acc,
                sklearn_version=sklearn.__version__,
            ))

        return {
            "total_samples": len(df), "classes": int(y.nunique()),
            "cv_accuracy": cv_acc, "train_accuracy": train_acc,
        }

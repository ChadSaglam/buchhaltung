"""
Self-learning transaction classifier.

The classifier operates in 3 layers (priority order):
  1. Exact-match memory  — corrections the user made previously
  2. ML model            — TF-IDF + LogisticRegression trained on Banana data
  3. Keyword rules       — hardcoded fallback for when no model exists

Every user correction is logged to `data/corrections.jsonl`.
When corrections accumulate, the model retrains automatically in the background.
"""

from __future__ import annotations

import json
import os
import pickle
import re
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_PATH = DATA_DIR / "classifier_model.pkl"
CORRECTIONS_PATH = DATA_DIR / "corrections.jsonl"
MODEL_INFO_PATH = DATA_DIR / "model_info.json"
MEMORY_PATH = DATA_DIR / "memory.json"  # exact-match corrections cache

DATA_DIR.mkdir(exist_ok=True)

# ── Constants ────────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.35
AUTO_RETRAIN_THRESHOLD = 20  # retrain after N new corrections


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    kt_soll: str
    kt_haben: str
    mwst_code: str
    mwst_pct: str
    mwst_amount: float | str
    confidence: float = 0.0
    source: str = "Regeln"  # "Gedächtnis", "ML", "Regeln"


# ── Text preprocessing ──────────────────────────────────────────────────────

def preprocess(text: str) -> str:
    """Normalize description for classification."""
    text = text.lower().strip()
    text = re.sub(
        r"\b(januar|februar|märz|april|mai|juni|juli|august|"
        r"september|oktober|november|dezember)\b",
        "", text,
    )
    text = re.sub(r"\b(jan|feb|mär|apr|jun|jul|aug|sep|okt|nov|dez)\b", "", text)
    text = re.sub(r"\(\w+\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_memory_key(text: str) -> str:
    """Create a stable lookup key from description text."""
    return preprocess(text).strip()


# ── MwSt calculation ─────────────────────────────────────────────────────────

def calc_mwst(betrag: float, mwst_pct: str) -> float | str:
    """Calculate MwSt amount from gross amount and percentage string."""
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


# ── Keyword rules (fallback) ────────────────────────────────────────────────

CLASSIFICATION_RULES = [
    (["iso-trade", "iso-center", "isolier", "material", "baumate", "spenglerei",
      "werkzeug", "schrauben", "befestigung"], "4000", "1020", "M81", "8.10"),
    (["handelsware", "einkauf waren", "grosshandel"], "4200", "1020", "M81", "8.10"),
    (["tankstelle", "benzin", "fuel", "agrola", "socar energy", "diesel",
      "avia ", "shell ", "bp ", "eni "], "6210", "1020", "I81", "8.10"),
    (["strassenverkehr", "verkehrsamt", "mfk ", "motorfahrzeug"], "6230", "1020", "", ""),
    (["garage", "auto ", "autoreparatur", "reifenwechsel", "pneu ",
      "dorfgarage", "feldmann"], "6200", "1020", "I81", "8.10"),
    (["autoversicherung", "fahrzeugversicherung"], "6230", "1020", "", ""),
    (["leasing fahrzeug", "autoleasing"], "6260", "1020", "", ""),
    (["lohn", "gehalt", "salary", "aksoy", "nettolohn"], "5000", "1020", "", ""),
    (["ahv", "iv ", "eo ", "alv", "fak ", "sozialversicherung"], "5700", "1020", "", ""),
    (["pension", "bvg", "vorsorge", "2. säule"], "5700", "1020", "", ""),
    (["spesen mitarbeiter", "spesenabrechnung", "spesen"], "5800", "1020", "", ""),
    (["miete", "mietverwaltung", "immobilien", "nebenkosten gebäude"], "6000", "1020", "", ""),
    (["reparatur", "unterhalt", "wartung", "service "], "6100", "1020", "I81", "8.10"),
    (["chadev", "software", "it-", "hosting", "domain", "server",
      "microsoft", "google workspace", "adobe", "informatik"], "6570", "1020", "I81", "8.10"),
    (["versicherung", "insurance", "vaudoise", "mobiliar", "helvetia",
      "axa ", "zurich ", "generali"], "6300", "1020", "", ""),
    (["werbung", "marketing", "inserat", "google ads", "facebook ads",
      "flyer", "druckerei", "visitenkarte"], "6600", "1020", "I81", "8.10"),
    (["coop", "migros", "subway", "gastro", "brot", "zopf", "tchibo",
      "restaurant", "mcdonald", "pizza", "kebab", "essen", "lunch"], "6500", "1020", "", ""),
    (["büromaterial", "schreibwaren", "post ", "porto", "briefmarke"], "6500", "1020", "I81", "8.10"),
    (["telefon", "swisscom", "sunrise", "salt ", "handy"], "6500", "1020", "I81", "8.10"),
    (["obi ", "interdiscount", "baumarkt", "jumbo ", "hornbach"], "6500", "1020", "I81", "8.10"),
    (["dienstleistungspreis", "bankgebühr", "kontoführung", "saldo dienst",
      "kontospesen", "kartengebühr"], "6900", "1020", "", ""),
    (["strom", "elektrizität", "gas ", "heizung", "ewz", "energie"], "6400", "1020", "I81", "8.10"),
    (["steuer", "direkte steuer", "gemeinde", "kanton"], "8900", "1020", "", ""),
    (["rechtsanwalt", "anwalt", "beratung", "consulting", "treuhänder",
      "notar", "revision"], "4400", "1020", "I81", "8.10"),
    (["zahlung qr-rechnung", "zahlung qr"], "6500", "1020", "", ""),
    (["lastschrift"], "6500", "1020", "", ""),
    (["clearing", "gutschrift"], "1020", "3000", "V81", "-8.10"),
    (["zahlung erhalten", "einzahlung kunde"], "1020", "1100", "", ""),
]


# ── Classifier class ────────────────────────────────────────────────────────

class TransactionClassifier:
    """Self-learning transaction classifier with 3-layer fallback."""

    def __init__(self, konto_defaults: dict | None = None):
        self._model: Pipeline | None = None
        self._konto_defaults: dict = konto_defaults or {}
        self._memory: dict = {}  # key → {kt_soll, kt_haben, mwst_code, mwst_pct}
        self._corrections_since_train: int = 0
        self._lock = threading.Lock()
        self._load_model()
        self._load_memory()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_model(self):
        if MODEL_PATH.exists():
            with open(MODEL_PATH, "rb") as f:
                self._model = pickle.load(f)

    def _load_memory(self):
        if MEMORY_PATH.exists():
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                self._memory = json.load(f)

    def _save_memory(self):
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(self._memory, f, ensure_ascii=False, indent=2)

    def set_konto_defaults(self, defaults: dict):
        """Update the KontoSoll → default mapping."""
        self._konto_defaults = defaults

    @property
    def has_model(self) -> bool:
        return self._model is not None

    @property
    def correction_count(self) -> int:
        if not CORRECTIONS_PATH.exists():
            return 0
        with open(CORRECTIONS_PATH, "r") as f:
            return sum(1 for _ in f)

    @property
    def memory_count(self) -> int:
        return len(self._memory)

    @property
    def model_info(self) -> dict:
        if MODEL_INFO_PATH.exists():
            with open(MODEL_INFO_PATH, "r") as f:
                return json.load(f)
        return {}

    # ── Classification ───────────────────────────────────────────────────────

    def classify(self, beschreibung: str, is_credit: bool, betrag: float) -> ClassificationResult:
        """
        Classify a transaction through the 3-layer system:
          1. Exact-match memory (user corrections)
          2. ML model (if available and confident)
          3. Keyword rules (fallback)
        """
        # Credits are always income
        if is_credit:
            pct = 8.10
            return ClassificationResult(
                kt_soll="1020",
                kt_haben="3000",
                mwst_code="V81",
                mwst_pct="-8.10",
                mwst_amount=round(-betrag * pct / (100 + pct), 2),
                confidence=1.0,
                source="Regeln",
            )

        # Layer 1: Exact-match memory
        key = _make_memory_key(beschreibung)
        if key in self._memory:
            mem = self._memory[key]
            return ClassificationResult(
                kt_soll=mem["kt_soll"],
                kt_haben=mem["kt_haben"],
                mwst_code=mem.get("mwst_code", ""),
                mwst_pct=mem.get("mwst_pct", ""),
                mwst_amount=calc_mwst(betrag, mem.get("mwst_pct", "")),
                confidence=1.0,
                source="Gedächtnis",
            )

        # Layer 2: ML model
        if self._model is not None:
            clean = preprocess(beschreibung)
            proba = self._model.predict_proba([clean])[0]
            confidence = float(proba.max())
            predicted_soll = self._model.classes_[proba.argmax()]

            if confidence >= CONFIDENCE_THRESHOLD:
                defaults = self._konto_defaults.get(predicted_soll, {})
                kt_haben = defaults.get("KontoHaben", "1020")
                mwst_code = defaults.get("MwStCode", "")
                mwst_pct = defaults.get("MwStUStProz", "")

                return ClassificationResult(
                    kt_soll=predicted_soll,
                    kt_haben=kt_haben,
                    mwst_code=mwst_code,
                    mwst_pct=mwst_pct,
                    mwst_amount=calc_mwst(betrag, mwst_pct),
                    confidence=confidence,
                    source="ML",
                )

        # Layer 3: Keyword rules
        return self._classify_rules(beschreibung, betrag)

    def _classify_rules(self, beschreibung: str, betrag: float) -> ClassificationResult:
        desc_lower = beschreibung.lower()

        for keywords, account, gegen, code, pct in CLASSIFICATION_RULES:
            if any(kw in desc_lower for kw in keywords):
                return ClassificationResult(
                    kt_soll=account,
                    kt_haben=gegen,
                    mwst_code=code,
                    mwst_pct=pct,
                    mwst_amount=calc_mwst(betrag, pct),
                    confidence=0.0,
                    source="Regeln",
                )

        # Default fallback
        return ClassificationResult(
            kt_soll="6500",
            kt_haben="1020",
            mwst_code="",
            mwst_pct="",
            mwst_amount="",
            confidence=0.0,
            source="Regeln",
        )

    # ── Learning ─────────────────────────────────────────────────────────────

    def log_correction(
        self,
        beschreibung: str,
        original: ClassificationResult,
        corrected_soll: str,
        corrected_haben: str,
        corrected_mwst_code: str,
        corrected_mwst_pct: str,
    ):
        """
        Log a user correction and update the memory cache.
        Called when the user changes an account assignment in the editor.
        """
        # Only log if something actually changed
        if (
            original.kt_soll == corrected_soll
            and original.kt_haben == corrected_haben
            and original.mwst_code == corrected_mwst_code
            and original.mwst_pct == corrected_mwst_pct
        ):
            return

        # Update in-memory exact-match cache
        key = _make_memory_key(beschreibung)
        self._memory[key] = {
            "kt_soll": corrected_soll,
            "kt_haben": corrected_haben,
            "mwst_code": corrected_mwst_code,
            "mwst_pct": corrected_mwst_pct,
        }
        self._save_memory()

        # Append to corrections log
        entry = {
            "timestamp": datetime.now().isoformat(),
            "beschreibung": beschreibung,
            "original_soll": original.kt_soll,
            "original_haben": original.kt_haben,
            "corrected_soll": corrected_soll,
            "corrected_haben": corrected_haben,
            "corrected_mwst_code": corrected_mwst_code,
            "corrected_mwst_pct": corrected_mwst_pct,
        }
        with open(CORRECTIONS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._corrections_since_train += 1

    def should_retrain(self) -> bool:
        """Check if enough corrections have accumulated to justify retraining."""
        return self._corrections_since_train >= AUTO_RETRAIN_THRESHOLD

    # ── Training ─────────────────────────────────────────────────────────────

    def train_from_banana_xml(self, xls_path: str) -> dict:
        """
        Train the classifier from a Banana XML-XLS export.
        Returns a dict with training stats.
        """
        import xml.etree.ElementTree as ET

        tree = ET.parse(xls_path)
        root = tree.getroot()
        ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

        ws = root.findall(".//ss:Worksheet", ns)[0]
        table = ws.find("ss:Table", ns)
        rows = table.findall("ss:Row", ns)

        # Parse field names from row 4
        field_row = rows[4]
        cells = field_row.findall("ss:Cell", ns)
        field_names = []
        for cell in cells:
            data = cell.find("ss:Data", ns)
            field_names.append(data.text if data is not None else "")

        # Parse data rows
        all_data = []
        for row in rows[5:]:
            cells = row.findall("ss:Cell", ns)
            row_data = {}
            col_idx = 0
            for cell in cells:
                idx_attr = cell.attrib.get(
                    "{urn:schemas-microsoft-com:office:spreadsheet}Index"
                )
                if idx_attr:
                    col_idx = int(idx_attr) - 1
                data = cell.find("ss:Data", ns)
                text = data.text if data is not None else ""
                if col_idx < len(field_names):
                    row_data[field_names[col_idx]] = text
                col_idx += 1
            all_data.append(row_data)

        df = pd.DataFrame(all_data)
        return self._train_from_df(df)

    def train_from_corrections(self) -> dict | None:
        """Retrain the model by merging corrections into the existing training data."""
        if not CORRECTIONS_PATH.exists():
            return None

        corrections = []
        with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    corrections.append(json.loads(line))

        if not corrections:
            return None

        # Build a DataFrame from corrections
        rows = []
        for c in corrections:
            rows.append({
                "Beschreibung": c["beschreibung"],
                "KontoSoll": c["corrected_soll"],
                "KontoHaben": c["corrected_haben"],
                "MwStCode": c.get("corrected_mwst_code", ""),
                "MwStUStProz": c.get("corrected_mwst_pct", ""),
            })

        correction_df = pd.DataFrame(rows)

        # If we have an existing training set, merge
        training_csv = DATA_DIR / "training_data.csv"
        if training_csv.exists():
            existing = pd.read_csv(training_csv, dtype=str)
            # Ensure columns exist
            for col in ["Beschreibung", "KontoSoll", "KontoHaben", "MwStCode", "MwStUStProz"]:
                if col not in existing.columns:
                    existing[col] = ""
            combined = pd.concat([
                existing[["Beschreibung", "KontoSoll", "KontoHaben", "MwStCode", "MwStUStProz"]],
                correction_df,
            ], ignore_index=True)
        else:
            combined = correction_df

        return self._train_from_prepared_df(combined)

    def _train_from_df(self, df: pd.DataFrame) -> dict:
        """Train from a raw Banana-format DataFrame."""
        # Clean
        df = df[df["Datum"].notna() & df["Datum"].str.contains(r"\d{4}", na=False)].copy()
        df = df[~df["KontoSoll"].isin(["AccountDebit", "String", ""])].copy()
        df = df[df["Beschreibung"].notna() & (df["Beschreibung"] != "")].copy()
        df["MwStCode"] = df["MwStCode"].fillna("")
        df["MwStUStProz"] = df["MwStUStProz"].fillna("")

        # Save clean training data for future retraining
        df[["Beschreibung", "KontoSoll", "KontoHaben", "KontoSollBeschr", "KontoHabenBeschr",
            "MwStCode", "MwStUStProz"]].to_csv(
            DATA_DIR / "training_data.csv", index=False
        )

        # Build Kontenplan
        from .kontenplan import KontenplanManager
        kp_mgr = KontenplanManager()
        for _, row in df.iterrows():
            if row.get("KontoSoll") and row.get("KontoSollBeschr"):
                kp_mgr.set(row["KontoSoll"], row["KontoSollBeschr"])
            if row.get("KontoHaben") and row.get("KontoHabenBeschr"):
                kp_mgr.set(row["KontoHaben"], row["KontoHabenBeschr"])
        kp_mgr.save()

        # Build default mappings
        defaults = {}
        for konto_soll, group in df.groupby("KontoSoll"):
            haben_mode = group["KontoHaben"].mode()
            mwst_mode = group["MwStCode"].mode()
            rate_mode = group["MwStUStProz"].mode()
            defaults[konto_soll] = {
                "KontoHaben": haben_mode.iloc[0] if len(haben_mode) > 0 else "1020",
                "MwStCode": mwst_mode.iloc[0] if len(mwst_mode) > 0 else "",
                "MwStUStProz": rate_mode.iloc[0] if len(rate_mode) > 0 else "",
            }
        from .kontenplan import save_konto_defaults
        save_konto_defaults(defaults)
        self._konto_defaults = defaults

        prepared = df[["Beschreibung", "KontoSoll", "KontoHaben", "MwStCode", "MwStUStProz"]].copy()
        return self._train_from_prepared_df(prepared)

    def _train_from_prepared_df(self, df: pd.DataFrame) -> dict:
        """Train the ML pipeline on a prepared DataFrame with standard columns."""
        df = df[df["Beschreibung"].notna() & (df["Beschreibung"] != "")].copy()
        df = df[df["KontoSoll"].notna() & (df["KontoSoll"] != "")].copy()
        df["MwStCode"] = df["MwStCode"].fillna("")

        if len(df) < 5:
            return {"error": "Zu wenige Daten zum Trainieren (min. 5 Buchungen)"}

        df["text_clean"] = df["Beschreibung"].apply(preprocess)
        X = df["text_clean"]
        y = df["KontoSoll"]

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                max_features=5000,
                sublinear_tf=True,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=5.0,
                class_weight="balanced",
                solver="lbfgs",
            )),
        ])

        # Cross-validation
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

        # Train final model
        pipeline.fit(X, y)
        train_acc = float((pipeline.predict(X) == y).mean())

        # Save
        with self._lock:
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(pipeline, f)
            self._model = pipeline

        info = {
            "total_samples": len(df),
            "classes": int(y.nunique()),
            "cv_accuracy": cv_acc,
            "train_accuracy": train_acc,
            "trained_at": datetime.now().isoformat(),
        }
        with open(MODEL_INFO_PATH, "w") as f:
            json.dump(info, f, indent=2)

        self._corrections_since_train = 0

        return info

    # ── Corrections history ──────────────────────────────────────────────────

    def get_corrections(self, limit: int = 100) -> list[dict]:
        """Return the most recent corrections."""
        if not CORRECTIONS_PATH.exists():
            return []
        corrections = []
        with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    corrections.append(json.loads(line))
        return corrections[-limit:]

    def clear_corrections(self):
        """Clear the corrections log."""
        if CORRECTIONS_PATH.exists():
            CORRECTIONS_PATH.unlink()
        self._corrections_since_train = 0

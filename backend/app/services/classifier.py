from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accuracy_history import AccuracyHistory
from app.models.booking import Booking
from app.models.classifier_model import ClassifierModel
from app.models.correction import Correction
from app.models.kontenplan import KontoDefault
from app.models.memory import Memory
from app.models.training_data import TrainingRow
from app.services.export import round_chf
from app.services.model_blob import UntrustedModelBlob, pack, sha256_hex, unpack

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.45
AUTO_RETRAIN_THRESHOLD = 20
RULE_CONFIDENCE = 0.72
DEFAULT_RULE_CONFIDENCE = 0.35
# Amount memory (Betrag-Gedächtnis): a bank line without a counterparty
# ("E-BANKING-AUFTRAG 770.60") is still recognisable by its amount when the
# tenant booked that exact amount before, consistently to one account.
AMOUNT_MIN_HITS = 2
AMOUNT_MIN_SHARE = 0.6
AMOUNT_MAX_CONFIDENCE = 0.92

ZU_WENIG_DATEN = "Zu wenige Daten zum Trainieren (min. 5 Buchungen)"
EIN_EINZIGES_KONTO = (
    "Alle Buchungen gehen auf dasselbe Konto ({konto}). "
    "Das Modell lernt erst, wenn mindestens zwei verschiedene Konten vorkommen."
)


_MONTH_RE = re.compile(
    r"\b(?:januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember"
    r"|jan|feb|mär|mrz|apr|jun|jul|aug|sep|sept|okt|nov|dez)\b\.?"
)


def preprocess(text: str) -> str:
    """Normalise a booking text for the ML features and the memory key.

    Lower-case, drop month names/abbreviations (whole words only — B-04: a bare
    substring match turned "E-Mail" into "e-l"), drop digits, collapse blanks.
    Changing this function changes every ``memory.lookup_key``; ship a data
    migration alongside (see ``alembic/versions/*_rederive_memory_lookup_keys.py``).
    """
    text = (text or "").lower().strip()
    text = _MONTH_RE.sub("", text)
    text = re.sub(r"\d", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_memory_key(text: str) -> str:
    return preprocess(text).strip()


def key_ist_brauchbar(key: str) -> bool:
    """Whether a memory key identifies anything (B-56).

    ``preprocess`` removes digits and month names but not punctuation, so
    ``"2024 03"`` reduces to ``""`` and ``"31.12."`` to ``".."`` — two "keys"
    that carry no information and match every other description that reduces to
    the same thing. One such row silently classifies a whole class of bank lines
    to whatever it was taught.

    Deliberately a separate check rather than a change to ``make_memory_key``:
    that function's output is stored, and migration ``4c7e2a91b0d3`` already had
    to re-derive every key once. Changing it again would invalidate every
    tenant's memory table.
    """
    return any(ch.isalnum() for ch in key)


# Swiss VAT rate -> Vorsteuer code (Banana). Current rates first, pre-2024 rates kept
# for old receipts. The rate printed on the receipt is the truth; codes follow it.
VAT_CODE_BY_RATE: dict[float, str] = {8.1: "I81", 2.6: "I26", 3.8: "I38", 7.7: "I77", 2.5: "I25", 3.7: "I37"}


#: Names that were in `CLASSIFICATION_RULES` and must not come back (B-56).
#: Each one is a specific company or person, so it classified for tenants who
#: have no relationship with them at all. `tests/test_parser_hygiene.py` holds
#: this list against the rules.
VERBOTENE_KEYWORDS: frozenset[str] = frozenset(
    {
        "iso-trade",  # one customer's insulation supplier
        "iso-center",  # the same
        "spenglerei",  # one customer's trade, not a supplier category
        "dorfgarage",  # a named garage
        "feldmann",  # a surname
        "aksoy",  # a surname — and it booked to 5000 Lohn
        "chadev",  # our own company
    }
)


def vat_code_for(rate: float, current_code: str = "") -> tuple[str, str] | None:
    """(mwst_pct, mwst_code) for a detected VAT rate, or None when the rate is unknown.

    A code the classifier already chose is kept when it belongs to the same rate
    (``V81``/``M81`` stay), otherwise it is replaced — code and rate must agree.
    """
    code = VAT_CODE_BY_RATE.get(round(float(rate), 1))
    if not code:
        return None
    if current_code and current_code.endswith(code[1:]):
        code = current_code
    return f"{round(float(rate), 1):.2f}", code


def calc_mwst(betrag: float, mwst_pct: str) -> float | str:
    """Tax portion of a gross amount, rounded half-up to the Rappen (see ``round_chf``).

    A negative rate (Umsatzsteuer, e.g. ``"-8.10"``) flips the sign; a
    negative gross keeps its sign. Returns ``""`` when nothing can be computed.
    """
    if not mwst_pct or not betrag:
        return ""
    try:
        pct_val = abs(float(mwst_pct))
        mwst_val = float(round_chf(float(betrag) * pct_val / (100 + pct_val)))
        if float(mwst_pct) < 0:
            mwst_val = -mwst_val
        return mwst_val
    except (ValueError, TypeError):
        return ""


#: Keyword rules shared by **every tenant of every deployment** (B-56).
#:
#: Which is the whole constraint: a keyword here classifies for a customer who
#: has never heard of it. So only *generic* trade vocabulary belongs — "benzin",
#: "werkzeug", "versicherung" — never the name of one customer's supplier.
#:
#: Five names were in here and are gone (`VERBOTENE_KEYWORDS` below keeps them
#: out). The worst was **"aksoy"** in the payroll rule: a surname, which booked
#: any invoice from a supplier of that name to 5000 Lohn for every tenant in the
#: world. A tenant's own suppliers are learned per tenant, automatically, the
#: first time they correct one (`save_to_memory`) — which is both more accurate
#: and the mechanism that already exists.
CLASSIFICATION_RULES: list[tuple[list[str], str, str, str, str]] = [
    (
        [
            "isolier",
            "material",
            "baumate",
            "werkzeug",
            "schrauben",
            "befestigung",
        ],
        "4000",
        "1020",
        "M81",
        "8.10",
    ),
    (["handelsware", "einkauf waren", "grosshandel"], "4200", "1020", "M81", "8.10"),
    (
        ["tankstelle", "benzin", "fuel", "agrola", "landi", "socar energy", "diesel", "avia ", "shell ", "bp ", "eni "],
        "6210",
        "1020",
        "I81",
        "8.10",
    ),
    (["strassenverkehr", "verkehrsamt", "mfk ", "motorfahrzeug"], "6230", "1020", "", ""),
    (
        ["garage", "auto ", "autoreparatur", "reifenwechsel", "pneu "],
        "6200",
        "1020",
        "I81",
        "8.10",
    ),
    (["autoversicherung", "fahrzeugversicherung"], "6230", "1020", "", ""),
    (["leasing fahrzeug", "autoleasing"], "6260", "1020", "", ""),
    (["lohn", "gehalt", "salary", "nettolohn"], "5000", "1020", "", ""),
    (["ahv", "iv ", "eo ", "alv", "fak ", "sozialversicherung"], "5700", "1020", "", ""),
    (["pension", "bvg", "vorsorge", "2. säule"], "5700", "1020", "", ""),
    (["spesen mitarbeiter", "spesenabrechnung", "spesen"], "5800", "1020", "", ""),
    (["miete", "mietverwaltung", "immobilien", "nebenkosten gebäude"], "6000", "1020", "", ""),
    (["reparatur", "unterhalt", "wartung", "service "], "6100", "1020", "I81", "8.10"),
    (
        [
            "software",
            "it-",
            "hosting",
            "domain",
            "server",
            "microsoft",
            "google workspace",
            "adobe",
            "informatik",
        ],
        "6570",
        "1020",
        "I81",
        "8.10",
    ),
    (
        ["versicherung", "insurance", "vaudoise", "mobiliar", "helvetia", "axa ", "zurich ", "generali"],
        "6300",
        "1020",
        "",
        "",
    ),
    (
        ["werbung", "marketing", "inserat", "google ads", "facebook ads", "flyer", "druckerei", "visitenkarte"],
        "6600",
        "1020",
        "I81",
        "8.10",
    ),
    (
        [
            "coop",
            "migros",
            "subway",
            "gastro",
            "brot",
            "zopf",
            "tchibo",
            "restaurant",
            "mcdonald",
            "pizza",
            "kebab",
            "essen",
            "lunch",
        ],
        "6500",
        "1020",
        "",
        "",
    ),
    (["büromaterial", "schreibwaren", "post ", "porto", "briefmarke"], "6500", "1020", "I81", "8.10"),
    (["telefon", "swisscom", "sunrise", "salt ", "handy"], "6500", "1020", "I81", "8.10"),
    (["obi ", "interdiscount", "baumarkt", "jumbo ", "hornbach"], "6500", "1020", "I81", "8.10"),
    (
        ["dienstleistungspreis", "bankgebühr", "kontoführung", "saldo dienst", "kontospesen", "kartengebühr"],
        "6900",
        "1020",
        "",
        "",
    ),
    (["strom", "elektrizität", "gas ", "heizung", "ewz", "energie"], "6400", "1020", "I81", "8.10"),
    (["steuer", "direkte steuer", "gemeinde", "kanton"], "8900", "1020", "", ""),
    (
        ["rechtsanwalt", "anwalt", "beratung", "consulting", "treuhänder", "notar", "revision"],
        "4400",
        "1020",
        "I81",
        "8.10",
    ),
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
    # Description the tenant used for the same amount before (amount memory);
    # empty when there is nothing better than the bank text.
    beschreibung_vorschlag: str = ""


AmountRow = tuple[str, str, str, str, str]  # beschreibung, kt_soll, kt_haben, mwst_code, mwst_pct


def amount_candidate(rows: list[AmountRow], betrag: float) -> ClassificationResult | None:
    """Classification from earlier bookings with the same amount, or None.

    Needs at least ``AMOUNT_MIN_HITS`` earlier bookings of which a share of
    ``AMOUNT_MIN_SHARE`` agree on the account pair. Confidence grows with the
    number of agreeing bookings and shrinks with disagreement: 12/12 → 0.92,
    2/2 → 0.67, 11/18 → 0.56 — the last one is shown as "unsicher", on purpose.
    """
    if len(rows) < AMOUNT_MIN_HITS:
        return None
    pairs = Counter((r[1], r[2]) for r in rows if r[1])
    if not pairs:
        return None
    (kt_soll, kt_haben), hits = pairs.most_common(1)[0]
    share = hits / len(rows)
    if hits < AMOUNT_MIN_HITS or share < AMOUNT_MIN_SHARE:
        return None
    agreeing = [r for r in rows if (r[1], r[2]) == (kt_soll, kt_haben)]
    mwst_code, mwst_pct = Counter((r[3] or "", r[4] or "") for r in agreeing).most_common(1)[0][0]
    descriptions = Counter(r[0].strip() for r in agreeing if r[0] and r[0].strip())
    vorschlag = descriptions.most_common(1)[0][0] if descriptions else ""
    confidence = round(min(AMOUNT_MAX_CONFIDENCE, 0.55 + 0.06 * hits) * share, 3)
    return ClassificationResult(
        kt_soll=kt_soll,
        kt_haben=kt_haben,
        mwst_code=mwst_code,
        mwst_pct=mwst_pct,
        mwst_amount=calc_mwst(betrag, mwst_pct),
        confidence=confidence,
        source="Betrag",
        beschreibung_vorschlag=vorschlag,
    )


FittedModel = tuple[Pipeline, int, int, float | None, float]  # pipeline, rows, classes, cv_acc, train_acc


class TrainingDatenFehlen(ValueError):
    """The training set cannot produce a model, and it is the data's fault, not ours.

    Separate from an ordinary exception because the difference decides the status
    code: this is a 400 the user can act on ("book a second kind of expense"),
    everything else is a 500 (B-57).
    """


def fit_pipeline(rows: list[dict[str, str]]) -> FittedModel:
    """Build and fit the TF-IDF + LogisticRegression pipeline.

    Raises :class:`TrainingDatenFehlen` when the rows cannot train anything.
    Pure CPU, no I/O — safe to run in a worker thread.
    """
    df = pd.DataFrame(rows)
    if df.empty:
        raise TrainingDatenFehlen(ZU_WENIG_DATEN)
    df = df[df["Beschreibung"].notna() & (df["Beschreibung"] != "")]
    df = df[df["KontoSoll"].notna() & (df["KontoSoll"] != "")]
    if len(df) < 5:
        raise TrainingDatenFehlen(ZU_WENIG_DATEN)
    if df["KontoSoll"].nunique() < 2:
        # scikit-learn raises "This solver needs samples of at least 2 classes"
        # from inside `fit`, which reached the user as a 500. A new tenant whose
        # first receipts all go to one account hits this on their first retrain —
        # it is the most ordinary state there is, not a server fault.
        raise TrainingDatenFehlen(EIN_EINZIGES_KONTO.format(konto=df["KontoSoll"].iloc[0]))

    df["text_clean"] = df["Beschreibung"].apply(preprocess)
    X = df["text_clean"]
    y = df["KontoSoll"]

    pipeline = Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "tfidf_char",
                            TfidfVectorizer(
                                analyzer="char_wb", ngram_range=(2, 5), max_features=6000, sublinear_tf=True
                            ),
                        ),
                        (
                            "tfidf_word",
                            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=4000, sublinear_tf=True),
                        ),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=1000, C=5.0, class_weight="balanced", solver="lbfgs")),
        ]
    )

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
    return pipeline, len(df), int(y.nunique()), cv_acc, train_acc


#: One unpickled pipeline per (tenant, model version) per process (B-27).
#:
#: ``self._model`` only ever helped inside a single request: every request built
#: a new ``TenantClassifier``, pulled the blob out of the database again and
#: unpickled a scikit-learn pipeline to answer one prediction.
#:
#: The key carries ``model_sha256``, so a retrain (new blob, new digest, new
#: ``updated_at``) misses the cache by construction — there is no invalidation
#: call to forget. **A row without a digest is never cached**: that is the
#: pre-B-34 shape, where the only thing standing between the blob and
#: ``pickle.loads`` is the signature check in ``model_row_is_trusted``, and that
#: check has to run against the bytes every single time.
#:
#: The cached ``Pipeline`` is shared by every request in the process. Predicting
#: does not mutate a fitted pipeline; nothing here may start.
_MODEL_CACHE: OrderedDict[int, tuple[str, Pipeline]] = OrderedDict()
#: Bounded so a busy multi-tenant process cannot hold every model it ever served.
_MODEL_CACHE_MAX = 32


def _model_version(updated_at: object, sha256: str | None) -> str | None:
    """The cache key, or None when this row must not be cached."""
    return f"{updated_at}:{sha256}" if sha256 else None


def _cache_get(tenant_id: int, version: str | None) -> Pipeline | None:
    if version is None:
        return None
    hit = _MODEL_CACHE.get(tenant_id)
    if hit is None or hit[0] != version:
        return None
    _MODEL_CACHE.move_to_end(tenant_id)
    return hit[1]


def _cache_put(tenant_id: int, version: str | None, model: Pipeline) -> None:
    if version is None:
        return
    _MODEL_CACHE[tenant_id] = (version, model)
    _MODEL_CACHE.move_to_end(tenant_id)
    while len(_MODEL_CACHE) > _MODEL_CACHE_MAX:
        _MODEL_CACHE.popitem(last=False)


def model_row_is_trusted(row: ClassifierModel | None) -> bool:
    """Signed by this installation and — when the fingerprint exists — unchanged since written."""
    if row is None or not row.model_blob:
        return False
    if row.model_sha256 and sha256_hex(row.model_blob) != row.model_sha256:
        return False
    from app.services.model_blob import is_trusted

    return is_trusted(row.model_blob)


class TenantClassifier:
    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db
        self._model: Pipeline | None = None
        self._konto_defaults: dict[str, dict] | None = None

    async def _load_model(self) -> Pipeline | None:
        if self._model is not None:
            return self._model
        # B-27: read the two small columns first. On a hit that is the whole
        # database traffic — the blob (hundreds of KB) is never transferred and
        # never unpickled.
        head = (
            await self.db.execute(
                select(ClassifierModel.updated_at, ClassifierModel.model_sha256).where(
                    ClassifierModel.tenant_id == self.tenant_id
                )
            )
        ).one_or_none()
        if head is None:
            return None
        version = _model_version(head[0], head[1])
        cached = _cache_get(self.tenant_id, version)
        if cached is not None:
            self._model = cached
            return self._model

        result = await self.db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id))
        row = result.scalar_one_or_none()
        if row:
            if not model_row_is_trusted(row):
                # Unsigned (pre-B-32), foreign, or altered since it was written (B-34):
                # never unpickle it. The classifier falls through to memory/rules until retraining.
                logger.warning("[CLASSIFIER] tenant=%s: model blob is not trusted, ignoring it", self.tenant_id)
                return None
            try:
                self._model = unpack(row.model_blob)
                _cache_put(self.tenant_id, version, self._model)
            except UntrustedModelBlob:
                logger.warning("[CLASSIFIER] tenant=%s: model blob is not signed, ignoring it", self.tenant_id)
        return self._model

    async def _load_konto_defaults(self) -> dict[str, dict]:
        if self._konto_defaults is not None:
            return self._konto_defaults
        result = await self.db.execute(select(KontoDefault).where(KontoDefault.tenant_id == self.tenant_id))
        self._konto_defaults = {
            r.konto_soll: {
                "KontoHaben": r.konto_haben,
                "MwStCode": r.mwst_code,
                "MwStUStProz": r.mwst_pct,
            }
            for r in result.scalars().all()
        }
        return self._konto_defaults

    async def _amount_history(self, betrag: float) -> list[AmountRow]:
        """Earlier bookings of this tenant with the same gross amount (± half a Rappen)."""
        try:
            amount = round(abs(float(betrag)), 2)
        except (TypeError, ValueError):
            return []
        if not amount or not (amount < float("inf")):
            return []
        lo, hi = amount - 0.005, amount + 0.005
        rows: list[AmountRow] = []
        result = await self.db.execute(
            select(
                TrainingRow.beschreibung,
                TrainingRow.kt_soll,
                TrainingRow.kt_haben,
                TrainingRow.mwst_code,
                TrainingRow.mwst_pct,
            ).where(TrainingRow.tenant_id == self.tenant_id, TrainingRow.betrag.between(lo, hi))
        )
        rows.extend(tuple(r) for r in result.all())
        result = await self.db.execute(
            select(Booking.beschreibung, Booking.kt_soll, Booking.kt_haben, Booking.mwst_code, Booking.mwst_pct).where(
                Booking.tenant_id == self.tenant_id,
                Booking.betrag.between(lo, hi),
                Booking.kt_soll != "",
            )
        )
        rows.extend(tuple(r) for r in result.all())
        return rows

    async def classify(self, beschreibung: str, is_credit: bool, betrag: float) -> ClassificationResult:
        by_amount = amount_candidate(await self._amount_history(betrag), betrag)

        if is_credit:
            # The revenue default stays at 1.0; the amount memory only overrides it when the
            # tenant consistently booked this amount elsewhere (e.g. 1100 Debitoren). When it
            # agrees, it just lends the customer's name — a 67 % on a sure line was a regression.
            if by_amount and by_amount.confidence >= 0.6 and by_amount.kt_soll != "1020":
                return by_amount
            pct = 8.10
            return ClassificationResult(
                kt_soll="1020",
                kt_haben="3000",
                mwst_code="V81",
                mwst_pct="-8.10",
                mwst_amount=float(round_chf(-betrag * pct / (100 + pct))),
                confidence=1.0,
                source="Regeln",
                beschreibung_vorschlag=by_amount.beschreibung_vorschlag if by_amount else "",
            )

        key = make_memory_key(beschreibung)
        # A key with nothing in it is not a key (B-56). `save_to_memory` refuses
        # to write one now, but a row written before that fix would still match —
        # so the *lookup* refuses too, and the old row becomes harmless without a
        # migration over every tenant's memory table.
        result = await self.db.execute(
            select(Memory).where(Memory.tenant_id == self.tenant_id, Memory.lookup_key == key)
        )
        mem = result.scalar_one_or_none() if key_ist_brauchbar(key) else None
        if mem:
            return ClassificationResult(
                kt_soll=mem.kt_soll,
                kt_haben=mem.kt_haben,
                mwst_code=mem.mwst_code,
                mwst_pct=mem.mwst_pct,
                mwst_amount=calc_mwst(betrag, mem.mwst_pct),
                confidence=1.0,
                source="Gedächtnis",
            )

        # Three candidates, most confident wins; ties go amount → rules → ML.
        # A keyword rule (≥ 0.72) therefore beats a hesitant model (0.45–0.71):
        # the model used to turn "SALDO DIENSTLEISTUNGSPREIS…" into revenue at 48 %.
        candidates: list[ClassificationResult] = []
        if by_amount:
            candidates.append(by_amount)
        candidates.append(self._classify_rules(beschreibung, betrag))

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
                candidates.append(
                    ClassificationResult(
                        kt_soll=predicted_soll,
                        kt_haben=kt_haben,
                        mwst_code=mwst_code,
                        mwst_pct=mwst_pct,
                        mwst_amount=calc_mwst(betrag, mwst_pct),
                        confidence=confidence,
                        source="ML",
                    )
                )

        best = max(candidates, key=lambda c: c.confidence)  # max() keeps the first of equals
        # The remembered description only makes sense when it belongs to the account we
        # chose: "BANCOMAT → 5820 (ML)" must not be captioned "Swiss Life" (the 5720 memory).
        if by_amount and best is not by_amount and best.kt_soll == by_amount.kt_soll:
            best.beschreibung_vorschlag = by_amount.beschreibung_vorschlag
        return best

    def _classify_rules(self, beschreibung: str, betrag: float) -> ClassificationResult:
        desc_lower = (beschreibung or "").lower()
        for keywords, account, gegen, code, pct in CLASSIFICATION_RULES:
            matched = [kw for kw in keywords if kw in desc_lower]
            if matched:
                confidence = min(0.95, RULE_CONFIDENCE + (len(matched) - 1) * 0.08)
                return ClassificationResult(
                    kt_soll=account,
                    kt_haben=gegen,
                    mwst_code=code,
                    mwst_pct=pct,
                    mwst_amount=calc_mwst(betrag, pct),
                    confidence=confidence,
                    source="Regeln",
                )
        return ClassificationResult(
            kt_soll="6500",
            kt_haben="1020",
            mwst_code="",
            mwst_pct="",
            mwst_amount="",
            confidence=DEFAULT_RULE_CONFIDENCE,
            source="Regeln",
        )

    async def save_to_memory(
        self,
        beschreibung: str,
        kt_soll: str,
        kt_haben: str,
        mwst_code: str = "",
        mwst_pct: str = "",
    ):
        key = make_memory_key(beschreibung)
        if not key_ist_brauchbar(key):
            return
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
            self.db.add(
                Memory(
                    tenant_id=self.tenant_id,
                    lookup_key=key,
                    kt_soll=kt_soll,
                    kt_haben=kt_haben,
                    mwst_code=mwst_code,
                    mwst_pct=mwst_pct,
                )
            )

    async def log_correction(
        self,
        beschreibung: str,
        original: ClassificationResult,
        corrected_soll: str,
        corrected_haben: str,
        corrected_mwst_code: str = "",
        corrected_mwst_pct: str = "",
    ):
        await self.save_to_memory(
            beschreibung,
            corrected_soll,
            corrected_haben,
            corrected_mwst_code,
            corrected_mwst_pct,
        )
        if (
            original.kt_soll == corrected_soll
            and original.kt_haben == corrected_haben
            and original.mwst_code == corrected_mwst_code
            and original.mwst_pct == corrected_mwst_pct
        ):
            return

        self.db.add(
            Correction(
                tenant_id=self.tenant_id,
                beschreibung=beschreibung,
                original_soll=original.kt_soll,
                original_haben=original.kt_haben,
                corrected_soll=corrected_soll,
                corrected_haben=corrected_haben,
                corrected_mwst_code=corrected_mwst_code,
                corrected_mwst_pct=corrected_mwst_pct,
            )
        )
        count = await self.correction_count()
        if count > 0 and count % AUTO_RETRAIN_THRESHOLD == 0:
            from app.services.training_worker import enqueue_training

            # Queued in this session; the worker (in-API or separate process)
            # picks it up after the request commits.
            await enqueue_training(self.db, self.tenant_id)

    async def correction_count(self) -> int:
        result = await self.db.execute(select(func.count(Correction.id)).where(Correction.tenant_id == self.tenant_id))
        return result.scalar() or 0

    async def memory_count(self) -> int:
        result = await self.db.execute(select(func.count(Memory.id)).where(Memory.tenant_id == self.tenant_id))
        return result.scalar() or 0

    async def model_info(self) -> dict | None:
        result = await self.db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "total_samples": row.total_samples,
            "classes": row.num_classes,
            "cv_accuracy": row.cv_accuracy,
            "train_accuracy": row.train_accuracy,
            "sklearn_version": row.sklearn_version,
            "updated_at": str(row.updated_at),
        }

    async def train_from_db(self) -> dict:
        result = await self.db.execute(select(TrainingRow).where(TrainingRow.tenant_id == self.tenant_id))
        training_rows = result.scalars().all()

        result = await self.db.execute(select(Correction).where(Correction.tenant_id == self.tenant_id))
        corrections = result.scalars().all()

        rows = []
        for r in training_rows:
            rows.append({"Beschreibung": r.beschreibung, "KontoSoll": r.kt_soll})
        for c in corrections:
            rows.append({"Beschreibung": c.beschreibung, "KontoSoll": c.corrected_soll})

        if len(rows) < 5:
            return {"error": ZU_WENIG_DATEN}

        # sklearn fit + cross-validation are CPU-bound and take seconds on a few
        # thousand rows; run them in a worker thread so the event loop keeps
        # serving requests (B-49). Nothing in there touches the session.
        try:
            fitted = await asyncio.to_thread(fit_pipeline, rows)
        except TrainingDatenFehlen as exc:
            return {"error": str(exc)}
        pipeline, n_rows, n_classes, cv_acc, train_acc = fitted
        self._model = pipeline
        model_blob = pack(pipeline)

        import sklearn

        result = await self.db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == self.tenant_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.model_blob = model_blob
            existing.model_sha256 = sha256_hex(model_blob)
            existing.total_samples = n_rows
            existing.num_classes = n_classes
            existing.cv_accuracy = cv_acc
            existing.train_accuracy = train_acc
            existing.sklearn_version = sklearn.__version__
        else:
            self.db.add(
                ClassifierModel(
                    tenant_id=self.tenant_id,
                    model_blob=model_blob,
                    model_sha256=sha256_hex(model_blob),
                    total_samples=n_rows,
                    num_classes=n_classes,
                    cv_accuracy=cv_acc,
                    train_accuracy=train_acc,
                    sklearn_version=sklearn.__version__,
                )
            )

        self.db.add(
            AccuracyHistory(
                tenant_id=self.tenant_id,
                cv_accuracy=cv_acc,
                train_accuracy=train_acc,
                total_samples=n_rows,
                num_classes=n_classes,
                sklearn_version=sklearn.__version__,
            )
        )

        return {
            "total_samples": n_rows,
            "classes": n_classes,
            "cv_accuracy": cv_acc,
            "train_accuracy": train_acc,
        }

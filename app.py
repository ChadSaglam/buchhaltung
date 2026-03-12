"""
📄 RDS Buchhaltung — Self-Learning Swiss KMU Bookkeeping

Main entry point. Uses Streamlit's native multi-page layout via pages/ folder.
Initializes shared state (classifier, Kontenplan) once at startup.
"""

import streamlit as st
from datetime import datetime

from core.kontenplan import KontenplanManager, load_konto_defaults
from core.classifier import TransactionClassifier
from core.database import DatabaseManager

st.set_page_config(
    page_title="RDS Buchhaltung",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal CSS — light theme ─────────────────────────────────────────────────
st.markdown("""
<style>
    /* Metric cards */
    div[data-testid="stMetric"] {
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border-radius: 10px;
        padding: 14px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }

    /* Download buttons */
    .stDownloadButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    /* Data editor */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ── Shared state (initialized once per session) ─────────────────────────────
# ── Auto-retrain model if sklearn version changed (BEFORE loading classifier) ─────
def _needs_retrain() -> bool:
    """Check if the model pickle needs retraining due to sklearn version mismatch."""
    import pathlib, json
    info_path = pathlib.Path(__file__).parent / "data" / "model_info.json"
    model_path = pathlib.Path(__file__).parent / "data" / "classifier_model.pkl"
    training_csv = pathlib.Path(__file__).parent / "data" / "training_data.csv"
    if not model_path.exists() or not training_csv.exists():
        return False
    try:
        import sklearn
        stored_version = None
        if info_path.exists():
            with open(info_path) as f:
                stored_version = json.load(f).get("sklearn_version")
        return stored_version != sklearn.__version__
    except Exception:
        return False

_retrain_needed = _needs_retrain()

if "kp_mgr" not in st.session_state:
    st.session_state.kp_mgr = KontenplanManager()

if "classifier" not in st.session_state:
    import warnings
    defaults = load_konto_defaults()
    # Suppress sklearn warnings if we're about to retrain anyway
    if _retrain_needed:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf = TransactionClassifier(konto_defaults=defaults)
    else:
        clf = TransactionClassifier(konto_defaults=defaults)
    st.session_state.classifier = clf

if "rechnung_rows" not in st.session_state:
    st.session_state.rechnung_rows = []

# Retrain now if needed
if _retrain_needed:
    try:
        import pathlib, json
        import pandas as pd
        training_csv = pathlib.Path(__file__).parent / "data" / "training_data.csv"
        clf = st.session_state.classifier
        df = pd.read_csv(training_csv)
        if len(df) > 10:
            result = clf._train_from_prepared_df(df)
            if "error" not in result:
                st.toast("ML-Modell automatisch neu trainiert für aktuelle sklearn-Version")
    except Exception:
        pass

# ── Sidebar (shared component) ───────────────────────────────────────────────

from core.sidebar import render_sidebar
render_sidebar()

# ── Home page ────────────────────────────────────────────────────────────────

clf: TransactionClassifier = st.session_state.classifier
kp: KontenplanManager = st.session_state.kp_mgr
db = DatabaseManager()

st.markdown("## 🏢 RDS Buchhaltung")
st.caption("Selbstlernende Schweizer KMU-Buchhaltung")

st.markdown("---")

# Dashboard metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    if clf.has_model:
        info = clf.model_info
        acc = info.get("cv_accuracy")
        st.metric("ML-Modell", f"{acc:.0%}" if acc else "Aktiv", delta="Genauigkeit")
    else:
        st.metric("ML-Modell", "—", delta="Nicht trainiert", delta_color="off")

with col2:
    st.metric("Kontenplan", f"{len(kp)} Konten")

with col3:
    st.metric("Gedächtnis", f"{clf.memory_count} Einträge")

with col4:
    corrections = clf.correction_count
    st.metric("Korrekturen", corrections)

# DB stats
if db.is_configured():
    stats = db.get_stats()
    if stats and stats.get("total", 0) > 0:
        st.markdown("---")
        st.markdown("### 🗄️ Datenbank")
        db_c1, db_c2, db_c3 = st.columns(3)
        db_c1.metric("Buchungen in DB", stats["total"])
        per_src = stats.get("per_source", {})
        db_c2.metric("Kontoauszüge", per_src.get("kontoauszug", 0))
        db_c3.metric("Rechnungen", per_src.get("rechnung", 0))

# Status
st.markdown("---")

if clf.has_model:
    info = clf.model_info
    st.success(
        f"ML-Modell aktiv — trainiert mit {info.get('total_samples', '?')} Buchungen, "
        f"{info.get('classes', '?')} Kontoklassen"
    )
else:
    st.warning(
        "Kein ML-Modell vorhanden. Klassifizierung läuft über Keyword-Regeln.\n\n"
        "Gehen Sie zu **Kontenplan & Training**, um ein Modell zu trainieren."
    )

if clf.should_retrain():
    st.info(
        f"Es gibt {clf.correction_count} neue Korrekturen. "
        "Das Modell sollte neu trainiert werden für bessere Genauigkeit.\n\n"
        "→ **Kontenplan & Training** → **Aus Korrekturen trainieren**"
    )

st.markdown("---")

# Feature cards
st.markdown("### Funktionen")

fc1, fc2 = st.columns(2)
with fc1:
    with st.container(border=True):
        st.markdown("#### 📄 Kontoauszug")
        st.markdown(
            "UBS PDF hochladen → automatisch kontieren → "
            "Excel/Banana Export oder per E-Mail versenden"
        )
    with st.container(border=True):
        st.markdown("#### ⚙️ Kontenplan & Training")
        st.markdown(
            "Kontenplan bearbeiten, Modell trainieren, "
            "Standard-Zuordnungen verwalten"
        )

with fc2:
    with st.container(border=True):
        st.markdown("#### 📸 Rechnung Scanner")
        st.markdown(
            "Quittung fotografieren → AI erkennt Daten → "
            "Buchung erstellen und per E-Mail senden"
        )
    with st.container(border=True):
        st.markdown("#### 🧠 Modell Manager")
        st.markdown(
            "ML-Modell herunterladen, hochladen, testen, "
            "Gedächtnis verwalten"
        )

# ── PostgreSQL setup guide (when DB not configured) ────────────────────────
if not db.is_configured():
    with st.expander("🗄️ PostgreSQL einrichten (optional)"):
        st.markdown("""
Die Datenbank ist **optional** — die App funktioniert auch ohne. Wenn Sie Buchungen
persistent speichern möchten:

**1. PostgreSQL installieren (macOS):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**2. Datenbank erstellen:**
```bash
createdb chadev_buchhaltung
```

**3. In `.env` konfigurieren:**
```
DATABASE_URL=postgresql://IhrBenutzername@localhost:5432/chadev_buchhaltung
```

**4. App neu starten:**
```bash
streamlit run app.py
```

Die Tabellen werden automatisch erstellt.
""")

st.markdown("")
st.caption("Das System lernt aus jeder Korrektur automatisch mit.")

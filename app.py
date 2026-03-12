"""
📄 RDS Buchhaltung — Self-Learning Swiss KMU Bookkeeping

Main entry point. Uses Streamlit's native multi-page layout via pages/ folder.
Initializes shared state (classifier, Kontenplan) once at startup.
"""

import streamlit as st

from core.kontenplan import KontenplanManager, load_konto_defaults
from core.classifier import TransactionClassifier

st.set_page_config(
    page_title="RDS Buchhaltung",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared state (initialized once per session) ─────────────────────────────

if "kp_mgr" not in st.session_state:
    st.session_state.kp_mgr = KontenplanManager()

if "classifier" not in st.session_state:
    defaults = load_konto_defaults()
    clf = TransactionClassifier(konto_defaults=defaults)
    st.session_state.classifier = clf

if "rechnung_rows" not in st.session_state:
    st.session_state.rechnung_rows = []

# ── Home page ────────────────────────────────────────────────────────────────

clf: TransactionClassifier = st.session_state.classifier
kp: KontenplanManager = st.session_state.kp_mgr

st.title("📄 RDS Buchhaltung")
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

st.markdown("### Funktionen")
st.markdown(
    "- **📄 Kontoauszug** — UBS PDF hochladen → automatisch kontieren → Excel/Banana Export\n"
    "- **📸 Rechnung Scanner** — Quittung fotografieren → AI erkennt Daten → Buchung erstellen\n"
    "- **⚙️ Kontenplan & Training** — Kontenplan bearbeiten, Modell trainieren\n"
    "- **📊 Lernverlauf** — Korrekturen ansehen, Modell-Statistiken\n\n"
    "Das System lernt aus jeder Korrektur automatisch mit."
)

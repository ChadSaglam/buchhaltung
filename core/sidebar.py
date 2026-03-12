"""
Shared sidebar component — imported by every page for consistent layout.
Also ensures session state is initialized (handles direct page navigation).
"""

import streamlit as st
from datetime import datetime


def _ensure_session_state():
    """Initialize session state if not already done (handles direct page load)."""
    if "classifier" not in st.session_state:
        import warnings
        from core.kontenplan import KontenplanManager, load_konto_defaults
        from core.classifier import TransactionClassifier

        if "kp_mgr" not in st.session_state:
            st.session_state.kp_mgr = KontenplanManager()

        defaults = load_konto_defaults()
        # Suppress sklearn version warnings — auto-retrain handles this
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf = TransactionClassifier(konto_defaults=defaults)
        st.session_state.classifier = clf

    if "kp_mgr" not in st.session_state:
        from core.kontenplan import KontenplanManager
        st.session_state.kp_mgr = KontenplanManager()

    if "rechnung_rows" not in st.session_state:
        st.session_state.rechnung_rows = []


def render_sidebar():
    """Render the shared sidebar on every page."""
    _ensure_session_state()

    from core.classifier import TransactionClassifier
    from core.kontenplan import KontenplanManager
    from core.email_sender import is_email_configured
    from core.database import DatabaseManager

    clf: TransactionClassifier = st.session_state.classifier
    kp: KontenplanManager = st.session_state.kp_mgr
    db = DatabaseManager()

    with st.sidebar:
        st.markdown("### 🏢 RDS Isolierungen")
        st.caption("Selbstlernende Buchhaltung")

        st.markdown("---")

        # System status
        st.markdown("**📊 System-Status**")

        # ML Model
        if clf.has_model:
            info = clf.model_info
            acc = info.get("cv_accuracy", 0)
            st.markdown(f"✅ **ML-Modell** — {acc:.0%}")
        else:
            st.markdown("⚠️ **ML-Modell** — Nicht trainiert")

        # Memory
        mem_count = clf.memory_count
        if mem_count > 0:
            st.markdown(f"✅ **Gedächtnis** — {mem_count} Einträge")
        else:
            st.markdown("⬜ **Gedächtnis** — Leer")

        # Email
        if is_email_configured():
            st.markdown("✅ **E-Mail** — Konfiguriert")
        else:
            st.markdown("❌ **E-Mail** — Nicht konfiguriert")

        # Database
        if db.is_configured():
            st.markdown("✅ **Datenbank** — Verbunden")
        else:
            st.markdown("➖ **Datenbank** — Optional")

        # Corrections pending
        corrections = clf.correction_count
        if corrections > 0:
            if clf.should_retrain():
                st.markdown(f"⚠️ **Korrekturen** — {corrections} (Retraining empfohlen)")
            else:
                st.markdown(f"🔄 **Korrekturen** — {corrections}")

        st.markdown("---")

        # Quick stats
        st.markdown("**📁 Daten**")
        st.markdown(f"• {len(kp)} Konten im Kontenplan")
        if clf.has_model:
            info = clf.model_info
            st.markdown(f"• {info.get('total_samples', '?')} Trainings-Buchungen")
            st.markdown(f"• {info.get('classes', '?')} Kontoklassen")

        rechnung_count = len(st.session_state.get("rechnung_rows", []))
        if rechnung_count > 0:
            st.markdown(f"• {rechnung_count} Rechnungen in Liste")

        st.markdown("---")

        # Footer
        st.caption(f"RDS Isolierungen · v2.5")
        st.caption(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")

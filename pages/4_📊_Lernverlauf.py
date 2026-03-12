"""
📊 Lernverlauf — Correction history, model stats, memory viewer.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from core.classifier import TransactionClassifier

st.header("📊 Lernverlauf")
st.caption("Korrekturen, Gedächtnis und Modell-Statistiken")

clf: TransactionClassifier = st.session_state.classifier

# ── Model info ───────────────────────────────────────────────────────────────

st.markdown("### 🤖 Modell-Status")

if clf.has_model:
    info = clf.model_info
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Genauigkeit", f"{info.get('cv_accuracy', 0):.0%}")
    c2.metric("Trainings-Daten", info.get("total_samples", "?"))
    c3.metric("Kontoklassen", info.get("classes", "?"))
    trained_at = info.get("trained_at", "")
    c4.metric("Trainiert am", trained_at[:10] if trained_at else "?")
else:
    st.warning("Kein ML-Modell vorhanden.")

# ── Memory (exact-match cache) ──────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🧠 Gedächtnis")
st.caption(
    "Das Gedächtnis speichert exakte Zuordnungen aus Ihren Korrekturen. "
    "Wenn dieselbe Beschreibung wieder vorkommt, wird die Korrektur sofort angewendet — "
    "ohne ML-Modell."
)

from core.classifier import MEMORY_PATH

if MEMORY_PATH.exists():
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        memory = json.load(f)

    if memory:
        mem_rows = []
        for key, val in sorted(memory.items()):
            mem_rows.append({
                "Beschreibung": key,
                "KtSoll": val.get("kt_soll", ""),
                "KtHaben": val.get("kt_haben", ""),
                "MwSt-Code": val.get("mwst_code", ""),
                "MwSt-%": val.get("mwst_pct", ""),
            })
        mem_df = pd.DataFrame(mem_rows)

        st.dataframe(mem_df, use_container_width=True, hide_index=True,
                      height=min(len(mem_df) * 38 + 40, 400))

        st.metric("Gespeicherte Zuordnungen", len(memory))

        if st.button("🗑️ Gedächtnis leeren", key="clear_memory"):
            MEMORY_PATH.unlink()
            clf._memory = {}
            st.success("Gedächtnis gelöscht.")
            st.rerun()
    else:
        st.info("Gedächtnis ist leer.")
else:
    st.info("Noch kein Gedächtnis aufgebaut. Korrigieren Sie Buchungen, um dem System beizubringen.")

# ── Correction history ───────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 📝 Korrekturen-Verlauf")
st.caption("Alle Korrekturen, die Sie an automatischen Kontierungen vorgenommen haben.")

corrections = clf.get_corrections(limit=200)

if corrections:
    corr_rows = []
    for c in reversed(corrections):  # newest first
        corr_rows.append({
            "Zeitpunkt": c.get("timestamp", "")[:19].replace("T", " "),
            "Beschreibung": c.get("beschreibung", ""),
            "Original Soll": c.get("original_soll", ""),
            "→ Korrigiert Soll": c.get("corrected_soll", ""),
            "Original Haben": c.get("original_haben", ""),
            "→ Korrigiert Haben": c.get("corrected_haben", ""),
            "MwSt-Code": c.get("corrected_mwst_code", ""),
        })
    corr_df = pd.DataFrame(corr_rows)

    st.dataframe(corr_df, use_container_width=True, hide_index=True,
                  height=min(len(corr_df) * 38 + 40, 500))

    st.metric("Total Korrekturen", len(corrections))

    col1, col2 = st.columns(2)
    with col1:
        if clf.should_retrain():
            st.info("Genug Korrekturen gesammelt — Modell kann unter 'Kontenplan & Training' neu trainiert werden.")
    with col2:
        if st.button("🗑️ Korrekturen leeren", key="clear_corrections"):
            clf.clear_corrections()
            st.success("Korrekturen gelöscht.")
            st.rerun()
else:
    st.info("Noch keine Korrekturen. Bearbeiten Sie Buchungen, um Korrekturen zu sammeln.")

# ── How it works ─────────────────────────────────────────────────────────────

st.markdown("---")
with st.expander("ℹ️ Wie das Lernsystem funktioniert"):
    st.markdown("""
**3-Schichten-Klassifizierung (nach Priorität):**

1. **🧠 Gedächtnis** — Exakte Treffer aus Ihren früheren Korrekturen.
   Wenn Sie z.B. "Sunrise" einmal zu KtSoll=6510 korrigiert haben,
   wird "Sunrise" in Zukunft immer automatisch richtig zugeordnet.

2. **🤖 ML-Modell** — TF-IDF + LogisticRegression, trainiert auf Ihren
   Banana-Buchhaltungsdaten. Erkennt auch neue, ähnliche Beschreibungen.

3. **📋 Keyword-Regeln** — Hardcodierte Fallback-Regeln für den Fall,
   dass weder Gedächtnis noch Modell eine Antwort haben.

**Lernzyklus:**

```
Sie korrigieren eine Buchung
       ↓
Korrektur wird im Gedächtnis gespeichert (sofort aktiv)
       ↓
Korrektur wird im Log gespeichert
       ↓
Nach 20+ Korrekturen → Modell kann neu trainiert werden
       ↓
Besseres Modell → weniger Korrekturen nötig
```
""")

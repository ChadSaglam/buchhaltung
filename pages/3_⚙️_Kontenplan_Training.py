"""
⚙️ Kontenplan & Training — Edit accounts, train/retrain model.
"""

import os
import sys
import tempfile

import streamlit as st
import pandas as pd

from core.classifier import TransactionClassifier
from core.kontenplan import KontenplanManager, load_konto_defaults, save_konto_defaults

st.header("⚙️ Kontenplan & Training")

clf: TransactionClassifier = st.session_state.classifier
kp: KontenplanManager = st.session_state.kp_mgr

MWST_CODE_OPTIONS = ["", "V81", "M81", "I81", "V77", "M77", "I77", "V25", "M25", "I25", "I26"]
MWST_PCT_OPTIONS = ["", "8.10", "7.70", "2.60", "2.50", "-8.10", "-7.70"]

# ── Model status ─────────────────────────────────────────────────────────────

st.markdown("### 📊 Status")

c1, c2, c3, c4 = st.columns(4)
with c1:
    if clf.has_model:
        info = clf.model_info
        st.metric("Genauigkeit", f"{info.get('cv_accuracy', 0):.0%}")
    else:
        st.metric("Genauigkeit", "—")
with c2:
    st.metric("Konten", len(kp))
with c3:
    st.metric("Gedächtnis", clf.memory_count)
with c4:
    st.metric("Korrekturen", clf.correction_count)

if clf.has_model:
    info = clf.model_info
    st.success(
        f"ML-Modell aktiv — {info.get('total_samples', '?')} Buchungen, "
        f"{info.get('classes', '?')} Klassen, "
        f"trainiert am {info.get('trained_at', '?')[:10]}"
    )
else:
    st.warning("Kein ML-Modell. Keyword-Regeln aktiv.")

# ── Training ─────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🎓 Modell trainieren")

tab_banana, tab_corrections = st.tabs(["📁 Aus Banana Export", "🔄 Aus Korrekturen"])

with tab_banana:
    st.caption("Banana Buchhaltung Export (.xls) hochladen um ein neues Modell zu trainieren.")
    st.markdown(
        "**So exportieren Sie aus Banana:**\n"
        "1. Datei → Tabelle exportieren\n"
        "2. Buchungen auswählen\n"
        "3. Format: XML-XLS"
    )

    training_file = st.file_uploader("Banana Export (.xls)", type=["xls"], key="training_upload")

    if training_file:
        if st.button("🚀 Modell trainieren", type="primary", key="train_banana"):
            with st.spinner("Modell wird trainiert..."):
                with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
                    tmp.write(training_file.getvalue())
                    tmp_path = tmp.name

                try:
                    result = clf.train_from_banana_xml(tmp_path)
                    # Reload Kontenplan
                    st.session_state.kp_mgr = KontenplanManager()
                    st.session_state.classifier.set_konto_defaults(load_konto_defaults())

                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(
                            f"Modell trainiert: {result['total_samples']} Buchungen, "
                            f"{result['classes']} Klassen, "
                            f"Genauigkeit: {result.get('cv_accuracy', 0):.0%}"
                        )
                        st.rerun()
                finally:
                    os.unlink(tmp_path)

with tab_corrections:
    st.caption("Modell mit den gesammelten Korrekturen verbessern.")

    n_corrections = clf.correction_count
    if n_corrections == 0:
        st.info("Noch keine Korrekturen. Bearbeiten Sie Buchungen im Kontoauszug-Tab, um dem System beizubringen.")
    else:
        st.markdown(f"**{n_corrections}** Korrekturen verfügbar.")

        if st.button("🔄 Modell mit Korrekturen verbessern", type="primary", key="train_corrections"):
            with st.spinner("Retraining mit Korrekturen..."):
                result = clf.train_from_corrections()
                if result is None:
                    st.error("Keine Korrekturen zum Trainieren.")
                elif "error" in result:
                    st.error(result["error"])
                else:
                    st.success(
                        f"Modell verbessert: {result['total_samples']} Buchungen, "
                        f"Genauigkeit: {result.get('cv_accuracy', 0):.0%}"
                    )
                    st.rerun()

# ── Kontenplan editor ────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### ✏️ Kontenplan bearbeiten")

kp_data = kp.plan
kp_df = pd.DataFrame([{"Konto": k, "Bezeichnung": v} for k, v in sorted(kp_data.items())])

edited_kp = st.data_editor(
    kp_df,
    use_container_width=True, hide_index=True, num_rows="dynamic",
    height=min(len(kp_df) * 38 + 40, 600),
    column_config={
        "Konto": st.column_config.TextColumn("Konto-Nr.", width="small"),
        "Bezeichnung": st.column_config.TextColumn("Bezeichnung", width="large"),
    },
    key="kp_editor",
)

if st.button("💾 Kontenplan speichern", type="primary", key="save_kp"):
    new_kp = {}
    for _, row in edited_kp.iterrows():
        k = str(row.get("Konto", "")).strip()
        v = str(row.get("Bezeichnung", "")).strip()
        if k and v:
            new_kp[k] = v
    kp.update_from_dict(new_kp)
    st.session_state.kp_mgr = KontenplanManager()  # reload
    st.success(f"Kontenplan gespeichert ({len(new_kp)} Konten)")
    st.rerun()

# ── Default mappings ─────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🔗 Standard-Zuordnungen")
st.caption("Wenn KontoSoll erkannt wird, welches KontoHaben und welcher MwSt-Code?")

defaults = load_konto_defaults()
if defaults:
    defaults_rows = []
    for soll, vals in sorted(defaults.items()):
        defaults_rows.append({
            "KontoSoll": soll,
            "Beschreibung": kp.get(soll),
            "KontoHaben": vals.get("KontoHaben", "1020"),
            "MwStCode": vals.get("MwStCode", ""),
            "MwSt-%": vals.get("MwStUStProz", ""),
        })
    defaults_df = pd.DataFrame(defaults_rows)

    edited_defaults = st.data_editor(
        defaults_df,
        use_container_width=True, hide_index=True, num_rows="dynamic",
        height=min(len(defaults_df) * 38 + 40, 600),
        column_config={
            "KontoSoll": st.column_config.TextColumn("KontoSoll", width="small"),
            "Beschreibung": st.column_config.TextColumn("Beschreibung", width="medium", disabled=True),
            "KontoHaben": st.column_config.TextColumn("KontoHaben", width="small"),
            "MwStCode": st.column_config.SelectboxColumn("MwSt-Code", options=MWST_CODE_OPTIONS, width="small"),
            "MwSt-%": st.column_config.SelectboxColumn("MwSt-%", options=MWST_PCT_OPTIONS, width="small"),
        },
        key="defaults_editor",
    )

    if st.button("💾 Zuordnungen speichern", type="primary", key="save_defaults"):
        new_defaults = {}
        for _, row in edited_defaults.iterrows():
            soll = str(row.get("KontoSoll", "")).strip()
            if soll:
                new_defaults[soll] = {
                    "KontoHaben": str(row.get("KontoHaben", "1020")).strip(),
                    "MwStCode": str(row.get("MwStCode", "")).strip(),
                    "MwStUStProz": str(row.get("MwSt-%", "")).strip(),
                }
        save_konto_defaults(new_defaults)
        clf.set_konto_defaults(new_defaults)
        st.success(f"Gespeichert ({len(new_defaults)} Zuordnungen)")
        st.rerun()
else:
    st.info("Noch keine Zuordnungen. Trainieren Sie zuerst ein Modell.")

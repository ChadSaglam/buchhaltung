"""
📸 AI Rechnung Scanner — Scan receipts with Ollama vision, auto-classify.
"""

import streamlit as st
import pandas as pd

from core.ollama_vision import check_ollama_status, extract_invoice
from core.classifier import TransactionClassifier, ClassificationResult, calc_mwst
from core.kontenplan import KontenplanManager
from core.export import df_to_styled_excel, df_to_banana_tsv, df_to_csv

st.header("📸 AI Rechnung Scanner")
st.caption("Rechnung / Quittung fotografieren oder hochladen → AI erkennt automatisch alle Details")

clf: TransactionClassifier = st.session_state.classifier
kp: KontenplanManager = st.session_state.kp_mgr
KONTENPLAN = kp.plan

MWST_CODE_OPTIONS = ["", "V81", "M81", "I81", "V77", "M77", "I77", "V25", "M25", "I25", "I26"]
MWST_PCT_OPTIONS = ["", "8.10", "7.70", "2.60", "2.50", "-8.10", "-7.70"]


def classify_rechnung(vendor: str, description: str, amount: float, mwst_rate: float | None) -> ClassificationResult:
    """Classify a Rechnung using the ML model or rules."""
    combined = f"{vendor} {description}"
    is_credit = any(kw in combined.lower() for kw in ["gutschrift", "zahlung erhalten", "einzahlung"])
    result = clf.classify(combined, is_credit, amount)

    # If AI detected a MwSt rate, override
    if mwst_rate is not None and mwst_rate > 0:
        if mwst_rate >= 7.0:
            result.mwst_pct = "8.10"
            result.mwst_code = result.mwst_code or "I81"
        elif mwst_rate >= 2.0:
            result.mwst_pct = "2.60"
            result.mwst_code = result.mwst_code or "I25"

        result.mwst_amount = calc_mwst(amount, result.mwst_pct)

    return result


# ── Ollama status ────────────────────────────────────────────────────────────

ollama_ok, ollama_msg, all_display_models, vision_model_names = check_ollama_status()

if not ollama_ok:
    st.error(ollama_msg)
    st.markdown("---")
    st.markdown("### 🛠 Setup-Anleitung")
    st.markdown(
        "1. **Ollama installieren:** [ollama.com/download](https://ollama.com/download)\n"
        "2. **Ollama starten:** `ollama serve`\n"
        "3. **Vision-Modell installieren:**\n\n"
        "```\nollama pull gemma3:12b\n```\n\n"
        "4. **Seite neu laden**"
    )
    st.stop()

# Model selection — show ALL models, vision ones marked with 👁
default_model = ollama_msg  # raw model name of best pick

# Find the display entry that starts with the default model name
default_idx = 0
for i, disp in enumerate(all_display_models):
    if disp.startswith(default_model):
        default_idx = i
        break

if len(all_display_models) > 1:
    selected_display = st.selectbox(
        "🤖 Modell wählen", options=all_display_models,
        index=default_idx, key="model_select",
        help="👁 Vision = kann Bilder analysieren. ☁ Cloud = läuft auf externem Server."
    )
else:
    selected_display = all_display_models[0]

# Extract raw model name from display string (strip tags)
vision_model = selected_display.split("  (")[0].strip()

# Warn if non-vision model selected for image scanning
if vision_model not in vision_model_names:
    st.warning(
        f"⚠️ **{vision_model}** hat keine Vision-Fähigkeit. "
        "Bilder können möglicherweise nicht analysiert werden. "
        "Wählen Sie ein Modell mit 👁 für beste Ergebnisse."
    )
else:
    st.success(f"Ollama verbunden — Modell: **{vision_model}** 👁")

with st.expander("💡 Tipps für bessere Erkennung"):
    st.markdown(
        "- **Grösseres Modell** = bessere Erkennung: `ollama pull gemma3:12b`\n"
        "- **Gute Beleuchtung**: Foto bei Tageslicht oder unter Lampe\n"
        "- **Ganzer Beleg sichtbar**: Alle 4 Ecken im Bild\n"
        "- **Nicht abgeschnitten**: Besonders Total und MwSt-Zeile\n"
        "- **Scharf fotografieren**: Kein Wackler, kein Zoom"
    )

# ── Upload ───────────────────────────────────────────────────────────────────

uploaded_images = st.file_uploader(
    "Rechnung / Quittung hochladen (Foto oder Scan)",
    type=["jpg", "jpeg", "png", "webp", "bmp"],
    accept_multiple_files=True,
    key="rechnung_upload",
)

if uploaded_images:
    for img_file in uploaded_images:
        with st.expander(f"📄 {img_file.name}", expanded=True):
            col_img, col_result = st.columns([1, 1])

            with col_img:
                st.image(img_file, use_container_width=True)

            with col_result:
                cache_key = f"ai_{img_file.name}_{img_file.size}_{vision_model}"
                if cache_key not in st.session_state:
                    with st.spinner(f"🤖 AI analysiert mit {vision_model}..."):
                        result = extract_invoice(img_file.getvalue(), vision_model)
                        st.session_state[cache_key] = result

                result = st.session_state[cache_key]

                if st.button("🔄 Erneut analysieren", key=f"retry_{cache_key}"):
                    with st.spinner(f"🤖 AI analysiert erneut mit {vision_model}..."):
                        result = extract_invoice(img_file.getvalue(), vision_model)
                        st.session_state[cache_key] = result
                        st.rerun()

                if result is None:
                    st.error("AI konnte die Rechnung nicht lesen. Versuchen Sie ein besseres Foto oder grösseres Modell.")
                else:
                    st.markdown("### Erkannte Daten")

                    vendor = st.text_input("Lieferant", value=result.get("vendor", ""), key=f"vendor_{cache_key}")
                    date_val = st.text_input("Datum", value=result.get("date", ""), key=f"date_{cache_key}")
                    inv_nr = st.text_input("Rechnung-Nr.", value=result.get("invoice_number", ""), key=f"invnr_{cache_key}")
                    desc = st.text_input("Beschreibung", value=result.get("description", ""), key=f"desc_{cache_key}")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        total = st.number_input("Betrag CHF (inkl. MwSt)",
                            value=float(result.get("total_amount", 0)),
                            format="%.2f", key=f"total_{cache_key}")
                    with col_b:
                        vat_rate = st.number_input("MwSt-% (0 wenn unbekannt)",
                            value=float(result.get("vat_rate", 0)),
                            format="%.1f", key=f"vat_{cache_key}")

                    # Auto-classify
                    acct = classify_rechnung(vendor, desc, total, vat_rate if vat_rate > 0 else None)

                    st.markdown("### Kontierung (automatisch)")

                    source_icon = {"Gedächtnis": "🧠", "ML": "🤖", "Regeln": "📋"}.get(acct.source, "❓")
                    st.caption(f"{source_icon} {acct.source} (Konfidenz: {acct.confidence:.0%})")

                    col_k1, col_k2 = st.columns(2)
                    with col_k1:
                        kt_soll = st.text_input(
                            f"KtSoll ({KONTENPLAN.get(acct.kt_soll, '')})",
                            value=acct.kt_soll, key=f"kts_{cache_key}")
                    with col_k2:
                        kt_haben = st.text_input(
                            f"KtHaben ({KONTENPLAN.get(acct.kt_haben, '')})",
                            value=acct.kt_haben, key=f"kth_{cache_key}")

                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        mwst_code = st.selectbox("MwSt-Code", options=MWST_CODE_OPTIONS,
                            index=MWST_CODE_OPTIONS.index(acct.mwst_code) if acct.mwst_code in MWST_CODE_OPTIONS else 0,
                            key=f"mcode_{cache_key}")
                    with col_m2:
                        mwst_pct = st.selectbox("MwSt-%", options=MWST_PCT_OPTIONS,
                            index=MWST_PCT_OPTIONS.index(acct.mwst_pct) if acct.mwst_pct in MWST_PCT_OPTIONS else 0,
                            key=f"mpct_{cache_key}")
                    with col_m3:
                        mwst_chf = acct.mwst_amount
                        st.text_input("MwSt CHF",
                            value=f"{mwst_chf:.2f}" if isinstance(mwst_chf, (int, float)) else "",
                            disabled=True, key=f"mchf_{cache_key}")

                    if st.button("✅ Zur Buchungsliste hinzufügen", type="primary", key=f"add_{cache_key}"):
                        final_mwst = calc_mwst(total, mwst_pct) if mwst_pct else ""
                        combined_desc = f"{vendor} - {desc}" if vendor and desc else vendor or desc

                        # Log correction (learns from the final values)
                        clf.log_correction(
                            beschreibung=combined_desc,
                            original=acct,
                            corrected_soll=kt_soll,
                            corrected_haben=kt_haben,
                            corrected_mwst_code=mwst_code,
                            corrected_mwst_pct=mwst_pct,
                        )

                        row_num = len(st.session_state.rechnung_rows) + 1
                        st.session_state.rechnung_rows.append({
                            "Nr": row_num,
                            "Datum": date_val,
                            "Beleg": "",
                            "Rechnung": inv_nr,
                            "Beschreibung": combined_desc,
                            "KtSoll": kt_soll,
                            "KtHaben": kt_haben,
                            "Betrag CHF": total,
                            "MwSt/USt-Code": mwst_code,
                            "Art Betrag": "",
                            "MwSt-%": mwst_pct,
                            "Gebuchte MwSt/USt CHF": final_mwst,
                            "KS3": "",
                        })
                        st.success(f"Buchung #{row_num} hinzugefügt — gelernt!")
                        st.rerun()

# ── Buchungsliste ────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 📋 Buchungsliste aus Rechnungen")

if not st.session_state.rechnung_rows:
    st.info("Noch keine Buchungen. Laden Sie eine Rechnung hoch, um zu beginnen.")
else:
    rechnung_df = pd.DataFrame(st.session_state.rechnung_rows)

    if "rechnung_df_edit" not in st.session_state:
        st.session_state.rechnung_df_edit = rechnung_df
    if len(rechnung_df) != len(st.session_state.rechnung_df_edit):
        st.session_state.rechnung_df_edit = rechnung_df

    edited_rechnung_df = st.data_editor(
        st.session_state.rechnung_df_edit,
        use_container_width=True, hide_index=True, num_rows="dynamic",
        height=min(len(rechnung_df) * 38 + 40, 500),
        column_config={
            "Nr": st.column_config.NumberColumn("Nr", width="small"),
            "Datum": st.column_config.TextColumn("Datum", width="small"),
            "Beleg": st.column_config.TextColumn("Beleg", width="small"),
            "Rechnung": st.column_config.TextColumn("Rechnung", width="small"),
            "Beschreibung": st.column_config.TextColumn("Beschreibung", width="large"),
            "KtSoll": st.column_config.TextColumn("KtSoll", width="small"),
            "KtHaben": st.column_config.TextColumn("KtHaben", width="small"),
            "Betrag CHF": st.column_config.NumberColumn("Betrag CHF", format="%.2f", width="small"),
            "MwSt/USt-Code": st.column_config.SelectboxColumn("MwSt/USt-Code", options=MWST_CODE_OPTIONS, width="small"),
            "Art Betrag": st.column_config.TextColumn("Art Betrag", width="small"),
            "MwSt-%": st.column_config.SelectboxColumn("MwSt-%", options=MWST_PCT_OPTIONS, width="small"),
            "Gebuchte MwSt/USt CHF": st.column_config.NumberColumn("Gebuchte MwSt/USt CHF", format="%.2f", width="small"),
            "KS3": st.column_config.TextColumn("KS3", width="small"),
        },
        key="rechnung_editor",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💾 Speichern", type="primary", key="rechnung_save"):
            st.session_state.rechnung_df_edit = edited_rechnung_df
            st.session_state.rechnung_rows = edited_rechnung_df.to_dict("records")
            st.success("Gespeichert!")
            st.rerun()
    with c2:
        if st.button("🔄 MwSt neu berechnen", key="rechnung_recalc"):
            recalc = edited_rechnung_df.copy()
            for idx, row in recalc.iterrows():
                mp = row.get("MwSt-%", "")
                bt = row.get("Betrag CHF", 0)
                if mp and bt:
                    try:
                        pv = abs(float(mp))
                        mv = round(float(bt) * pv / (100 + pv), 2)
                        if float(mp) < 0: mv = -mv
                        recalc.at[idx, "Gebuchte MwSt/USt CHF"] = mv
                    except (ValueError, TypeError):
                        pass
            st.session_state.rechnung_df_edit = recalc
            st.session_state.rechnung_rows = recalc.to_dict("records")
            st.success("MwSt neu berechnet!")
            st.rerun()
    with c3:
        if st.button("🗑️ Liste leeren", key="rechnung_clear"):
            st.session_state.rechnung_rows = []
            if "rechnung_df_edit" in st.session_state:
                del st.session_state.rechnung_df_edit
            st.rerun()

    # Downloads
    st.markdown("### ⬇️ Download Rechnungen")
    dl_df = edited_rechnung_df
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("🍌 Banana Import (.txt)",
            data=df_to_banana_tsv(dl_df).encode("utf-8"),
            file_name="banana_import_rechnungen.txt",
            mime="text/plain", type="primary", key="rechnung_banana")
    with c2:
        st.download_button("📥 Excel (.xlsx)",
            data=df_to_styled_excel(dl_df),
            file_name="buchhaltung_rechnungen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
            key="rechnung_excel")
    with c3:
        st.download_button("📥 CSV (.csv)",
            data=df_to_csv(dl_df),
            file_name="buchhaltung_rechnungen.csv",
            mime="text/csv", key="rechnung_csv")

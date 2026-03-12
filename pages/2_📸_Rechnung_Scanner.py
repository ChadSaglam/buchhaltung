"""
📸 AI Rechnung Scanner — Scan receipts with Ollama vision, auto-classify.

Supports "Buchhaltung Modell" pipeline: Vision AI → ML Classifier → Auto-Kontierung.
"""

import streamlit as st
import pandas as pd

from core.ollama_vision import (
    check_ollama_status, extract_invoice, extract_invoice_with_buchhaltung,
    is_buchhaltung_model, get_vision_models_ranked,
    BUCHHALTUNG_MODEL, BUCHHALTUNG_DISPLAY,
)
from core.classifier import TransactionClassifier, ClassificationResult, calc_mwst
from core.kontenplan import KontenplanManager
from core.export import df_to_styled_excel, df_to_banana_tsv, df_to_csv
from core.email_sender import is_email_configured, send_bookkeeping_email
from core.database import DatabaseManager
from core.sidebar import render_sidebar

render_sidebar()

st.markdown("## 📸 Rechnung Scanner")
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

# Model selection — Buchhaltung Modell first if available, then vision, then others
default_model = ollama_msg  # raw model name of best pick

# Find the best default index
default_idx = 0
if all_display_models and all_display_models[0].startswith("🏢"):
    # Buchhaltung Modell is available — select it by default
    default_idx = 0
else:
    for i, disp in enumerate(all_display_models):
        if disp.startswith(default_model):
            default_idx = i
            break

if len(all_display_models) > 1:
    selected_display = st.selectbox(
        "🤖 Modell wählen", options=all_display_models,
        index=default_idx, key="model_select",
        help=(
            "🏢 Buchhaltung Modell = Vision AI + Ihr trainiertes ML-Modell (empfohlen). "
            "👁 Vision = kann Bilder analysieren. ⚡ Cloud = läuft auf externem Server."
        ),
    )
else:
    selected_display = all_display_models[0]

# Determine mode
using_buchhaltung = is_buchhaltung_model(selected_display)

if using_buchhaltung:
    # Show pipeline info
    from core.ollama_vision import get_best_vision_model
    ranked_vision = get_vision_models_ranked(vision_model_names)
    backend_vision = ranked_vision[0] if ranked_vision else None

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown("**🏢 Buchhaltung Modell**")
        st.caption("Vision + ML Pipeline")
    with col_info2:
        info = clf.model_info
        acc = info.get("cv_accuracy", 0) if clf.has_model else 0
        mem = clf.memory_count
        st.markdown(f"**ML:** {acc:.0%} Genauigkeit")
        st.caption(f"{mem} Gedächtnis-Einträge")
    with col_info3:
        st.markdown(f"**Vision:** {backend_vision or '?'}")
        is_cloud_bv = backend_vision and (backend_vision.endswith(":cloud") or backend_vision.endswith("-cloud"))
        fallback_info = f" (+{len(ranked_vision)-1} Fallback)" if len(ranked_vision) > 1 else ""
        st.caption(("⚡ Cloud" if is_cloud_bv else "💻 Lokal") + fallback_info)

    st.success(
        f"Buchhaltung Modell aktiv — {len(ranked_vision)} Vision-Modelle mit Auto-Fallback, "
        f"ML-Modell klassifiziert automatisch"
    )

    # Extract raw model name for non-pipeline use
    vision_model = backend_vision or default_model
else:
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
        "- **Buchhaltung Modell wählen** = beste Erkennung + automatische Kontierung\n"
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
                st.image(img_file, width="stretch")

            with col_result:
                model_key = "buchhaltung" if using_buchhaltung else vision_model
                cache_key = f"ai_{img_file.name}_{img_file.size}_{model_key}"
                pipeline_cache_key = f"pipeline_{cache_key}"

                # Speed hint based on model
                if using_buchhaltung:
                    speed_hint = "Vision + ML-Klassifizierung"
                elif vision_model.endswith(":cloud") or vision_model.endswith("-cloud"):
                    speed_hint = "~5-15s"
                else:
                    speed_hint = "~30s-3min je nach Modellgrösse"

                if cache_key not in st.session_state:
                    with st.spinner(f"🤖 {'Buchhaltung Modell' if using_buchhaltung else vision_model} analysiert... ({speed_hint})"):
                        if using_buchhaltung:
                            result, pipe_info = extract_invoice_with_buchhaltung(
                                img_file.getvalue(), vision_model_names
                            )
                            st.session_state[cache_key] = result
                            st.session_state[pipeline_cache_key] = pipe_info
                        else:
                            result = extract_invoice(img_file.getvalue(), vision_model)
                            st.session_state[cache_key] = result

                result = st.session_state[cache_key]
                pipe_info = st.session_state.get(pipeline_cache_key)

                if st.button("🔄 Erneut analysieren", key=f"retry_{cache_key}"):
                    with st.spinner(f"🤖 {'Buchhaltung Modell' if using_buchhaltung else vision_model} analysiert erneut... ({speed_hint})"):
                        if using_buchhaltung:
                            result, pipe_info = extract_invoice_with_buchhaltung(
                                img_file.getvalue(), vision_model_names
                            )
                            st.session_state[cache_key] = result
                            st.session_state[pipeline_cache_key] = pipe_info
                        else:
                            result = extract_invoice(img_file.getvalue(), vision_model)
                            st.session_state[cache_key] = result
                        st.rerun()

                # Show pipeline steps if Buchhaltung model
                if pipe_info and using_buchhaltung:
                    with st.container(border=True):
                        st.markdown("**🏢 Pipeline-Schritte:**")
                        for step in pipe_info.get("steps", []):
                            st.markdown(f"  {step}")
                        if pipe_info.get("error"):
                            st.error(pipe_info["error"])

                if result is None:
                    st.error("AI konnte die Rechnung nicht lesen. Versuchen Sie ein besseres Foto oder grösseres Modell.")

                    # Show debug info to help troubleshoot
                    debug = st.session_state.get("_last_vision_debug", {})
                    if debug:
                        with st.expander("🔍 Debug-Informationen"):
                            st.markdown(f"**Modell:** {debug.get('model', '?')}")
                            st.markdown(f"**Bildgrösse:** {debug.get('image_size_kb', 0):.0f} KB")
                            for key, val in debug.items():
                                if key.startswith("attempt_"):
                                    st.markdown(f"**{key}:** `{str(val)[:300]}`")
                            st.caption("Diese Info hilft bei der Fehlersuche.")
                else:
                    st.markdown("### Erkannte Daten")

                    vendor = st.text_input("Lieferant", value=result.get("vendor", ""), key=f"vendor_{cache_key}")
                    date_val = st.text_input("Datum", value=result.get("date", ""), key=f"date_{cache_key}")
                    inv_nr = st.text_input("Rechnung-Nr.", value=result.get("invoice_number", ""), key=f"invnr_{cache_key}")
                    desc = st.text_input("Beschreibung", value=result.get("description", ""), key=f"desc_{cache_key}")

                    # Show line items if available
                    line_items = result.get("line_items", [])
                    if line_items and isinstance(line_items, list) and len(line_items) > 0:
                        with st.expander(f"📝 Einzelposten ({len(line_items)})"):
                            for item in line_items:
                                if isinstance(item, dict):
                                    item_name = item.get("item", "")
                                    item_amount = item.get("amount", "")
                                    if item_name:
                                        st.markdown(f"• {item_name}" + (f" — CHF {item_amount}" if item_amount else ""))

                    col_a, col_b = st.columns(2)
                    with col_a:
                        total = st.number_input("Betrag CHF (inkl. MwSt)",
                            value=float(result.get("total_amount", 0)),
                            format="%.2f", key=f"total_{cache_key}")
                    with col_b:
                        vat_rate = st.number_input("MwSt-% (0 wenn unbekannt)",
                            value=float(result.get("vat_rate", 0)),
                            format="%.1f", key=f"vat_{cache_key}")

                    # Auto-classify — use pipeline result if available, otherwise standard
                    pipeline_classification = result.get("_classification") if using_buchhaltung else None

                    if pipeline_classification:
                        # Use the Buchhaltung pipeline classification
                        acct = ClassificationResult(
                            kt_soll=pipeline_classification["kt_soll"],
                            kt_haben=pipeline_classification["kt_haben"],
                            mwst_code=pipeline_classification["mwst_code"],
                            mwst_pct=pipeline_classification["mwst_pct"],
                            mwst_amount=pipeline_classification["mwst_amount"],
                            confidence=pipeline_classification["confidence"],
                            source=pipeline_classification["source"],
                        )
                        # Still apply MwSt override from vision
                        if vat_rate > 0:
                            if vat_rate >= 7.0:
                                acct.mwst_pct = "8.10"
                                acct.mwst_code = acct.mwst_code or "I81"
                            elif vat_rate >= 2.0:
                                acct.mwst_pct = "2.60"
                                acct.mwst_code = acct.mwst_code or "I25"
                            acct.mwst_amount = calc_mwst(total, acct.mwst_pct)
                    else:
                        acct = classify_rechnung(vendor, desc, total, vat_rate if vat_rate > 0 else None)

                    st.markdown("### Kontierung (automatisch)")

                    source_icon = {"Gedächtnis": "🧠", "ML": "🤖", "Regeln": "📋"}.get(acct.source, "❓")
                    if using_buchhaltung:
                        st.caption(f"🏢 Buchhaltung Modell → {source_icon} {acct.source} (Konfidenz: {acct.confidence:.0%})")
                    else:
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

                        # Also save to memory for instant recall next time
                        clf.save_to_memory(
                            beschreibung=combined_desc,
                            kt_soll=kt_soll,
                            kt_haben=kt_haben,
                            mwst_code=mwst_code,
                            mwst_pct=mwst_pct,
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
                        st.success(f"Buchung #{row_num} hinzugefügt — 🏢 gelernt!")
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
        width="stretch", hide_index=True, num_rows="dynamic",
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

    # ── Action buttons ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("💾 Speichern", type="primary", key="rechnung_save", width="stretch"):
            st.session_state.rechnung_df_edit = edited_rechnung_df
            st.session_state.rechnung_rows = edited_rechnung_df.to_dict("records")
            st.success("Gespeichert!")

            # Save to DB if configured
            _db = DatabaseManager()
            if _db.is_configured():
                if _db.save_buchungen(edited_rechnung_df, source="rechnung"):
                    st.info("Buchungen in Datenbank gespeichert.")
                else:
                    st.warning("Datenbank-Speicherung fehlgeschlagen.")

            st.rerun()
    with c2:
        if st.button("🔄 MwSt neu berechnen", key="rechnung_recalc", width="stretch"):
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
        if st.button("🗑️ Liste leeren", key="rechnung_clear", width="stretch"):
            st.session_state.rechnung_rows = []
            if "rechnung_df_edit" in st.session_state:
                del st.session_state.rechnung_df_edit
            st.rerun()
    with c4:
        email_btn = st.button("📧 Per E-Mail senden", key="rechnung_email_btn", width="stretch")

    # ── Email send form ─────────────────────────────────────────────────
    if email_btn or st.session_state.get("_show_email_rechnung", False):
        st.session_state["_show_email_rechnung"] = True
        with st.container(border=True):
            st.markdown("#### 📧 E-Mail versenden")
            if not is_email_configured():
                st.error("E-Mail nicht konfiguriert. Bitte `.env` Datei mit SMTP-Daten erstellen.")
            else:
                email_to = st.text_input(
                    "Empfänger E-Mail",
                    value=st.session_state.get("_last_email_to", ""),
                    placeholder="empfaenger@example.ch",
                    key="rechnung_email_to",
                )
                email_subject = st.text_input(
                    "Betreff (optional)",
                    value="",
                    placeholder="RDS Buchhaltung — Rechnungen",
                    key="rechnung_email_subject",
                )
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("✅ Jetzt senden", type="primary", key="rechnung_send_email"):
                        if not email_to or "@" not in email_to:
                            st.error("Bitte gültige E-Mail-Adresse eingeben.")
                        else:
                            with st.spinner("E-Mail wird gesendet..."):
                                ok, msg = send_bookkeeping_email(
                                    df=edited_rechnung_df,
                                    to_email=email_to.strip(),
                                    subject=email_subject.strip() or None,
                                    base_filename="rechnungen",
                                )
                            if ok:
                                st.success(f"✅ {msg}")
                                st.session_state["_last_email_to"] = email_to.strip()
                                st.session_state["_show_email_rechnung"] = False
                            else:
                                st.error(f"❌ {msg}")
                with ec2:
                    if st.button("Abbrechen", key="rechnung_cancel_email"):
                        st.session_state["_show_email_rechnung"] = False
                        st.rerun()
                st.caption("Sendet Banana TXT + CSV als Anhang.")

    # ── Downloads ───────────────────────────────────────────────────────
    st.markdown("### ⬇️ Download Rechnungen")
    dl_df = edited_rechnung_df
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("🍌 Banana Import (.txt)",
            data=df_to_banana_tsv(dl_df).encode("utf-8"),
            file_name="banana_import_rechnungen.txt",
            mime="text/plain", type="primary", key="rechnung_banana",
            width="stretch")
    with c2:
        st.download_button("📥 Excel (.xlsx)",
            data=df_to_styled_excel(dl_df),
            file_name="buchhaltung_rechnungen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
            key="rechnung_excel", width="stretch")
    with c3:
        st.download_button("📥 CSV (.csv)",
            data=df_to_csv(dl_df),
            file_name="buchhaltung_rechnungen.csv",
            mime="text/csv", key="rechnung_csv", width="stretch")

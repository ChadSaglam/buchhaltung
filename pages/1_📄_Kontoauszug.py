"""
📄 Kontoauszug (PDF) — Upload, classify, edit, export.

Self-learning: every edit the user makes is logged as a correction.
Next time the same vendor appears, the classifier remembers.
"""

import streamlit as st
import pandas as pd

from core.pdf_parser import extract_transactions_from_pdf
from core.classifier import TransactionClassifier, ClassificationResult
from core.kontenplan import KontenplanManager
from core.export import fmt_swiss, df_to_styled_excel, df_to_banana_tsv, df_to_csv
from core.email_sender import is_email_configured, send_bookkeeping_email
from core.database import DatabaseManager
from core.sidebar import render_sidebar

render_sidebar()

st.markdown("## 📄 Kontoauszug")
st.caption("UBS Kontoauszug PDF hochladen → Bearbeiten → Export")

clf: TransactionClassifier = st.session_state.classifier
kp: KontenplanManager = st.session_state.kp_mgr
KONTENPLAN = kp.plan

# ── MWST options ─────────────────────────────────────────────────────────────

MWST_CODE_OPTIONS = ["", "V81", "M81", "I81", "V77", "M77", "I77", "V25", "M25", "I25", "I26"]
MWST_PCT_OPTIONS = ["", "8.10", "7.70", "2.60", "2.50", "-8.10", "-7.70"]


# ── Build accounting DataFrame ───────────────────────────────────────────────

def build_accounting_df(transactions: list[dict]) -> tuple[pd.DataFrame, list[ClassificationResult]]:
    """Convert raw transactions into accounting DataFrame + keep classification results."""
    rows = []
    results = []
    for i, tx in enumerate(transactions):
        is_credit = tx["Gutschrift"] is not None and tx["Gutschrift"] > 0
        betrag = tx["Betrag CHF"]
        acct = clf.classify(tx["Beschreibung"], is_credit, betrag)
        results.append(acct)

        rows.append({
            "Nr": 1 + i,
            "Datum": tx["Datum"],
            "Beleg": "",
            "Rechnung": "",
            "Beschreibung": tx["Beschreibung"],
            "KtSoll": acct.kt_soll,
            "KtHaben": acct.kt_haben,
            "Betrag CHF": betrag,
            "MwSt/USt-Code": acct.mwst_code,
            "Art Betrag": "",
            "MwSt-%": acct.mwst_pct,
            "Gebuchte MwSt/USt CHF": acct.mwst_amount,
            "KS3": "",
        })

    return pd.DataFrame(rows), results


# ── Upload ───────────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader("Kontoauszug PDF hochladen", type=["pdf"], key="pdf_upload")

if uploaded_file:
    with st.spinner("PDF wird verarbeitet..."):
        transactions = extract_transactions_from_pdf(uploaded_file)

    if not transactions:
        st.error("Keine Transaktionen gefunden. Bitte prüfen Sie das PDF-Format.")
        st.stop()

    st.success(f"{len(transactions)} Transaktionen extrahiert")

    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if "df" not in st.session_state or st.session_state.get("_last_file") != file_key:
        df, class_results = build_accounting_df(transactions)
        st.session_state.df = df
        st.session_state._class_results = class_results
        st.session_state._last_file = file_key
        st.session_state._original_df = df.copy()

    df = st.session_state.df

    # ── Source indicators ────────────────────────────────────────────────────
    if "_class_results" in st.session_state:
        results = st.session_state._class_results
        sources = pd.Series([r.source for r in results]).value_counts()
        cols = st.columns(len(sources))
        for i, (source, count) in enumerate(sources.items()):
            icon = {"Gedächtnis": "🧠", "ML": "🤖", "Regeln": "📋"}.get(source, "❓")
            cols[i].metric(f"{icon} {source}", count)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_view, tab_edit = st.tabs(["📊 Übersicht", "✏️ Bearbeiten"])

    with tab_view:
        st.markdown("### Buchhaltungstabelle")

        display_df = df.copy()
        for col in ["Betrag CHF", "Gebuchte MwSt/USt CHF"]:
            display_df[col] = display_df[col].apply(
                lambda x: fmt_swiss(x) if x != "" and x is not None and not (isinstance(x, float) and pd.isna(x)) else ""
            )

        st.dataframe(display_df, width="stretch", hide_index=True,
                      height=min(len(df) * 38 + 40, 800))

        total_betrag = sum(
            float(r) for r in df["Betrag CHF"]
            if r != "" and r is not None and not (isinstance(r, float) and pd.isna(r))
        )
        total_mwst = sum(
            float(r) for r in df["Gebuchte MwSt/USt CHF"]
            if r != "" and r is not None and not (isinstance(r, float) and pd.isna(r))
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Anzahl Buchungen", len(df))
        c2.metric("Total Betrag CHF", fmt_swiss(total_betrag))
        c3.metric("Total MwSt CHF", fmt_swiss(total_mwst))

    with tab_edit:
        st.markdown("### Tabelle bearbeiten")
        st.caption(
            "Änderungen an KtSoll/KtHaben werden als Korrekturen gespeichert — "
            "das System lernt daraus für zukünftige Buchungen."
        )

        edited_df = st.data_editor(
            df,
            width="stretch",
            hide_index=True,
            num_rows="dynamic",
            height=min(len(df) * 38 + 40, 800),
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
            key="pdf_editor",
        )

        col_save, col_recalc = st.columns(2)

        with col_save:
            if st.button("💾 Änderungen übernehmen & lernen", type="primary", key="pdf_save"):
                # Detect corrections and log them
                original_df = st.session_state.get("_original_df", df)
                corrections_logged = 0

                if "_class_results" in st.session_state:
                    for idx in range(min(len(edited_df), len(original_df))):
                        if idx >= len(st.session_state._class_results):
                            break

                        orig_result = st.session_state._class_results[idx]
                        new_row = edited_df.iloc[idx]
                        beschreibung = str(new_row.get("Beschreibung", ""))

                        if beschreibung:
                            clf.log_correction(
                                beschreibung=beschreibung,
                                original=orig_result,
                                corrected_soll=str(new_row.get("KtSoll", "")),
                                corrected_haben=str(new_row.get("KtHaben", "")),
                                corrected_mwst_code=str(new_row.get("MwSt/USt-Code", "")),
                                corrected_mwst_pct=str(new_row.get("MwSt-%", "")),
                            )
                            corrections_logged += 1

                st.session_state.df = edited_df
                st.session_state._original_df = edited_df.copy()

                if corrections_logged > 0:
                    st.success(f"Gespeichert — {corrections_logged} Korrekturen gelernt!")
                    if clf.should_retrain():
                        st.info("Genug Korrekturen gesammelt — Modell kann unter 'Kontenplan & Training' neu trainiert werden.")
                else:
                    st.success("Änderungen gespeichert!")

                # Save to DB if configured
                _db = DatabaseManager()
                if _db.is_configured():
                    if _db.save_buchungen(edited_df, source="kontoauszug"):
                        st.info("Buchungen in Datenbank gespeichert.")
                    else:
                        st.warning("Datenbank-Speicherung fehlgeschlagen.")

                st.rerun()

        with col_recalc:
            if st.button("🔄 MwSt neu berechnen", key="pdf_recalc"):
                recalc_df = edited_df.copy()
                for idx, row in recalc_df.iterrows():
                    mwst_pct = row.get("MwSt-%", "")
                    betrag = row.get("Betrag CHF", 0)
                    if mwst_pct and betrag:
                        try:
                            pct_val = abs(float(mwst_pct))
                            mwst_val = round(float(betrag) * pct_val / (100 + pct_val), 2)
                            if float(mwst_pct) < 0:
                                mwst_val = -mwst_val
                            recalc_df.at[idx, "Gebuchte MwSt/USt CHF"] = mwst_val
                        except (ValueError, TypeError):
                            pass
                st.session_state.df = recalc_df
                st.success("MwSt neu berechnet!")
                st.rerun()

    # ── Downloads & Email ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⬇️ Download & Versand")

    base_name = uploaded_file.name.replace(".pdf", "").replace(".PDF", "")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.download_button(
            "🍌 Banana Import (.txt)",
            data=df_to_banana_tsv(st.session_state.df).encode("utf-8"),
            file_name=f"banana_import_{base_name}.txt",
            mime="text/plain", type="primary", key="pdf_banana",
            width="stretch",
        )
    with c2:
        st.download_button(
            "📥 Excel (.xlsx)",
            data=df_to_styled_excel(st.session_state.df),
            file_name=f"buchhaltung_{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
            key="pdf_excel", width="stretch",
        )
    with c3:
        st.download_button(
            "📥 CSV (.csv)",
            data=df_to_csv(st.session_state.df),
            file_name=f"buchhaltung_{base_name}.csv",
            mime="text/csv", key="pdf_csv", width="stretch",
        )
    with c4:
        pdf_email_btn = st.button("📧 Per E-Mail senden", key="pdf_email_btn", width="stretch")

    # ── Email send form ─────────────────────────────────────────────────────
    if pdf_email_btn or st.session_state.get("_show_email_pdf", False):
        st.session_state["_show_email_pdf"] = True
        with st.container(border=True):
            st.markdown("#### 📧 E-Mail versenden")
            if not is_email_configured():
                st.error("E-Mail nicht konfiguriert. Bitte `.env` Datei mit SMTP-Daten erstellen.")
            else:
                email_to = st.text_input(
                    "Empfänger E-Mail",
                    value=st.session_state.get("_last_email_to", ""),
                    placeholder="empfaenger@example.ch",
                    key="pdf_email_to",
                )
                email_subject = st.text_input(
                    "Betreff (optional)",
                    value="",
                    placeholder=f"RDS Buchhaltung — {base_name}",
                    key="pdf_email_subject",
                )
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("✅ Jetzt senden", type="primary", key="pdf_send_email"):
                        if not email_to or "@" not in email_to:
                            st.error("Bitte gültige E-Mail-Adresse eingeben.")
                        else:
                            with st.spinner("E-Mail wird gesendet..."):
                                ok, msg = send_bookkeeping_email(
                                    df=st.session_state.df,
                                    to_email=email_to.strip(),
                                    subject=email_subject.strip() or None,
                                    base_filename=base_name,
                                )
                            if ok:
                                st.success(f"✅ {msg}")
                                st.session_state["_last_email_to"] = email_to.strip()
                                st.session_state["_show_email_pdf"] = False
                            else:
                                st.error(f"❌ {msg}")
                with ec2:
                    if st.button("Abbrechen", key="pdf_cancel_email"):
                        st.session_state["_show_email_pdf"] = False
                        st.rerun()
                st.caption("Sendet Banana TXT + CSV als Anhang.")

    with st.expander("ℹ️ Banana Import-Anleitung"):
        st.markdown(
            "**So importieren Sie in Banana Buchhaltung:**\n\n"
            "1. Die `.txt`-Datei oben herunterladen\n"
            "2. In Banana: **Aktionen** → **In Buchhaltung importieren**\n"
            "3. Importieren: **Buchungen** auswählen\n"
            "4. Dateityp: **Textdatei mit Spaltenüberschriften** auswählen\n"
            "5. Die heruntergeladene `.txt`-Datei auswählen\n"
            "6. Mit **OK** bestätigen\n\n"
            "**Format:** Tab-getrennt, UTF-8, Datum als YYYY-MM-DD\n\n"
            "**Spalten:** Date, Description, AccountDebit, AccountCredit, Amount, VatCode"
        )

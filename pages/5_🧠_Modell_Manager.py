"""
🧠 Modell Manager — Download, upload, inspect, and manage the Buchhaltung ML model.
"""

import io
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

from core.classifier import TransactionClassifier, DATA_DIR, MODEL_PATH, MODEL_INFO_PATH, MEMORY_PATH, CORRECTIONS_PATH
from core.sidebar import render_sidebar

render_sidebar()

st.markdown("## 🧠 Modell Manager")
st.caption("Ihr Buchhaltung Modell verwalten — herunterladen, hochladen, inspizieren und verbessern")

clf: TransactionClassifier = st.session_state.classifier

# ── Buchhaltung Model Overview ───────────────────────────────────────────────

st.markdown("### 🏢 Buchhaltung Modell")

# Check Ollama vision availability
try:
    from core.ollama_vision import check_ollama_status, get_best_vision_model
    ollama_ok, _, _, vision_names = check_ollama_status()
    best_vision = get_best_vision_model(vision_names) if ollama_ok else None
except Exception:
    ollama_ok = False
    best_vision = None
    vision_names = []

with st.container(border=True):
    st.markdown("**Ihr selbstlernendes Buchhaltungs-System besteht aus 2 Komponenten:**")

    col_ml, col_vision = st.columns(2)

    with col_ml:
        st.markdown("#### 🤖 ML-Klassifizierer")
        if clf.has_model:
            info = clf.model_info
            st.success("Aktiv")
            m1, m2 = st.columns(2)
            m1.metric("Genauigkeit", f"{info.get('cv_accuracy', 0):.0%}")
            m2.metric("Trainings-Daten", info.get("total_samples", "?"))
            m3, m4 = st.columns(2)
            m3.metric("Kontoklassen", info.get("classes", "?"))
            m4.metric("Gedächtnis", f"{clf.memory_count} Einträge")

            trained_at = info.get("trained_at", "")
            st.caption(f"Trainiert: {trained_at[:16].replace('T', ' ') if trained_at else '?'}")
        else:
            st.warning("Nicht trainiert")
            st.caption("Trainieren Sie unter Kontenplan & Training")

    with col_vision:
        st.markdown("#### 👁 Vision-Backend")
        if ollama_ok and best_vision:
            is_cloud = best_vision.endswith(":cloud") or best_vision.endswith("-cloud")
            st.success(f"Verbunden: {best_vision}")
            v1, v2 = st.columns(2)
            v1.metric("Vision-Modelle", len(vision_names))
            v2.metric("Typ", "⚡ Cloud" if is_cloud else "💻 Lokal")
            st.caption("Erkennt Rechnungen, liest Text aus Bildern")
        elif ollama_ok:
            st.warning("Ollama aktiv, aber kein Vision-Modell")
            st.caption("`ollama pull gemma3:4b` für Vision")
        else:
            st.error("Ollama nicht erreichbar")
            st.caption("`ollama serve` starten")

    # Pipeline status
    if clf.has_model and best_vision:
        st.success("🏢 **Buchhaltung Modell vollständig** — Vision erkennt Rechnungen, ML klassifiziert automatisch")
    elif clf.has_model:
        st.warning("🏢 **Teilweise aktiv** — ML-Modell bereit, Vision-Backend fehlt")
    elif best_vision:
        st.warning("🏢 **Teilweise aktiv** — Vision verfügbar, ML-Modell nicht trainiert")
    else:
        st.error("🏢 **Nicht konfiguriert** — Trainieren Sie ein Modell und installieren Sie ein Vision-Modell")

# ── How the System Works ─────────────────────────────────────────────────────

st.markdown("---")
with st.expander("ℹ️ Wie funktioniert das Buchhaltung Modell?"):
    st.markdown("""
**Das Buchhaltung Modell ist eine Pipeline aus 2 Stufen:**

| Stufe | Komponente | Aufgabe |
|-------|-----------|---------|
| 1️⃣ | **Vision AI** (Ollama) | Liest Rechnungen: Lieferant, Datum, Betrag, MwSt, Beschreibung |
| 2️⃣ | **ML-Klassifizierer** | Ordnet automatisch Konten zu (KtSoll, KtHaben, MwSt-Code) |

**Der ML-Klassifizierer hat 3 Schichten:**

| Priorität | Name | Funktion |
|-----------|------|----------|
| 1️⃣ | **Gedächtnis** | Exakte Treffer aus bestätigten Buchungen (100% genau) |
| 2️⃣ | **ML-Modell** | TF-IDF + LogReg — erkennt auch ähnliche Texte |
| 3️⃣ | **Keyword-Regeln** | Hardcodierte Fallback-Regeln |

**So lernt das System:**
1. Sie scannen eine Rechnung → Vision liest die Daten
2. ML klassifiziert → schlägt Konten vor
3. Sie bestätigen oder korrigieren
4. System speichert im Gedächtnis → beim nächsten Mal sofort korrekt

**Je mehr Sie buchen, desto besser wird das System!**
""")

# ── Model Stats ──────────────────────────────────────────────────────────────

if clf.has_model:
    st.markdown("---")
    st.markdown("### 📊 Detail-Statistiken")

    info = clf.model_info

    col_a, col_b = st.columns(2)
    with col_a:
        train_acc = info.get("train_accuracy", 0)
        cv_acc = info.get("cv_accuracy", 0)
        if train_acc and cv_acc:
            diff = train_acc - cv_acc
            if diff > 0.15:
                st.warning(f"Overfit-Warnung: Training {train_acc:.0%} vs. CV {cv_acc:.0%} (Differenz: {diff:.0%})")
            else:
                st.success(f"Training: {train_acc:.0%} | Cross-Validation: {cv_acc:.0%}")
        st.markdown(f"**sklearn Version:** {info.get('sklearn_version', 'unbekannt')}")

    with col_b:
        model_size = MODEL_PATH.stat().st_size / 1024 if MODEL_PATH.exists() else 0
        memory_size = MEMORY_PATH.stat().st_size / 1024 if MEMORY_PATH.exists() else 0
        st.markdown(f"**Modell-Datei:** {model_size:.0f} KB")
        st.markdown(f"**Gedächtnis-Datei:** {memory_size:.1f} KB")
        st.markdown(f"**Korrekturen:** {clf.correction_count}")

# ── Download Section ─────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### ⬇️ Modell herunterladen")
st.caption("Sichern Sie Ihr trainiertes Buchhaltung Modell inkl. Gedächtnis und Konfiguration")

if clf.has_model or clf.memory_count > 0:
    def create_model_bundle() -> bytes:
        """Create a zip with model, memory, info, and metadata."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if MODEL_PATH.exists():
                zf.write(MODEL_PATH, "classifier_model.pkl")
            if MODEL_INFO_PATH.exists():
                zf.write(MODEL_INFO_PATH, "model_info.json")
            if MEMORY_PATH.exists():
                zf.write(MEMORY_PATH, "memory.json")

            defaults_path = DATA_DIR / "konto_defaults.json"
            if defaults_path.exists():
                zf.write(defaults_path, "konto_defaults.json")

            kp_path = DATA_DIR / "kontenplan.json"
            if kp_path.exists():
                zf.write(kp_path, "kontenplan.json")

            training_path = DATA_DIR / "training_data.csv"
            if training_path.exists():
                zf.write(training_path, "training_data.csv")

            if CORRECTIONS_PATH.exists():
                zf.write(CORRECTIONS_PATH, "corrections.jsonl")

            meta = {
                "model_name": "Buchhaltung Modell",
                "business": "RDS Isolierungen",
                "exported_at": datetime.now().isoformat(),
                "app_version": "2.5",
                "model_accuracy": clf.model_info.get("cv_accuracy", 0) if clf.has_model else 0,
                "memory_entries": clf.memory_count,
                "total_samples": clf.model_info.get("total_samples", 0) if clf.has_model else 0,
                "sklearn_version": clf.model_info.get("sklearn_version", "") if clf.has_model else "",
                "contents": {
                    "classifier_model.pkl": "TF-IDF + LogisticRegression Pipeline",
                    "model_info.json": "Modell-Statistiken und Metadaten",
                    "memory.json": "Exakt-Treffer Gedächtnis aus Korrekturen",
                    "konto_defaults.json": "KontoSoll → KontoHaben Standard-Zuordnungen",
                    "kontenplan.json": "Schweizer Kontenrahmen",
                    "training_data.csv": "Originale Trainings-Buchungen",
                    "corrections.jsonl": "Alle Korrekturen-History",
                },
            }
            zf.writestr("README.json", json.dumps(meta, indent=2, ensure_ascii=False))

        return buf.getvalue()

    bundle = create_model_bundle()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    dl_c1, dl_c2, dl_c3 = st.columns(3)
    with dl_c1:
        st.download_button(
            "📦 Komplettes Modell-Paket (.zip)",
            data=bundle,
            file_name=f"buchhaltung_modell_{timestamp}.zip",
            mime="application/zip",
            type="primary",
            width="stretch",
            help="Enthält: ML-Modell, Gedächtnis, Kontenplan, Trainingsdaten, Korrekturen",
        )
    with dl_c2:
        if MODEL_PATH.exists():
            st.download_button(
                "🤖 Nur ML-Modell (.pkl)",
                data=MODEL_PATH.read_bytes(),
                file_name=f"buchhaltung_classifier_{timestamp}.pkl",
                mime="application/octet-stream",
                width="stretch",
            )
    with dl_c3:
        if MEMORY_PATH.exists() and clf.memory_count > 0:
            st.download_button(
                "🧠 Nur Gedächtnis (.json)",
                data=MEMORY_PATH.read_bytes(),
                file_name=f"buchhaltung_memory_{timestamp}.json",
                mime="application/json",
                width="stretch",
            )

    st.caption(f"Paketgrösse: {len(bundle) / 1024:.0f} KB — enthält alles für Backup oder Übertragung")
else:
    st.info("Noch nichts zum Herunterladen. Trainieren Sie zuerst ein Modell oder erstellen Sie Buchungen.")

# ── Upload Section ───────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### ⬆️ Modell hochladen")
st.caption("Ein zuvor gesichertes Buchhaltung Modell-Paket wiederherstellen")

uploaded_bundle = st.file_uploader(
    "Modell-Paket (.zip) oder einzelne Datei hochladen",
    type=["zip", "pkl", "json"],
    key="model_upload",
)

if uploaded_bundle:
    fname = uploaded_bundle.name.lower()

    if fname.endswith(".zip"):
        with st.expander("📦 Paket-Inhalt", expanded=True):
            try:
                with zipfile.ZipFile(io.BytesIO(uploaded_bundle.getvalue())) as zf:
                    file_list = zf.namelist()
                    st.markdown("**Enthaltene Dateien:**")
                    for f in file_list:
                        finfo = zf.getinfo(f)
                        st.markdown(f"- `{f}` ({finfo.file_size / 1024:.1f} KB)")

                    if "README.json" in file_list:
                        meta = json.loads(zf.read("README.json"))
                        st.markdown(f"**Modell:** {meta.get('model_name', 'Unbekannt')}")
                        st.markdown(f"**Exportiert:** {meta.get('exported_at', '?')[:19].replace('T', ' ')}")
                        st.markdown(f"**Genauigkeit:** {meta.get('model_accuracy', 0):.0%}")
                        st.markdown(f"**Gedächtnis:** {meta.get('memory_entries', 0)} Einträge")

            except Exception as e:
                st.error(f"Konnte Paket nicht lesen: {e}")

        col_restore, col_cancel = st.columns(2)
        with col_restore:
            if st.button("🔄 Modell wiederherstellen", type="primary", key="restore_model"):
                try:
                    with zipfile.ZipFile(io.BytesIO(uploaded_bundle.getvalue())) as zf:
                        restore_map = {
                            "classifier_model.pkl": MODEL_PATH,
                            "model_info.json": MODEL_INFO_PATH,
                            "memory.json": MEMORY_PATH,
                            "konto_defaults.json": DATA_DIR / "konto_defaults.json",
                            "kontenplan.json": DATA_DIR / "kontenplan.json",
                            "training_data.csv": DATA_DIR / "training_data.csv",
                            "corrections.jsonl": CORRECTIONS_PATH,
                        }
                        restored = []
                        for zip_name, target_path in restore_map.items():
                            if zip_name in zf.namelist():
                                target_path.write_bytes(zf.read(zip_name))
                                restored.append(zip_name)

                    from core.kontenplan import KontenplanManager, load_konto_defaults
                    st.session_state.kp_mgr = KontenplanManager()
                    defaults = load_konto_defaults()
                    new_clf = TransactionClassifier(konto_defaults=defaults)
                    st.session_state.classifier = new_clf

                    st.success(f"Buchhaltung Modell wiederhergestellt: {', '.join(restored)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Wiederherstellen: {e}")
        with col_cancel:
            st.caption("Achtung: Überschreibt das aktuelle Modell!")

    elif fname.endswith(".pkl"):
        if st.button("🤖 ML-Modell laden", type="primary", key="load_pkl"):
            MODEL_PATH.write_bytes(uploaded_bundle.getvalue())
            clf._load_model()
            st.success("ML-Modell geladen!")
            st.rerun()

    elif fname.endswith(".json"):
        try:
            data = json.loads(uploaded_bundle.getvalue())
            if isinstance(data, dict):
                sample = next(iter(data.values()), None) if data else None
                if sample and isinstance(sample, dict) and "kt_soll" in sample:
                    if st.button("🧠 Gedächtnis laden", type="primary", key="load_memory"):
                        MEMORY_PATH.write_text(
                            json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        clf._load_memory()
                        st.success(f"Gedächtnis geladen: {len(data)} Einträge")
                        st.rerun()
                else:
                    st.info("JSON erkannt, aber Format nicht eindeutig. Bitte als .zip-Paket hochladen.")
        except json.JSONDecodeError:
            st.error("Ungültige JSON-Datei.")

# ── Model Inspection ─────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🔍 Modell inspizieren")

if clf.has_model:
    tab_test, tab_top, tab_memory, tab_retrain = st.tabs([
        "🧪 Testen", "📈 Top-Zuordnungen", "🧠 Gedächtnis", "🔄 Neu trainieren"
    ])

    with tab_test:
        st.caption("Testen Sie wie das Buchhaltung Modell eine Beschreibung klassifiziert")

        test_input = st.text_input(
            "Beschreibung eingeben",
            placeholder="z.B. Migros Zürich Lebensmittel",
            key="test_classify",
        )

        if test_input:
            from core.classifier import ClassificationResult
            result = clf.classify(test_input, is_credit=False, betrag=100.0)
            from core.kontenplan import KontenplanManager
            kp = st.session_state.kp_mgr

            source_icon = {"Gedächtnis": "🧠", "ML": "🤖", "Regeln": "📋"}.get(result.source, "❓")

            r1, r2, r3 = st.columns(3)
            r1.metric("Quelle", f"{source_icon} {result.source}")
            r2.metric("KtSoll", f"{result.kt_soll} ({kp.get(result.kt_soll)})")
            r3.metric("Konfidenz", f"{result.confidence:.0%}")

            st.markdown(f"**KtHaben:** {result.kt_haben} ({kp.get(result.kt_haben)})")
            if result.mwst_code:
                st.markdown(f"**MwSt:** {result.mwst_code} / {result.mwst_pct}%")

            if result.source == "ML" and clf._model is not None:
                from core.classifier import preprocess
                text_clean = preprocess(test_input)
                try:
                    probs = clf._model.predict_proba([text_clean])[0]
                    classes = clf._model.classes_
                    top_n = sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)[:5]

                    st.markdown("**Top 5 ML-Vorhersagen:**")
                    for klass, prob in top_n:
                        name = kp.get(klass) or klass
                        st.markdown(f"`{klass}` {name} — **{prob:.0%}**")
                        st.progress(prob)
                except Exception:
                    pass

    with tab_top:
        st.caption("Häufigste Kontoklassen im Trainingsset")

        training_path = DATA_DIR / "training_data.csv"
        if training_path.exists():
            try:
                train_df = pd.read_csv(training_path)
                if "KontoSoll" in train_df.columns and "Beschreibung" in train_df.columns:
                    top_classes = (
                        train_df["KontoSoll"]
                        .dropna()
                        .value_counts()
                        .head(20)
                        .reset_index()
                    )
                    top_classes.columns = ["KontoSoll", "Anzahl"]

                    kp = st.session_state.kp_mgr
                    top_classes["Bezeichnung"] = top_classes["KontoSoll"].apply(
                        lambda x: kp.get(str(x)) or ""
                    )

                    st.dataframe(
                        top_classes[["KontoSoll", "Bezeichnung", "Anzahl"]],
                        width="stretch",
                        hide_index=True,
                        height=min(len(top_classes) * 38 + 40, 500),
                    )

                    st.metric("Total Kontoklassen", train_df["KontoSoll"].nunique())
            except Exception as e:
                st.error(f"Fehler beim Lesen: {e}")
        else:
            st.info("Keine Trainingsdaten vorhanden.")

    with tab_memory:
        st.caption("Alle gespeicherten Zuordnungen im Gedächtnis")

        if clf.memory_count > 0:
            from core.classifier import MEMORY_PATH as mem_path
            if mem_path.exists():
                with open(mem_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)

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

                st.dataframe(
                    mem_df,
                    width="stretch",
                    hide_index=True,
                    height=min(len(mem_df) * 38 + 40, 400),
                )
                st.metric("Gedächtnis-Einträge", len(memory))
        else:
            st.info(
                "Gedächtnis ist leer. Es füllt sich automatisch, wenn Sie Buchungen bestätigen "
                "oder korrigieren."
            )

    with tab_retrain:
        st.caption("Modell mit neuesten Korrekturen verbessern")

        corr_count = clf.correction_count
        if corr_count > 0:
            st.info(f"**{corr_count} Korrekturen** seit letztem Training verfügbar")

            if st.button("🔄 Jetzt neu trainieren", type="primary", key="retrain_btn"):
                with st.spinner("Modell wird neu trainiert..."):
                    result = clf.train_from_corrections()
                if result:
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(
                            f"Neu trainiert — Genauigkeit: {result.get('cv_accuracy', 0):.0%} "
                            f"({result.get('total_samples', 0)} Buchungen, {result.get('classes', 0)} Klassen)"
                        )
                        st.session_state.classifier = clf
                        st.rerun()
                else:
                    st.warning("Keine Korrekturen zum Trainieren gefunden.")
        else:
            st.success("Modell ist aktuell — keine neuen Korrekturen vorhanden.")

        st.markdown("---")
        st.caption("**Tipp:** Je mehr Rechnungen Sie scannen und bestätigen, desto besser wird das Modell.")

else:
    tab_memory_only, = st.tabs(["🧠 Gedächtnis"])
    with tab_memory_only:
        if clf.memory_count > 0:
            from core.classifier import MEMORY_PATH as mem_path
            if mem_path.exists():
                with open(mem_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                mem_rows = [{"Beschreibung": k, "KtSoll": v.get("kt_soll", ""), "KtHaben": v.get("kt_haben", "")}
                            for k, v in sorted(memory.items())]
                st.dataframe(pd.DataFrame(mem_rows), width="stretch", hide_index=True)
        else:
            st.info("Gedächtnis ist leer.")

# ── Danger Zone ──────────────────────────────────────────────────────────────

st.markdown("---")
with st.expander("⚠️ Gefahrenzone"):
    st.caption("Aktionen die nicht rückgängig gemacht werden können — sichern Sie zuerst Ihr Modell!")

    dz1, dz2, dz3 = st.columns(3)
    with dz1:
        if st.button("🗑️ Gedächtnis leeren", key="danger_clear_mem"):
            if MEMORY_PATH.exists():
                MEMORY_PATH.unlink()
            clf._memory = {}
            st.success("Gedächtnis gelöscht.")
            st.rerun()
    with dz2:
        if st.button("🗑️ Korrekturen leeren", key="danger_clear_corr"):
            clf.clear_corrections()
            st.success("Korrekturen gelöscht.")
            st.rerun()
    with dz3:
        if st.button("🗑️ ML-Modell löschen", key="danger_clear_model"):
            if MODEL_PATH.exists():
                MODEL_PATH.unlink()
            if MODEL_INFO_PATH.exists():
                MODEL_INFO_PATH.unlink()
            clf._model = None
            st.success("ML-Modell gelöscht.")
            st.rerun()

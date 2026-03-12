# RDS Buchhaltung — Selbstlernende KMU-Buchhaltung

Streamlit-App für die doppelte Buchhaltung mit MWST. Lernt aus jeder Korrektur automatisch.

## Starten

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Funktionen

| Seite | Beschreibung |
|-------|-------------|
| 📄 Kontoauszug | UBS PDF hochladen → automatisch kontieren → Export |
| 📸 Rechnung Scanner | Quittung mit Ollama AI scannen → Buchung erstellen |
| ⚙️ Kontenplan & Training | Kontenplan bearbeiten, ML-Modell trainieren |
| 📊 Lernverlauf | Korrekturen ansehen, Gedächtnis verwalten |

## Selbstlernendes System

3-Schichten-Klassifizierung:

1. **🧠 Gedächtnis** — Sofort aus Korrekturen (exakte Treffer)
2. **🤖 ML-Modell** — TF-IDF + LogisticRegression (trainiert auf Banana-Daten)
3. **📋 Keyword-Regeln** — Hardcodierter Fallback

Jede Korrektur wird sofort im Gedächtnis aktiv. Nach 20+ Korrekturen kann das ML-Modell neu trainiert werden.

## Projektstruktur

```
buchhaltung/
├── app.py                  # Hauptseite (Dashboard)
├── requirements.txt
├── core/
│   ├── classifier.py       # 3-Schichten-Klassifizierer
│   ├── kontenplan.py        # Kontenplan-Manager (JSON)
│   ├── pdf_parser.py        # UBS PDF-Parser
│   ├── ollama_vision.py     # Ollama Rechnung-Scanner
│   └── export.py            # Excel/Banana/CSV Export
├── pages/
│   ├── 1_📄_Kontoauszug.py
│   ├── 2_📸_Rechnung_Scanner.py
│   ├── 3_⚙️_Kontenplan_Training.py
│   └── 4_📊_Lernverlauf.py
└── data/
    ├── classifier_model.pkl  # Trainiertes Modell
    ├── kontenplan.json        # Kontenplan
    ├── konto_defaults.json    # Standard-Zuordnungen
    ├── memory.json            # Exakte Korrekturen
    ├── corrections.jsonl      # Korrektur-Log
    └── training_data.csv      # Trainingsdaten
```

## Erstes Training

```bash
# Banana Export hochladen im Tab "Kontenplan & Training"
# ODER direkt mit Python:
cd buchhaltung
python -c "
from core.classifier import TransactionClassifier
clf = TransactionClassifier()
result = clf.train_from_banana_xml('../Doppelte-Buchhaltung-mit-MWST-USt-2024.Buchungen.xls')
print(result)
"
```
